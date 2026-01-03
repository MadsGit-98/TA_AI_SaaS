// auth-interceptor.js - Authentication interceptor for jobs app with user activity tracking
// Uses axios instead of fetch with activity-based token refresh

/**
 * Retrieve the page CSRF token from a meta[name="csrf-token"] tag or the "csrftoken" cookie.
 * @returns {string|undefined} The CSRF token if found, otherwise `undefined`.
 */
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

/**
 * Trigger a server-side activity check that refreshes authentication tokens when appropriate; does nothing if the document is hidden.
 *
 * Sends a request to the user profile endpoint to update activity and let the server perform any necessary token refresh.
 * @returns {boolean} `true` if the server responded with status 200, `false` otherwise.
 */
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

// Track user activity to trigger token refresh
let lastActivity = Date.now();
const ACTIVITY_TIMEOUT = 18 * 60 * 1000; 
const accessTokenExpiry =  25 * 60 * 1000; /**
 * Monitors elapsed user inactivity and attempts a token refresh when the inactivity threshold is reached.
 *
 * When the time since the last recorded activity is at least ACTIVITY_TIMEOUT and before the access token expiry, calls checkAndRefreshToken(); if that succeeds, updates lastActivity to the current time.
 */

async function handleUserActivity() {
    const now = Date.now();

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

/**
 * Attach event listeners for user activity and page visibility to trigger activity handling.
 *
 * Registers handlers for load, mousedown, click, keydown, touchstart, and scroll (using the capture phase)
 * and treats the page becoming visible again as activity by invoking handleUserActivity on visibility changes.
 */
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

// Initialize WebSocket connection for token refresh notifications
let wsSocket = null;
let intentionalDisconnect = false;
let retryAttempts = 0;
const maxRetryAttempts = 10;
const baseDelay = 1000; // 1 second base delay
let retryTimer = null;

/**
 * Establishes a single WebSocket connection to receive server-driven token notifications.
 *
 * When a connection is already opening or open, the function returns without creating a new socket.
 * Listens for messages of type "refresh_tokens" with message "REFRESH" to invoke refreshTokenFromServer,
 * and with message "LOGOUT" to invoke logoutAndRedirect. On open, it resets retry state and clears any pending retry timer.
 * If the connection closes unintentionally, it attempts reconnection using exponential backoff up to maxRetryAttempts (with a capped delay); intentional closes do not trigger reconnection.
 */
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

/**
 * Close the active WebSocket connection, prevent automatic reconnection attempts, and clear any pending retry timer.
 *
 * If no WebSocket is present, the function is a no-op.
 */
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

/**
 * Perform a user logout flow: close the WebSocket, attempt a CSRF-protected server logout, and navigate to the login page.
 *
 * Attempts to POST to the server logout endpoint with credentials and a CSRF token; logs any errors but always redirects the browser to /login/ after the attempt.
 */
async function logoutAndRedirect() {
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
        // Redirect to login page regardless of logout API result
        window.location.href = '/login/';
    }
}

// Function to call the cookie refresh endpoint
let refreshPromise = null; // Promise to deduplicate concurrent refresh attempts
let retryCount = 0;
const maxRetries = 5; /**
 * Refreshes authentication tokens by calling the server cookie-refresh endpoint and returns the server response.
 *
 * Deduplicates concurrent refresh attempts by returning the same in-flight promise, retries on transient failures
 * with exponential backoff and random jitter, and triggers logoutAndRedirect on persistent failures or on 401/403 responses.
 * @returns {Promise<import("axios").AxiosResponse|undefined>} The axios response when refresh succeeds; `undefined` if the refresh failed or logout was triggered.
 */

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

            // Check if we've reached the max retry attempts
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
        } finally {
            // Clear the refresh promise when the operation completes (either success or failure)
            refreshPromise = null;
        }
    };

    // Store the promise to prevent concurrent executions
    refreshPromise = executeRefresh();
    return refreshPromise;
}

/**
 * Configure Axios to handle authentication failures by redirecting users to the login page.
 *
 * Installs a global Axios response interceptor that invokes logoutAndRedirect when a response
 * indicates an authentication error (HTTP 401 or 403). Successful responses are returned
 * unchanged and other errors are propagated to the caller.
 */
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