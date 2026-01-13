// auth-interceptor.js - Authentication interceptor for jobs app with user activity tracking

// Initialize WebSocket connection for token refresh notifications
let wsSocket = null;
let intentionalDisconnect = false;
let retryAttempts = 0;
const maxRetryAttempts = 10;
const baseDelay = 1000; // 1 second base delay
let retryTimer = null;

// Track user activity to trigger token refresh
let lastActivity = Date.now();
let isRememberMeChecked = false; // Track if user logged in with "Remember Me"
const ACTIVITY_TIMEOUT = 18 * 60 * 1000;
const accessTokenExpiry =  25 * 60 * 1000; // 25 minutes in milliseconds
const REMEMBER_ME_REFRESH_INTERVAL = 20 * 60 * 1000; // 20 minutes for remember me sessions

// Function to call the cookie refresh endpoint
let refreshPromise = null; // Promise to deduplicate concurrent refresh attempts
let retryCount = 0;
const maxRetries = 5; // Max retry attempts

// Function to get CSRF token from cookie or meta tag
function getCsrfToken() {
    // Try to get from meta tag first
    let token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    // If not found in meta tag, try to get from cookie
    if (!token) {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    token = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
    }
    return token;
}

// Check if tokens are about to expire and refresh them automatically
async function checkAndRefreshToken() {
    // Don't refresh if page is hidden (tab switched or minimized)
    if (document.hidden) {
        return false;
    }
    console.log("Updating User's activity!")
    try {
        // Make a request to the user profile endpoint which will update activity
        // and potentially trigger server-side refresh if needed
        const response = await axios.get('/api/accounts/auth/users/me/', {
            withCredentials: true, // Include cookies in requests
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            }
        });

        return response.status === 200;
    } catch (error) {
        // Errors are handled by the interceptor, so we just return false here
        console.error('Error checking token status:', error);
        return false;
    }
}

// Function to set remember me status
function setRememberMeStatus(rememberMe) {
    isRememberMeChecked = rememberMe;
    console.log('Remember Me status set to:', rememberMe);

    // If remember me is checked, start the interval-based refresh
    if (rememberMe) {
        startRememberMeRefreshInterval();
    } else {
        // If remember me is unchecked, clear the interval
        if (window.rememberMeInterval) {
            clearInterval(window.rememberMeInterval);
            window.rememberMeInterval = null;
        }
    }
}

// Make the function globally accessible so it can be called from other scripts
window.setRememberMeStatus = setRememberMeStatus;

// Start interval-based refresh for remember me sessions
function startRememberMeRefreshInterval() {
    // Clear any existing interval
    if (window.rememberMeInterval) {
        clearInterval(window.rememberMeInterval);
    }

    // Set up interval to refresh tokens every 20 minutes for remember me sessions
    window.rememberMeInterval = setInterval(async () => {
        console.log('Executing interval-based token refresh for remember me session');
        await checkAndRefreshToken();
    }, REMEMBER_ME_REFRESH_INTERVAL);

    console.log('Started interval-based token refresh for remember me sessions');
}

async function handleUserActivity() {
    const now = Date.now();

    // If remember me is checked, use interval-based refresh instead of activity-based
    if (isRememberMeChecked) {
        // Activity-based refresh is not needed for remember me sessions
        // The interval-based refresh will handle token refresh
        lastActivity = now;
        return;
    }

    const deltaTime = now - lastActivity;

    if((deltaTime >= ACTIVITY_TIMEOUT) && (deltaTime < accessTokenExpiry))
    {
        try {
            const refreshretVal = await checkAndRefreshToken();
            if(refreshretVal)
            {
                lastActivity = now;
            }
        } catch (error) {
            console.error('Error during token refresh in handleUserActivity:', error);
        }
    }

}

// Add event listeners for user activities
function setupActivityListeners() {
    // Events that count as user activity
    const events = ['load', 'mousedown', 'click', 'keydown', 'touchstart', 'scroll'];
    
    events.forEach(event => {
        window.addEventListener(event, handleUserActivity, true); // Use capture phase
    });
    
    // Page visibility change listener to avoid refreshing when tab is hidden
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            // When page becomes visible again, treat it as user activity
            handleUserActivity();
        }
    });
}

function initWebSocket() {
    // Check if there's already an active connection and return early to avoid multiple connections
    if (wsSocket && (wsSocket.readyState === WebSocket.CONNECTING || wsSocket.readyState === WebSocket.OPEN)) {
        console.log('WebSocket connection already active, skipping initialization');
        return;
    }

    // Construct WebSocket URL based on current protocol
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/token-notifications/`;

    // Create a new WebSocket instance
    wsSocket = new WebSocket(wsUrl);

    wsSocket.onopen = function(event) {
        console.log('WebSocket connection established for token notifications');
        // Reset retry attempts and clear any pending retry timer on successful connection
        retryAttempts = 0;
        if (retryTimer) {
            clearTimeout(retryTimer);
            retryTimer = null;
        }
    };

    wsSocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        // Check for the new format: {"type": "refresh_tokens", "message": "REFRESH"}
        if (data.type === 'refresh_tokens' && data.message === 'REFRESH') {
            console.log('Received token refresh notification from server');
            // Call the cookie refresh endpoint to get new tokens
            refreshTokenFromServer();
        }
        // Check for logout notification: {"type": "refresh_tokens", "message": "LOGOUT"}
        else if (data.type === 'refresh_tokens' && data.message === 'LOGOUT') {
            console.log('Received logout notification from server');
            // Call logoutAndRedirect to handle proper user logout
            logoutAndRedirect();
        }
    };

    wsSocket.onclose = function(event) {
        console.log('WebSocket connection closed for token notifications.');

        // Only attempt reconnects when the close was unintentional
        if (!intentionalDisconnect) {
            // Check if we've reached the max retry attempts
            if (retryAttempts < maxRetryAttempts) {
                // Calculate delay with exponential backoff: baseDelay * 2^attempts
                const delay = Math.min(baseDelay * Math.pow(2, retryAttempts), 30000); // Cap at 30 seconds
                console.log(`Attempting to reconnect in ${delay}ms (attempt ${retryAttempts + 1}/${maxRetryAttempts})`);

                retryTimer = setTimeout(() => {
                    retryAttempts++;
                    initWebSocket();
                }, delay);
            } else {
                console.error('Max retry attempts reached. WebSocket reconnection stopped.');
            }
        } else {
            console.log('WebSocket closed intentionally, not attempting to reconnect.');
        }
    };

    wsSocket.onerror = function(error) {
        console.error('WebSocket error for token notifications:', error);
    };
}

// Function to properly close the WebSocket connection
function closeWebSocket() {
    if (wsSocket) {
        // Set the intentional disconnect flag to prevent reconnection attempts
        intentionalDisconnect = true;

        // Clear any pending retry timer
        if (retryTimer) {
            clearTimeout(retryTimer);
            retryTimer = null;
        }

        // Close the WebSocket connection
        wsSocket.close();
        wsSocket = null;
    }
}

// Function to handle user logout and redirect to login
async function logoutAndRedirect(logoutReason = 'inactive') {
    // Clear the remember me interval before logging out
    if (window.rememberMeInterval) {
        clearInterval(window.rememberMeInterval);
        window.rememberMeInterval = null;
    }

    // Close the WebSocket connection before logging out
    closeWebSocket();

    try {
        // Call the server-side logout endpoint to properly log out the user
        await axios.post('/api/accounts/auth/logout/', {}, {
            withCredentials: true, // Include cookies in requests
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            }
        });
    } catch (error) {
        console.error('Error during logout:', error);
        // Even if the logout API call fails, still redirect to login
    } finally {
        // Redirect to login page with reason parameter regardless of logout API result
        const reasonParam = logoutReason ? `?reason=${encodeURIComponent(logoutReason)}` : '';
        window.location.href = `/login/${reasonParam}`;
    }
}



async function refreshTokenFromServer() {
    // Deduplicate concurrent refresh attempts by returning the same promise if one is in flight
    if (refreshPromise) {
        return refreshPromise;
    }

    const executeRefresh = async () => {
        try {
            const response = await axios.post('/api/accounts/auth/token/cookie-refresh/', {}, {
                withCredentials: true, // Include cookies in requests
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                }
            });

            // Reset retry count on successful refresh
            retryCount = 0;
            console.log('Token successfully refreshed from server notification');
            return response;
        } catch (error) {
            console.error('Error during token refresh from server notification:', error);

            // If it's a 401 or 403 error, immediately redirect to login
            if (error.response && (error.response.status === 401 || error.response.status === 403)) {
                retryCount = 0; // Reset retry count
                logoutAndRedirect();
                return;
            }

            // Handle network errors (poor connectivity)
            if (!error.response) {
                console.warn('Network error during token refresh, possibly poor connectivity:', error.message);

                // For Remember Me sessions, we might want to be more tolerant of temporary network issues
                if (isRememberMeChecked) {
                    console.log('Remember Me session detected, applying more tolerant retry logic for network issues');

                    // Increase max retries for Remember Me sessions to handle temporary connectivity issues
                    const maxRetriesForRememberMe = maxRetries * 2; // Double the retry attempts

                    if (retryCount < maxRetriesForRememberMe) {
                        // Calculate delay with exponential backoff and jitter
                        const backoff = baseDelay * Math.pow(2, retryCount); // Exponential backoff
                        const jitter = Math.random() * 1000; // Random jitter up to 1 second
                        const delay = backoff + jitter;

                        console.log(`Token refresh failed due to network issue, retrying in ${delay}ms (attempt ${retryCount + 1}/${maxRetriesForRememberMe})`);

                        retryCount++;

                        // Wait for the calculated delay before retrying
                        await new Promise(resolve => setTimeout(resolve, delay));

                        // Retry the refresh
                        return await executeRefresh();
                    } else {
                        console.error('Max retry attempts reached for token refresh with poor connectivity. Initiating logout.');
                        retryCount = 0; // Reset retry count
                        logoutAndRedirect();
                    }
                } else {
                    // For standard sessions, use the original retry logic
                    if (retryCount < maxRetries) {
                        // Calculate delay with exponential backoff and jitter
                        const backoff = baseDelay * Math.pow(2, retryCount); // Exponential backoff
                        const jitter = Math.random() * 1000; // Random jitter up to 1 second
                        const delay = backoff + jitter;

                        console.log(`Token refresh failed, retrying in ${delay}ms (attempt ${retryCount + 1}/${maxRetries})`);

                        retryCount++;

                        // Wait for the calculated delay before retrying
                        await new Promise(resolve => setTimeout(resolve, delay));

                        // Retry the refresh
                        return await executeRefresh();
                    } else {
                        console.error('Max retry attempts reached for token refresh. Initiating logout.');
                        retryCount = 0; // Reset retry count
                        logoutAndRedirect();
                    }
                }
            } else {
                // For other types of errors, use the original logic
                if (retryCount < maxRetries) {
                    // Calculate delay with exponential backoff and jitter
                    const backoff = baseDelay * Math.pow(2, retryCount); // Exponential backoff
                    const jitter = Math.random() * 1000; // Random jitter up to 1 second
                    const delay = backoff + jitter;

                    console.log(`Token refresh failed, retrying in ${delay}ms (attempt ${retryCount + 1}/${maxRetries})`);

                    retryCount++;

                    // Wait for the calculated delay before retrying
                    await new Promise(resolve => setTimeout(resolve, delay));

                    // Retry the refresh
                    return await executeRefresh();
                } else {
                    console.error('Max retry attempts reached for token refresh. Initiating logout.');
                    retryCount = 0; // Reset retry count
                    logoutAndRedirect();
                }
            }
        } finally {
            // Clear the refresh promise when the operation completes (either success or failure)
            refreshPromise = null;
        }
    };

    // Store the promise to prevent concurrent executions
    refreshPromise = executeRefresh();
    return refreshPromise;
}

// Function to set up the authentication interceptor
function setupAuthInterceptor() {
    // Add axios interceptor for handling 401 and 403 responses
    window.axios.interceptors.response.use(
        response => {
            // If response is successful, return it as is
            return response;
        },
        error => {
            // Handle 401 and 403 errors by redirecting to login
            if (error.response && (error.response.status === 401 || error.response.status === 403)) {
                // Clear any local data if needed
                // Logout and redirect to login page
                logoutAndRedirect();
            }

            // Return the error to the calling function
            return Promise.reject(error);
        }
    );
}

// Initialize auth functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Set up activity listeners
    setupActivityListeners();

    // Initialize WebSocket connection for token refresh notifications
    initWebSocket();

    // Check if axios is available before setting up interceptors
    if (typeof window.axios !== 'undefined' && window.axios) {
        // Set up the authentication interceptor
        setupAuthInterceptor();
    } else {
        // Log a clear error if axios is not available
        console.error('Axios not found. Authentication interceptor will not be set up. Please ensure axios is loaded before auth-interceptor.js.');

        // Try to initialize after a delay in case axios is still loading
        setTimeout(() => {
            if (typeof window.axios !== 'undefined' && window.axios) {
                // Set up the authentication interceptor
                setupAuthInterceptor();
            } else {
                console.error('Axios still not found after retry. Authentication interceptor could not be set up.');
            }
        }, 1000); // Retry after 1 second
    }
});