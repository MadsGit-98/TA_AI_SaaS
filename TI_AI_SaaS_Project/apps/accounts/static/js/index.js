// Homepage logout functionality

/**
 * Retrieve the CSRF token from the meta tag named "csrf-token".
 * @returns {string|undefined} The token string from the meta tag, or `undefined` if the meta tag is not present.
 */
function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
}

// Set up logout event listener
document.addEventListener('DOMContentLoaded', function() {
    const logoutLink = document.getElementById('logout-link');
    if (logoutLink) {
        logoutLink.addEventListener('click', async function(e) {
            e.preventDefault();

            // Get CSRF token with null check
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
            
            try {
                const response = await fetch('/api/accounts/auth/logout/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin'  // Include cookies in request
                });

                if (response.status === 204) {
                    // Redirect to home page after successful logout
                    window.location.href = '/';
                } else {
                    console.error('Logout failed');
                    // Even if there's an error, redirect to home page
                    window.location.href = '/';
                }
            } catch (error) {
                console.error('Error during logout:', error);
                // Even if there's an error, redirect to home page
                window.location.href = '/';
            }
        });
    }
});