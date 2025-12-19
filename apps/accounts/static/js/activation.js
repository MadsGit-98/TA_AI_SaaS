// Handle activation by making a direct fetch request
document.addEventListener('DOMContentLoaded', function() {
    const activationForm = document.getElementById('activationForm');
    if (activationForm) {
        // Extract CSRF token and form action URL
        const csrfTokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
        if (!csrfTokenElement) {
            console.error('CSRF token element not found on the page');
            // If CSRF token is not found, redirect to the activation error page
            window.location.replace('/activation-error');
            return; // Stop execution
        }
        const csrfToken = csrfTokenElement.value;
        const activationUrl = activationForm.action;

        // Make a direct fetch request to the activation API
        fetch(activationUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json',
                'Accept': 'application/json',  // Force JSON response
            },
        })
        .then(response => {
            
            if (!response.ok) {
                console.error('HTTP error occurred:', response.status);
                // Try to read error response as text to see what's happening
                return response.text().then(text => {
                    console.error('Error response text:', text);
                    throw new Error(`HTTP error! Status: ${response.status}`);
                });
            }
            
            // Check if the content type is JSON before parsing
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return response.json();
            } else {
                // If not JSON, log what was returned and throw an error
                return response.text().then(text => {
                    console.error('Non-JSON response received:', text);
                    throw new Error('Non-JSON response received from server');
                });
            }
        })
        .then(data => {
            if (data.redirect_url) {
                // Use replace to ensure clean redirect
                window.location.replace(data.redirect_url);
            } else {
                console.warn('No redirect URL in response, redirecting to homepage');
                window.location.replace('/');
            }
        })
        .catch(error => {
            console.error('Error during activation:', error);
            // In case of error, redirect to the activation error page
            window.location.replace('/activation-error');
        });
    } else {
        console.error('Activation form not found on the page');
        // If form is not found, redirect to the activation error page
        window.location.replace('/activation-error');
    }
});