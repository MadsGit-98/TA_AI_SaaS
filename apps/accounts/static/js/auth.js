// auth.js - Authentication functionality for X-Crewter (Cookie-based JWT)

// Token functions are no longer needed since tokens are stored in HttpOnly cookies
// The browser handles token storage and inclusion automatically
function getToken(tokenName) {
    // Tokens are now stored in HttpOnly cookies, not in localStorage/sessionStorage
    // This function is kept for compatibility but returns null
    return null;
}

// Token functions are no longer needed since tokens are stored in HttpOnly cookies
function setToken(tokenName, tokenValue, isPersistent) {
    // Tokens are now stored in HttpOnly cookies via server response
    // This function is kept for compatibility but does nothing
    console.warn("Tokens are now stored in HttpOnly cookies. Use server endpoints to manage tokens.");
}

// Token functions are no longer needed since tokens are stored in HttpOnly cookies
function removeToken(tokenName) {
    // Tokens are now stored in HttpOnly cookies, clearing is handled by logout
    // This function is kept for compatibility but does nothing
    console.warn("Tokens are stored in HttpOnly cookies. Use logout endpoint to clear tokens.");
}

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

document.addEventListener('DOMContentLoaded', function() {
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
    
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    // Password reset request form
    const passwordResetForm = document.getElementById('password-reset-form');
    if (passwordResetForm) {
        passwordResetForm.addEventListener('submit', handlePasswordReset);
    }
});

async function handleRegister(e) {
    e.preventDefault();
    
    const submitBtn = document.getElementById('submit-btn');
    const successMessage = document.getElementById('success-message');
    const errorMessage = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    
    // Get form data
    const formData = {
        first_name: document.getElementById('first-name').value,
        last_name: document.getElementById('last-name').value,
        email: document.getElementById('email').value,
        username: document.getElementById('email').value, // Use email as username
        password: document.getElementById('password').value,
        password_confirm: document.getElementById('confirm-password').value
    };
    
    // Show loading state
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="absolute left-0 inset-y-0 flex items-center pl-3"><svg class="h-5 w-5 text-cta-text group-hover:text-cta-text animate-spin" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clip-rule="evenodd" /></svg></span> Registering...';
    
    try {
        const response = await fetch('/api/accounts/auth/register/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            credentials: 'include',  // Include cookies in request
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Show success message
            document.getElementById('registration-form-container').style.display = 'none';
            successMessage.classList.remove('hidden');

            // Redirect to login page after a short delay to show success message
            setTimeout(() => {
                window.location.href = '/login/';
            }, 1500); // Wait 1.5 seconds before redirecting
        } else {
            // Show error message
            let errorMsg = 'Registration failed';
            if (data.email) {
                errorMsg = data.email[0];
            } else if (data.password) {
                errorMsg = data.password[0];
            } else if (data.non_field_errors) {
                errorMsg = data.non_field_errors[0];
            } else if (typeof data === 'string') {
                errorMsg = data;
            }
            
            errorText.textContent = errorMsg;
            errorMessage.classList.remove('hidden');
        }
    } catch (error) {
        errorText.textContent = 'An error occurred. Please try again.';
        errorMessage.classList.remove('hidden');
    } finally {
        // Reset button state
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span class="absolute left-0 inset-y-0 flex items-center pl-3"><svg class="h-5 w-5 text-cta-text group-hover:text-cta-text" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clip-rule="evenodd" /></svg></span> Sign up';
    }
}

async function handleLogin(e) {
    e.preventDefault();

    const submitBtn = document.getElementById('login-submit-btn');
    const errorMessage = document.getElementById('login-error-message');
    const errorText = document.getElementById('login-error-text');

    // Get form data
    const formData = {
        username: document.getElementById('login-email').value,  // Backend expects 'username' field which handles both username and email
        password: document.getElementById('login-password').value
    };

    // Get remember me setting
    const rememberMeCheckbox = document.getElementById('remember-me');
    const rememberMe = rememberMeCheckbox ? rememberMeCheckbox.checked : false;

    // Show loading state
    submitBtn.disabled = true;
    submitBtn.textContent = 'Logging in...';

    try {
        const response = await fetch('/api/accounts/auth/login/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            credentials: 'include',  // Include cookies in request
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            // Tokens are now stored in HttpOnly cookies, no need to store them in JS
            // The server sets the tokens in cookies automatically

            // Use server-provided redirect URL for navigation
            if (data.redirect_url && typeof data.redirect_url === 'string' && data.redirect_url.length > 0) {
                // Validate that the redirect URL is one of the allowed destinations for security
                const allowedRedirects = ['/dashboard/', '/landing/', '/'];
                if (allowedRedirects.includes(data.redirect_url)) {
                    window.location.href = data.redirect_url;
                } else {
                    // If the redirect URL is not in the whitelist, default to a safe page
                    console.warn('Invalid redirect URL received from server:', data.redirect_url);
                    window.location.href = '/landing/';
                }
            } else {
                // If no redirect URL provided by server, default to landing page and log issue
                console.warn('No redirect URL provided by server. Using default redirect.');
                window.location.href = '/landing/';
            }
        } else {
            // Show error message
            let errorMsg = 'Login failed';
            if (data.non_field_errors) {
                errorMsg = data.non_field_errors[0];
            } else if (typeof data === 'string') {
                errorMsg = data;
            }

            errorText.textContent = errorMsg;
            errorMessage.classList.remove('hidden');
        }
    } catch (error) {
        errorText.textContent = 'An error occurred. Please try again.';
        errorMessage.classList.remove('hidden');
    } finally {
        // Reset button state
        submitBtn.disabled = false;
        submitBtn.textContent = 'Sign in';
    }
}

async function handlePasswordReset(e) {
    e.preventDefault();
    
    const submitBtn = document.getElementById('password-reset-submit-btn');
    const successMessage = document.getElementById('password-reset-success-message');
    const errorMessage = document.getElementById('password-reset-error-message');
    const errorText = document.getElementById('password-reset-error-text');
    
    // Get form data
    const formData = {
        email: document.getElementById('reset-email').value
    };
    
    // Show loading state
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending...';
    
    try {
        const response = await fetch('/api/accounts/auth/password/reset/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            credentials: 'include',  // Include cookies in request
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Show success message
            successMessage.classList.remove('hidden');
            document.getElementById('password-reset-form').style.display = 'none';
        } else {
            // Show error message
            let errorMsg = 'Password reset request failed';
            if (data.email) {
                errorMsg = data.email[0];
            } else if (typeof data === 'string') {
                errorMsg = data;
            }
            
            errorText.textContent = errorMsg;
            errorMessage.classList.remove('hidden');
        }
    } catch (error) {
        errorText.textContent = 'An error occurred. Please try again.';
        errorMessage.classList.remove('hidden');
    } finally {
        // Reset button state
        submitBtn.disabled = false;
        submitBtn.textContent = 'Send Reset Link';
    }
}

// Check if tokens are about to expire and refresh them automatically
async function checkAndRefreshToken() {
    try {
        // Make a request to the user profile endpoint which will update activity
        // and potentially trigger server-side refresh if needed
        const response = await fetch('/api/accounts/auth/users/me/', {
            method: 'GET',
            credentials: 'include', // Important: include cookies in requests
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            }
        });

        if (response.status === 401) {
            // Token expired, redirect to login
            window.location.href = '/login/';
            return false;
        }

        return response.ok;
    } catch (error) {
        console.error('Error checking token status:', error);
        // On error, redirect to login
        window.location.href = '/login/';
        return false;
    }
}

// Set up automatic token refresh before expiration
function setupTokenRefresh() {
    // Refresh token automatically before it expires (checking every 20 minutes)
    // This ensures the user remains active and tokens are refreshed before expiration
    setInterval(() => {
        checkAndRefreshToken();
    }, 20 * 60 * 1000); // Check every 20 minutes
}

// Initialize auth functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }

    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    // Password reset request form
    const passwordResetForm = document.getElementById('password-reset-form');
    if (passwordResetForm) {
        passwordResetForm.addEventListener('submit', handlePasswordReset);
    }

    // Set up token refresh if user appears to be authenticated
    // Check for the presence of authentication cookies
    if (document.cookie.includes('access_token')) {
        setupTokenRefresh();
    }

    // Add response interceptor to handle 401s globally for API calls
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        return originalFetch.apply(this, args).then(response => {
            if (response.status === 401) {
                // If unauthorized, redirect to login
                window.location.href = '/login/';
            }
            return response;
        });
    };
});