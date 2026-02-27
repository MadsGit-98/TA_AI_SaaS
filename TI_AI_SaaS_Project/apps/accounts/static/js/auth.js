// auth.js - Authentication functionality for X-Crewter (Cookie-based JWT)
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

    // Check if we're on the login page and show inactivity message if needed
    const loginFormContainer = document.getElementById('login-form-container');
    if (loginFormContainer) {
        // Check URL parameters to show inactivity message if needed
        const urlParams = new URLSearchParams(window.location.search);
        const reason = urlParams.get('reason');

        if (reason === 'inactive') {
            // Show the inactivity message
            const inactivityMessage = document.getElementById('login-inactivity-message');
            const errorMessage = document.getElementById('login-error-message');

            // Hide the regular error message if it's visible
            if (errorMessage) {
                errorMessage.classList.add('hidden');
            }

            // Show the inactivity message if it exists
            if (inactivityMessage) {
                inactivityMessage.classList.remove('hidden');
            }
        }
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

/**
 * Handle login form submission by sending credentials (including a remember_me flag) to the authentication API, applying the server response (navigate on success, show error messages on failure).
 *
 * On success, if a global `window.setRememberMeStatus` function exists it will be called with the remember-me value; navigation will use a server-provided whitelisted redirect URL or fall back to `/landing/`. On failure, the server-provided error or a generic message is displayed.
 *
 * @param {Event} e - Submit event from the login form.
 */
async function handleLogin(e) {
    e.preventDefault();

    const submitBtn = document.getElementById('login-submit-btn');
    const errorMessage = document.getElementById('login-error-message');
    const errorText = document.getElementById('login-error-text');

    // Get remember me setting
    const rememberMeCheckbox = document.getElementById('remember-me');
    const rememberMe = rememberMeCheckbox ? rememberMeCheckbox.checked : false;

    // Get form data
    const formData = {
        username: document.getElementById('login-email').value,  // Backend expects 'username' field which handles both username and email
        password: document.getElementById('login-password').value,
        remember_me: rememberMe  // Include remember_me flag in form data
    };

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

            // Set the remember me status in the auth interceptor if it exists
            if (typeof window.setRememberMeStatus === 'function') {
                window.setRememberMeStatus(rememberMe);
            }

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
