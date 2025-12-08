// auth.js - Authentication functionality for X-Crewter

// Unified function to get token from either localStorage or sessionStorage
function getToken(tokenName) {
    // Try localStorage first, then sessionStorage
    return localStorage.getItem(tokenName) || sessionStorage.getItem(tokenName);
}

// Unified function to set token
function setToken(tokenName, tokenValue, isPersistent) {
    if (isPersistent) {
        localStorage.setItem(tokenName, tokenValue);
    } else {
        sessionStorage.setItem(tokenName, tokenValue);
    }
}

// Unified function to remove token
function removeToken(tokenName) {
    localStorage.removeItem(tokenName);
    sessionStorage.removeItem(tokenName);
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
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Show success message
            document.getElementById('registration-form-container').style.display = 'none';
            successMessage.classList.remove('hidden');
            
            // Optionally redirect after a delay or let user click a link to login
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
        email: document.getElementById('login-email').value,
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
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            // Store tokens based on remember me setting
            setToken('access_token', data.access, rememberMe);
            setToken('refresh_token', data.refresh, rememberMe);

            // Redirect to dashboard or previous page
            window.location.href = '/dashboard/'; // or wherever the user should go
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
        email: document.getElementById('password-reset-email').value
    };
    
    // Show loading state
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending...';
    
    try {
        const response = await fetch('/api/accounts/auth/password/reset/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
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