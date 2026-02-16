/**
 * Escape HTML special characters in a value for safe insertion into the DOM.
 * @param {*} text - Value to escape; null or undefined is treated as an empty string and all inputs are coerced to a string.
 * @returns {string} The input converted to a string with `&`, `<`, `>`, `"` and `'` replaced by their corresponding HTML entities.
 */
function escapeHtml(text) {
    // Coerce input to string, handling null/undefined safely
    text = String(text == null ? '' : text);

    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Display an error message in the dashboard UI by setting the text of the element with id "job-error-text" and revealing the "job-error-message" element for 5 seconds.
 * @param {string} message - The message to show to the user.
 */
function showError(message) {
    const errorMessage = document.getElementById('job-error-message');
    const errorText = document.getElementById('job-error-text');
    if (errorMessage && errorText) {
        errorText.textContent = message;
        errorMessage.classList.remove('hidden');
        setTimeout(() => {
            errorMessage.classList.add('hidden');
        }, 5000);
    }
}

/**
 * Displays a transient success message in the dashboard UI.
 *
 * Sets the text of the element with id "job-success-text", reveals the container
 * with id "job-success-message", and hides it again after 3 seconds.
 *
 * @param {string} message - The message text to show to the user.
 */
function showSuccess(message) {
    const successMessage = document.getElementById('job-success-message');
    const successText = document.getElementById('job-success-text');
    if (successMessage && successText) {
        successText.textContent = message;
        successMessage.classList.remove('hidden');
        setTimeout(() => {
            successMessage.classList.add('hidden');
        }, 3000);
    }
}

/**
 * Create and append a job listing card into the provided container element.
 *
 * The card displays the job title, a description truncated to 100 characters, tags for job level,
 * required experience, status, start/expiration dates, and action buttons for edit, copy application link,
 * activate/deactivate, and duplicate.
 *
 * @param {Object} job - Job data used to populate the card. Expected properties: `id`, `title`, `description`, `job_level`, `required_experience`, `status`, `start_date`, `expiration_date`, `application_link`.
 * @param {HTMLElement} container - DOM element to which the constructed job card will be appended.
 */
function createJobElement(job, container) {
    const jobElement = document.createElement('div');
    jobElement.className = 'border border-gray-200 rounded-lg p-4 bg-white';

    // Format dates
    const startDate = job.start_date ? new Date(job.start_date).toLocaleDateString() : 'Not set';
    const expirationDate = job.expiration_date ? new Date(job.expiration_date).toLocaleDateString() : 'Not set';

    // Create the content using safe DOM manipulation
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'flex justify-between items-start';

    // Left side content
    const leftSide = document.createElement('div');

    const titleElement = document.createElement('h2');
    titleElement.className = 'text-xl font-semibold';
    titleElement.textContent = job.title;
    leftSide.appendChild(titleElement);

    const descElement = document.createElement('p');
    descElement.className = 'text-gray-600';
    const desc = job.description || '';
    const descText = desc.length > 100 ?
        desc.substring(0, 100) + '...' :
        desc;
    descElement.textContent = descText;
    leftSide.appendChild(descElement);

    // Tags container
    const tagsContainer = document.createElement('div');
    tagsContainer.className = 'mt-2 flex flex-wrap gap-2';

    // Job level tag
    const levelTag = document.createElement('span');
    levelTag.className = 'inline-block bg-gray-200 rounded-full px-3 py-1 text-sm font-semibold text-gray-700';
    levelTag.textContent = job.job_level;
    tagsContainer.appendChild(levelTag);

    // Experience tag
    const expTag = document.createElement('span');
    expTag.className = 'inline-block bg-gray-200 rounded-full px-3 py-1 text-sm font-semibold text-gray-700';
    expTag.textContent = job.required_experience + ' yrs exp';
    tagsContainer.appendChild(expTag);

    // Status tag
    const statusTag = document.createElement('span');
    const statusClass = job.status === 'Active' ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800';
    statusTag.className = `inline-block ${statusClass} rounded-full px-3 py-1 text-sm font-semibold`;
    statusTag.textContent = job.status;
    tagsContainer.appendChild(statusTag);

    // Start date tag
    const startTag = document.createElement('span');
    startTag.className = 'inline-block bg-gray-200 rounded-full px-3 py-1 text-sm font-semibold text-gray-700';
    startTag.textContent = 'Starts: ' + startDate;
    tagsContainer.appendChild(startTag);

    // Expiration date tag
    const expDateTag = document.createElement('span');
    expDateTag.className = 'inline-block bg-gray-200 rounded-full px-3 py-1 text-sm font-semibold text-gray-700';
    expDateTag.textContent = 'Expires: ' + expirationDate;
    tagsContainer.appendChild(expDateTag);

    leftSide.appendChild(tagsContainer);

    // Right side buttons
    const rightSide = document.createElement('div');
    rightSide.className = 'flex flex-col space-y-2';

    // Edit button
    const editButton = document.createElement('button');
    editButton.className = 'text-blue-600 hover:text-blue-800 text-sm';
    editButton.textContent = 'Edit';
    editButton.addEventListener('click', () => editJob(job.id));
    rightSide.appendChild(editButton);

    // Copy link button
    const copyButton = document.createElement('button');
    copyButton.className = 'text-blue-600 hover:text-blue-800 text-sm';
    
    // Check if application link exists and is valid
    if (job.application_link && typeof job.application_link === 'string' && job.application_link.trim() !== '') {
        copyButton.textContent = 'Copy Link';
        copyButton.addEventListener('click', () => copyApplicationLink(job.application_link));
    } else {
        copyButton.textContent = 'No Link Available';
        copyButton.disabled = true;
        copyButton.classList.add('opacity-50', 'cursor-not-allowed');
    }
    rightSide.appendChild(copyButton);

    // Conditional status button - Status may be overridden by automatic checks
    let statusButton;
    if (job.status === 'Active') {
        statusButton = document.createElement('button');
        statusButton.className = 'text-red-600 hover:text-red-800 text-sm';
        statusButton.textContent = 'Deactivate';
        statusButton.addEventListener('click', () => deactivateJob(job.id));
    } else {
        statusButton = document.createElement('button');
        statusButton.className = 'text-green-600 hover:text-green-800 text-sm';
        statusButton.textContent = 'Activate';
        statusButton.addEventListener('click', () => activateJob(job.id));
    }
    // Add tooltip to indicate automatic status changes
    statusButton.title = 'Status may change automatically based on start/expiration dates';
    rightSide.appendChild(statusButton);

    // Duplicate button
    const duplicateButton = document.createElement('button');
    duplicateButton.className = 'text-purple-600 hover:text-purple-800 text-sm';
    duplicateButton.textContent = 'Duplicate';
    duplicateButton.addEventListener('click', () => duplicateJob(job.id));
    rightSide.appendChild(duplicateButton);

    // Assemble the content
    contentWrapper.appendChild(leftSide);
    contentWrapper.appendChild(rightSide);
    jobElement.appendChild(contentWrapper);

    container.appendChild(jobElement);
}

/**
 * Fetch and render job listings using current UI filters and pagination.
 *
 * Reads filter values from the page, requests the corresponding job data from the server, and updates the DOM
 * by populating the job listings container and pagination controls or showing an appropriate message on error or
 * empty results.
 * @param {number} [page=1] - Page number of job listings to load (1-based).
 */
async function loadJobListings(page = 1) {
    try {
        // Get filter values
        const statusFilter = document.getElementById('statusFilter').value;
        const dateRangeFilter = document.getElementById('dateRangeFilter').value;
        const jobLevelFilter = document.getElementById('jobLevelFilter').value;
        const searchFilter = document.getElementById('searchFilter').value;

        // Build query string
        let queryString = `?page=${page}`;
        if (statusFilter) queryString += `&status=${encodeURIComponent(statusFilter)}`;
        if (dateRangeFilter) queryString += `&date_range=${encodeURIComponent(dateRangeFilter)}`;
        if (jobLevelFilter) queryString += `&job_level=${encodeURIComponent(jobLevelFilter)}`;
        if (searchFilter) queryString += `&search=${encodeURIComponent(searchFilter)}`;

        const response = await fetch(`/dashboard/jobs/${queryString}`, {
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            const data = await response.json();
            const container = document.getElementById('jobListingsContainer');

            // Check if data has the expected structure with results array
            if (!data.hasOwnProperty('results')) {
                // If there's no 'results' property, check if it's a direct array or an error
                if (data.error || data.detail) {
                    // It's an error response
                    const errorElement = document.createElement('p');
                    errorElement.className = 'text-center text-red-500';
                    errorElement.textContent = `Error: ${data.error || data.detail}`;
                    container.innerHTML = ''; // Clear the container first
                    container.appendChild(errorElement);
                    document.getElementById('paginationContainer').innerHTML = '';
                    return;
                } else if (Array.isArray(data)) {
                    // It's a direct array of jobs (not paginated)
                    if (data.length === 0) {
                        const noJobsElement = document.createElement('p');
                        noJobsElement.className = 'text-center text-gray-500';
                        noJobsElement.textContent = 'No job listings found.';
                        container.innerHTML = ''; // Clear the container first
                        container.appendChild(noJobsElement);
                        document.getElementById('paginationContainer').innerHTML = '';
                        return;
                    }
                    
                    // Process the direct array
                    container.innerHTML = '';
                    data.forEach(job => {
                        createJobElement(job, container);
                    });
                    
                    // No pagination for non-paginated response
                    document.getElementById('paginationContainer').innerHTML = '';
                    return;
                } else {
                    // Unexpected response structure
                    console.error('Unexpected API response structure:', data);
                    const errorElement = document.createElement('p');
                    errorElement.className = 'text-center text-red-500';
                    errorElement.textContent = 'Unexpected API response structure.';
                    container.innerHTML = ''; // Clear the container first
                    container.appendChild(errorElement);
                    document.getElementById('paginationContainer').innerHTML = '';
                    return;
                }
            }

            // Process paginated response
            if (data.results.length === 0) {
                const noJobsElement = document.createElement('p');
                noJobsElement.className = 'text-center text-gray-500';
                noJobsElement.textContent = 'No job listings found.';
                container.innerHTML = ''; // Clear the container first
                container.appendChild(noJobsElement);
                document.getElementById('paginationContainer').innerHTML = '';
                return;
            }

            container.innerHTML = '';
            data.results.forEach(job => {
                createJobElement(job, container);
            });

            // Handle pagination
            renderPagination(data);
        } else {
            console.error('Failed to load job listings');
            const container = document.getElementById('jobListingsContainer');
            const errorElement = document.createElement('p');
            errorElement.className = 'text-center text-red-500';
            errorElement.textContent = 'Failed to load job listings. Please try again.';
            container.innerHTML = ''; // Clear the container first
            container.appendChild(errorElement);
        }
    } catch (error) {
        console.error('Error loading job listings:', error);
    }
}

/**
 * Render previous/next pagination controls into the element with id "paginationContainer".
 *
 * Renders "Previous" and/or "Next" buttons when the provided pagination object contains
 * `previous` and/or `next` URL values, clears existing pagination content before rendering,
 * and wires each button to load the corresponding page using getPageNumberFromUrl and loadJobListings.
 *
 * @param {Object} data - Pagination metadata from the API response.
 * @param {string|null} data.next - URL for the next page, or null if none.
 * @param {string|null} data.previous - URL for the previous page, or null if none.
 */
function renderPagination(data) {
    const container = document.getElementById('paginationContainer');
    container.innerHTML = '';

    if (!data.next && !data.previous) return; // No pagination needed

    const paginationDiv = document.createElement('div');
    paginationDiv.className = 'flex items-center space-x-2';

    // Previous button
    if (data.previous) {
        const prevButton = document.createElement('button');
        prevButton.textContent = 'Previous';
        prevButton.className = 'px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50';
        prevButton.onclick = () => loadJobListings(getPageNumberFromUrl(data.previous));
        paginationDiv.appendChild(prevButton);
    }

    // Next button
    if (data.next) {
        const nextButton = document.createElement('button');
        nextButton.textContent = 'Next';
        nextButton.className = 'px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 ml-2';
        nextButton.onclick = () => loadJobListings(getPageNumberFromUrl(data.next));
        paginationDiv.appendChild(nextButton);
    }

    container.appendChild(paginationDiv);
}

/**
 * Extract the numeric `page` query parameter from a URL string, returning 1 if missing or invalid.
 * @param {string} url - URL or query-containing string to read the `page` parameter from.
 * @returns {number} The page number parsed from `page` query parameter, or `1` when not present or not a valid number.
 */
function getPageNumberFromUrl(url) {
    // Check if URL is a non-empty string
    if (!url || typeof url !== 'string' || url.trim() === '') {
        return 1;
    }

    // Extract query string part after '?'
    const urlParts = url.split('?');
    if (urlParts.length < 2) {
        return 1;
    }

    const urlParams = new URLSearchParams(urlParts[1]);
    const pageParam = urlParams.get('page');

    // Parse the page parameter to number, fallback to 1 if parsing fails
    const pageNumber = parseInt(pageParam, 10);
    return isNaN(pageNumber) ? 1 : pageNumber;
}

/**
 * Retrieve the CSRF token value from the page's meta[name="csrf-token"] tag.
 * @returns {string|null} The CSRF token string, or `null` if the meta tag is not present.
 */
function getCsrfToken() {
    const tokenMeta = document.querySelector('meta[name="csrf-token"]');
    return tokenMeta ? tokenMeta.getAttribute('content') : null;
}

/**
 * Retrieve the value of a named cookie from document.cookie.
 * @param {string} name - The cookie name to look up.
 * @returns {string|null} The decoded cookie value if found, or `null` if not present.
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Navigate the browser to the edit page for the specified job.
 * @param {string|number} jobId - Job identifier used to construct the edit URL.
 */
function editJob(jobId) {
    window.location.href = `/dashboard/${jobId}/edit/`;
}

/**
 * Activate a job via the dashboard API after confirming with the user.
 *
 * Prompts the user for confirmation, sends a POST request to activate the specified job,
 * displays a success or error message based on the response, and refreshes the job listings on success.
 * @param {string|number} jobId - The identifier of the job to activate.
 */
async function activateJob(jobId) {
    if (!confirm('Are you sure you want to activate this job?')) return;

    try {
        const response = await fetch(`/dashboard/jobs/${jobId}/activate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            showSuccess('Job activated successfully!');
            loadJobListings(); // Refresh the list
        } else {
            const errorData = await response.json();
            showError(`Error activating job: ${JSON.stringify(errorData)}`);
        }
    } catch (error) {
        console.error('Error activating job:', error);
        showError('An error occurred while activating the job.');
    }
}

/**
 * Deactivate a job after user confirmation by calling the dashboard deactivate endpoint; shows UI feedback and refreshes the job listings on success.
 * @param {number|string} jobId - ID of the job to deactivate.
 */
async function deactivateJob(jobId) {
    if (!confirm('Are you sure you want to deactivate this job?')) return;

    try {
        const response = await fetch(`/dashboard/jobs/${jobId}/deactivate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            showSuccess('Job deactivated successfully!');
            loadJobListings(); // Refresh the list
        } else {
            const errorData = await response.json();
            showError(`Error deactivating job: ${JSON.stringify(errorData)}`);
        }
    } catch (error) {
        console.error('Error deactivating job:', error);
        showError('An error occurred while deactivating the job.');
    }
}

/**
 * Duplicate an existing job; on success shows a confirmation and navigates to the new job's edit page.
 *
 * Prompts the user for confirmation, attempts to create a duplicate via the server, displays success or error feedback,
 * and when the server returns a valid new job id, redirects to that job's edit screen. If duplication succeeds but
 * the response lacks a usable id, a success message is shown without redirection.
 * 
 * @param {number|string} jobId - The id of the job to duplicate.
 */
async function duplicateJob(jobId) {
    if (!confirm('Are you sure you want to duplicate this job?')) return;

    try {
        const response = await fetch(`/dashboard/jobs/${jobId}/duplicate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            const result = await response.json();
            if (result && (typeof result.id === 'number' || (typeof result.id === 'string' && result.id.trim() !== ''))) {
                showSuccess('Job duplicated successfully!');
                setTimeout(() => {
                    window.location.href = `/dashboard/${result.id}/edit/`; // Redirect to edit the new job
                }, 1500);
            } else {
                console.error('Invalid or missing ID in duplication response:', result);
                showSuccess('Job duplicated successfully but failed to redirect. Please refresh the page to see the new job.');
            }
        } else {
            const errorData = await response.json();
            showError(`Error duplicating job: ${JSON.stringify(errorData)}`);
        }
    } catch (error) {
        console.error('Error duplicating job:', error);
        showError('An error occurred while duplicating the job.');
    }
}

/**
 * Copy the full application URL (current origin + `/apply/` + provided link) to the clipboard and show a success or error message.
 * @param {string} link - Application path segment or identifier to append to `/apply/` (e.g., job slug or id).
 */
function copyApplicationLink(link) {
    const fullLink = `${window.location.origin}/apply/${link}`;
    navigator.clipboard.writeText(fullLink)
        .then(() => {
            showSuccess('Application link copied to clipboard!');
        })
        .catch(err => {
            console.error('Failed to copy link: ', err);
            showError('Failed to copy link to clipboard.');
        });
}

// Set up filter event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('statusFilter').addEventListener('change', () => loadJobListings());
    document.getElementById('dateRangeFilter').addEventListener('change', () => loadJobListings());
    document.getElementById('jobLevelFilter').addEventListener('change', () => loadJobListings());
    document.getElementById('searchFilter').addEventListener('input', () => {
        // Debounce the search
        clearTimeout(window.searchTimeout);
        window.searchTimeout = setTimeout(() => loadJobListings(), 500);
    });

    // Set up logout event listener
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

    // Load job listings when page loads
    loadJobListings();
});