/**
 * Logout functionality for bulk upload page
 * Handles logout button click and redirects to home page
 */

(function() {
    'use strict';

    /**
     * Helper function to get CSRF token from meta tag
     * @returns {string|null} CSRF token
     */
    function getCsrfToken() {
        const tokenMeta = document.querySelector('meta[name="csrf-token"]');
        return tokenMeta ? tokenMeta.getAttribute('content') : null;
    }

    /**
     * Initialize logout functionality
     */
    function initLogout() {
        const logoutLink = document.getElementById('logout-link');
        if (logoutLink) {
            logoutLink.addEventListener('click', async function(e) {
                e.preventDefault();

                // Get CSRF token first
                const csrfToken = getCsrfToken();
                
                // Build headers object - only add X-CSRFToken if token exists
                const headers = {};
                
                if (csrfToken) {
                    headers['X-CSRFToken'] = csrfToken;
                } else {
                    console.warn('CSRF token not found - logout request may fail');
                }

                try {
                    const response = await fetch('/api/accounts/auth/logout/', {
                        method: 'POST',
                        headers: headers,
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
