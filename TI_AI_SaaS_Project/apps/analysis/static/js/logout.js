/**
 * Logout functionality for analysis pages
 * Handles logout button click and redirects to home page
 */

(function() {
    'use strict';

    /**
     * Retrieve the CSRF token stored in the page's meta[name="csrf-token"] element.
     * @returns {string|null} The token string if the meta tag exists, otherwise null.
     */
    function getCsrfToken() {
        const tokenMeta = document.querySelector('meta[name="csrf-token"]');
        return tokenMeta ? tokenMeta.getAttribute('content') : null;
    }

    /**
     * Attaches a click handler to the element with id "logout-link" that sends a logout POST using the page CSRF token and redirects the user to the home page.
     *
     * If the element is not present, no action is taken.
     */
    function initLogout() {
        const logoutLink = document.getElementById('logout-link');
        if (logoutLink) {
            logoutLink.addEventListener('click', async function(e) {
                e.preventDefault();

                try {
                    const response = await fetch('/api/accounts/auth/logout/', {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCsrfToken(),
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
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLogout);
    } else {
        initLogout();
    }

})();
