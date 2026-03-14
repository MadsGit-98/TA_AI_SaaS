// Helper function to escape HTML
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

// Helper function to show error message
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

// Helper function to show success message
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
 * Create a styled job card DOM element from a job object and append it to the provided container.
 *
 * The card includes title, truncated description, tags for level, experience, status, start/expiration dates,
 * optional AI analysis progress or completion tags, and a column of action buttons for editing, copying the
 * application link, toggling status, and initiating/controlling AI analysis. Buttons are wired to existing
 * global handlers and the element is appended to the given container.
 *
 * @param {Object} job - Job data used to populate the card. Expected properties: `id`, `title`, `description`,
 *   `start_date`, `expiration_date`, `job_level`, `required_experience`, `status`, `application_link`,
 *   `analysis_in_progress`, `analysis_complete`, `progress_percentage`, `applicant_count`.
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

    // AI Analysis In Progress tag (if analysis is running)
    if (job.analysis_in_progress) {
        const progressTag = document.createElement('span');
        progressTag.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 bg-yellow-50 border-l-[3px] border-yellow-400 rounded font-mono text-xs font-semibold text-gray-900 shadow-sm';
        progressTag.title = 'AI Analysis in Progress';
        progressTag.setAttribute('data-job-id', job.id);
        progressTag.setAttribute('data-progress-type', 'in-progress');
        const progressPercent = job.progress_percentage || 0;
        progressTag.innerHTML = '<span class="inline-flex items-center justify-center w-4 h-4 text-yellow-600 animate-spin" aria-label="Loading">⟳</span>' +
            '<span class="text-gray-900 tracking-wide uppercase">Analyzing... ' + progressPercent + '%</span>';
        tagsContainer.appendChild(progressTag);
    }
    // AI Analysis Done tag (if analysis is complete)
    else if (job.analysis_complete) {
        const doneTag = document.createElement('span');
        doneTag.className = 'inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-200 border-l-[3px] border-[#00ff00] rounded font-mono text-xs font-semibold text-gray-900 shadow-sm';
        doneTag.title = 'AI Analysis Complete';
        doneTag.innerHTML = '<span class="inline-flex items-center justify-center w-4 h-4 bg-[#00ff00] text-gray-900 rounded-full text-[10px] font-bold">✓</span>' +
            '<span class="text-gray-900 tracking-wide uppercase">Analysis Done</span>';
        tagsContainer.appendChild(doneTag);
    }

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

    // AI Analysis button
    const analysisButton = document.createElement('button');
    analysisButton.className = 'text-indigo-600 hover:text-indigo-800 text-sm font-medium';

    // Check if analysis is in progress
    if (job.analysis_in_progress) {
        // Check if this job is being cancelled
        const isCancelling = cancellingJobs.has(job.id);
        
        // Show Cancel Analysis button when analysis is running
        analysisButton.textContent = 'Cancel Analysis';
        analysisButton.title = 'Cancel the running analysis';
        
        if (isCancelling) {
            // Disable button when cancelling
            analysisButton.disabled = true;
            analysisButton.classList.add('opacity-50', 'cursor-not-allowed');
            analysisButton.className = 'text-gray-400 text-sm font-medium cursor-not-allowed';
        } else {
            // Normal cancel button
            analysisButton.className = 'text-red-600 hover:text-red-800 text-sm font-medium';
            analysisButton.addEventListener('click', () => cancelAnalysis(job.id));
        }
    }
    // Check if analysis is already complete
    else if (job.analysis_complete) {
        analysisButton.textContent = 'View Analysis';
        analysisButton.addEventListener('click', () => viewAnalysis(job.id));
    } else {
        // Check if there are applicants to analyze
        const hasApplicants = job.applicant_count && job.applicant_count > 0;
        if (hasApplicants) {
            analysisButton.textContent = 'AI Analysis';
            analysisButton.title = `Initiate AI analysis for ${job.applicant_count} applicants`;
            analysisButton.addEventListener('click', () => initiateAnalysis(job.id));
        } else {
            analysisButton.textContent = 'No Applicants';
            analysisButton.disabled = true;
            analysisButton.classList.add('opacity-50', 'cursor-not-allowed');
            analysisButton.title = 'No applicants to analyze yet';
        }
    }
    rightSide.appendChild(analysisButton);

    // Assemble the content
    contentWrapper.appendChild(leftSide);
    contentWrapper.appendChild(rightSide);
    jobElement.appendChild(contentWrapper);

    container.appendChild(jobElement);
}

// Load job listings
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

// Render pagination controls
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

// Helper to extract page number from URL
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

// Helper function to get CSRF token from meta tag
function getCsrfToken() {
    const tokenMeta = document.querySelector('meta[name="csrf-token"]');
    return tokenMeta ? tokenMeta.getAttribute('content') : null;
}

// Helper function to get cookie value
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

// Job management functions
function editJob(jobId) {
    window.location.href = `/dashboard/${jobId}/edit/`;
}

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
 * Prompt the user to confirm and, if confirmed, deactivate the specified job on the server.
 *
 * Sends a POST request to the job deactivation endpoint, shows a success message and refreshes
 * the job list when the server responds with success, or shows an error message when it fails.
 *
 * @param {number|string} jobId - The identifier of the job to deactivate.
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
 * Copy the full application URL for a job to the user's clipboard.
 *
 * Builds an application URL from the current page origin and the provided path fragment, writes it to the clipboard, displays a success message on success, and displays an error message and logs to the console on failure.
 * @param {string} link - The application path or identifier to append after "/apply/" (e.g., "12345" or "job-slug").
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

/**
 * Initiates AI analysis for a job's applicants after user confirmation.
 *
 * Prompts the user to confirm initiation, requests the backend to start analysis,
 * and provides user feedback. On success, displays the number of applicants and
 * estimated duration, begins progress tracking for the job, and refreshes the
 * job listings to reflect the analysis state. On failure, displays an error message.
 *
 * @param {(number|string)} jobId - The identifier of the job to analyze.
 */
async function initiateAnalysis(jobId) {
    if (!confirm('Are you sure you want to initiate AI analysis for all applicants? This process may take several minutes depending on the number of applicants.')) return;

    try {
        const response = await fetch(`/api/analysis/jobs/${jobId}/analysis/initiate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'include'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Defensive check: ensure data.data exists before accessing properties
            if (!data.data) {
                console.error('API response missing data.data:', data);
                showError('Analysis started but response data is incomplete.');
                return;
            }
            const applicantCount = data.data.applicant_count;
            const estimatedMinutes = Math.ceil(data.data.estimated_duration_seconds / 60);
            showSuccess(`AI analysis started for ${applicantCount} applicants. Estimated time: ~${estimatedMinutes} minute(s).`);

            // Start progress tracking for this job
            startProgressTracking(jobId);

            // Refresh job list to show "Analyzing..." tag
            setTimeout(() => {
                loadJobListings();
            }, 500);
        } else {
            const errorMessage = data.error ? data.error.message : 'Failed to initiate analysis';
            showError(`Error: ${errorMessage}`);
        }
    } catch (error) {
        console.error('Error initiating analysis:', error);
        showError('An error occurred while initiating AI analysis.');
    }
}

/**
 * Request cancellation of a job's AI analysis and update the UI to reflect the cancelling state.
 *
 * Prompts the user for confirmation, marks the job as cancelling for immediate UI feedback, and sends a POST
 * to the cancellation endpoint with CSRF and credentials. On a successful request shows a brief success message
 * and relies on background polling to update final state. On failure or network error removes the cancelling flag,
 * shows an error message, and reloads the page to restore normal state.
 *
 * @param {string} jobId - ID of the job whose analysis should be cancelled.
 */
async function cancelAnalysis(jobId) {
    // Prevent multiple cancellation requests
    if (cancellingJobs.has(jobId)) {
        console.log('Already cancelling job', jobId);
        return;
    }
    
    if (!confirm('Are you sure you want to cancel the analysis? Results for already processed applicants will be preserved.')) return;

    try {
        // Mark as cancelling immediately for UI feedback
        markJobAsCancelling(jobId);

        const response = await fetch(`/api/analysis/jobs/${jobId}/analysis/cancel/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'include'
        });

        const data = await response.json();

        if (response.ok && data.success) {
            console.log('Cancellation requested for job', jobId);
            // Don't reload here - the polling will detect when task finishes and reload automatically
            // Just show a brief success message
            showSuccess(data.data.message || 'Analysis cancellation requested.');
        } else {
            const errorMessage = data.error ? data.error.message : 'Failed to cancel analysis';
            showError(`Error: ${errorMessage}`);
            // Remove from cancelling set on error
            cancellingJobs.delete(jobId);
            // Reload to restore normal state
            window.location.reload();
        }
    } catch (error) {
        console.error('Error cancelling analysis:', error);
        showError('An error occurred while cancelling analysis.');
        // Remove from cancelling set on error
        cancellingJobs.delete(jobId);
        // Reload to restore normal state
        window.location.reload();
    }
}

/**
 * Navigate the browser to the AI analysis reporting page for a specific job.
 * @param {number|string} jobId - The job identifier used to build the reporting URL.
 */
function viewAnalysis(jobId) {
    // Redirect to the analysis reporting page
    window.location.href = `/analysis/reporting/${jobId}/`;
}

/**
 * Fetches the AI analysis status for a job.
 * @param {number|string} jobId - The job identifier used in the status endpoint.
 * @returns {Object|null} The analysis status data returned by the API when available, or `null` if the request fails or the API response does not indicate success.
 */
async function checkAnalysisStatus(jobId) {
    try {
        const response = await fetch(`/api/analysis/jobs/${jobId}/analysis/status/`, {
            method: 'GET',
            credentials: 'include'
        });

        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                return data.data;
            }
        }
        return null;
    } catch (error) {
        console.error('Error checking analysis status:', error);
        return null;
    }
}

// =============================================================================
// Progress Tracking Functions
// =============================================================================

// Track jobs currently being analyzed (jobId -> intervalId mapping)
const analyzingJobs = new Map();

// Track jobs being cancelled (jobId -> {started: timestamp, lastStatus: string})
const cancellingJobs = new Map();

/**
 * Begin polling the server to monitor AI analysis progress for a job and update the UI accordingly.
 *
 * Sets up a 2-second polling interval that checks analysis status, updates the job's progress tag while processing,
 * handles a cancelling state (keeps showing "Cancelling..." until the server confirms cancellation), and stops
 * tracking then triggers a full page reload when the analysis completes, fails, or finishes cancelling.
 *
 * @param {string} jobId - The job identifier whose analysis progress should be tracked.
 */
function startProgressTracking(jobId) {
    // Check if already tracking this job
    if (analyzingJobs.has(jobId)) {
        console.log('Already tracking job', jobId);
        return;
    }

    console.log('Starting progress tracking for job', jobId);

    const intervalId = setInterval(async () => {
        try {
            console.log('Polling status for job', jobId);
            const status = await checkAnalysisStatus(jobId);
            console.log('Status for job', jobId, ':', status);

            // Check if this job is being cancelled
            const cancellingInfo = cancellingJobs.get(jobId);
            
            if (cancellingInfo) {
                // Job is in cancellation state
                if (status && status.status === 'cancelled') {
                    // Still cancelling - keep showing the tag
                    console.log('Job', jobId, 'still cancelling...');
                    // Don't update UI, keep showing "Cancelling..."
                } else {
                    // Status changed from 'cancelled' - task finished!
                    console.log('Task finished after cancellation, reloading page');
                    cancellingJobs.delete(jobId);
                    stopProgressTracking(jobId);
                    // Full page reload to ensure all state is fresh
                    window.location.reload();
                    return;
                }
            } else {
                // Not cancelling - normal progress tracking
                if (status && status.status === 'processing') {
                    // Update progress tag for this job
                    const percentage = status.progress_percentage || 0;
                    updateJobProgress(jobId, percentage);
                } else if (status && (status.status === 'completed' || status.status === 'failed')) {
                    // Stop tracking and reload
                    console.log('Analysis completed/failed for job', jobId, 'status:', status.status);
                    stopProgressTracking(jobId);
                    window.location.reload();
                }
            }
        } catch (error) {
            console.error('Error in progress tracking for job', jobId, error);
        }
    }, 2000); // Poll every 2 seconds for faster cancellation response

    analyzingJobs.set(jobId, intervalId);
}

/**
 * Stop and remove the interval polling analysis progress for the given job.
 *
 * If the job is not being tracked, this function is a no-op.
 * @param {string} jobId - Job identifier whose progress polling should be stopped.
 */
function stopProgressTracking(jobId) {
    const intervalId = analyzingJobs.get(jobId);
    if (intervalId) {
        clearInterval(intervalId);
        analyzingJobs.delete(jobId);
        console.log('Stopped progress tracking for job', jobId);
    }
}

/**
 * Mark a job as being cancelled
 * @param {string} jobId - The job ID
 */
function markJobAsCancelling(jobId) {
    cancellingJobs.set(jobId, {started: Date.now(), lastStatus: 'cancelling'});
    // Update UI immediately - both progress tag and button
    updateJobProgress(jobId, null, true);
    updateCancelButtonState(jobId, true);
}

/**
 * Update the cancel button state for a specific job
 * @param {string} jobId - The job ID to update
 * @param {boolean} isCancelling - Whether the job is being cancelled
 */
function updateCancelButtonState(jobId, isCancelling) {
    // Find the progress tag for this job
    const progressTag = document.querySelector(`[data-progress-type="in-progress"][data-job-id="${jobId}"]`);
    console.log('updateCancelButtonState: progressTag found:', !!progressTag, 'jobId:', jobId, 'isCancelling:', isCancelling);
    
    if (progressTag) {
        const jobCard = progressTag.closest('.border.border-gray-200');
        console.log('updateCancelButtonState: jobCard found:', !!jobCard);
        
        if (jobCard) {
            // Find all buttons in the right side column
            const rightSide = jobCard.querySelector('.flex.flex-col.space-y-2');
            console.log('updateCancelButtonState: rightSide found:', !!rightSide);
            
            if (rightSide) {
                const buttons = rightSide.querySelectorAll('button');
                console.log('updateCancelButtonState: found', buttons.length, 'buttons');
                
                // The cancel button is the 4th button (index 3) - after Edit, Copy Link, Deactivate/Activate
                const cancelBtn = buttons[3];
                console.log('updateCancelButtonState: cancelBtn found:', !!cancelBtn, 'text:', cancelBtn ? cancelBtn.textContent : 'N/A');
                
                if (cancelBtn && cancelBtn.textContent.trim() === 'Cancel Analysis') {
                    if (isCancelling) {
                        cancelBtn.disabled = true;
                        cancelBtn.classList.add('opacity-50', 'cursor-not-allowed');
                        cancelBtn.classList.remove('text-red-600', 'hover:text-red-800');
                        cancelBtn.classList.add('text-gray-400');
                        cancelBtn.style.pointerEvents = 'none';
                        console.log('updateCancelButtonState: disabled cancel button');
                    } else {
                        cancelBtn.disabled = false;
                        cancelBtn.classList.remove('opacity-50', 'cursor-not-allowed', 'text-gray-400');
                        cancelBtn.classList.add('text-red-600', 'hover:text-red-800');
                        cancelBtn.style.pointerEvents = 'auto';
                        console.log('updateCancelButtonState: enabled cancel button');
                    }
                }
            }
        }
    }
}

/**
 * Update the progress tag UI for a specific job
 * @param {string} jobId - The job ID to update
 * @param {number|null} percentage - The progress percentage (0-100), null for cancelling state
 * @param {boolean} isCancelling - Whether the job is being cancelled
 */
function updateJobProgress(jobId, percentage, isCancelling = false) {
    // Find all progress tags and update the one for this job
    const progressTags = document.querySelectorAll('[data-progress-type="in-progress"]');
    console.log('Found', progressTags.length, 'progress tags, looking for job', jobId);
    
    progressTags.forEach(tag => {
        const tagJobId = tag.getAttribute('data-job-id');
        console.log('Progress tag job ID:', tagJobId, 'looking for:', jobId, 'match:', tagJobId === jobId);
        
        if (tagJobId === jobId) {
            // The tag structure is:
            // <span data-progress-type="in-progress" data-job-id="...">
            //   <span class="...animate-spin">⟳</span>
            //   <span class="text-gray-900 tracking-wide uppercase">Analyzing... 45%</span>
            // </span>
            const spans = tag.querySelectorAll('span');
            const spinner = spans[0];  // First span is the spinner
            const textSpan = spans[1];  // Second span is the text

            console.log('Updating job', jobId, 'isCancelling:', isCancelling, 'percentage:', percentage, 'textSpan:', textSpan);
            
            if (isCancelling) {
                // Show cancelling state
                if (textSpan) {
                    textSpan.textContent = 'Cancelling...';
                    textSpan.className = 'text-gray-600 tracking-wide uppercase';
                    console.log('Set text to "Cancelling..."');
                }
                // Slow down spinner
                if (spinner) {
                    spinner.style.animationDuration = '2s';
                }
            } else if (percentage !== null) {
                // Show progress percentage
                if (textSpan) {
                    textSpan.textContent = 'Analyzing... ' + percentage + '%';
                    textSpan.className = 'text-gray-900 tracking-wide uppercase';
                }
                // Normal spinner speed
                if (spinner) {
                    spinner.style.animationDuration = '1s';
                }
            }
            console.log('Updated progress for job', jobId, isCancelling ? '(cancelling)' : percentage + '%');
        }
    });
}

/**
 * Resume active AI analysis progress polling for any job cards marked as in-progress.
 *
 * Finds elements with `data-progress-type="in-progress"` and starts tracking for each job not already being tracked.
 */
function initProgressTracking() {
    // Find all job cards with in-progress tags
    const progressTags = document.querySelectorAll('[data-progress-type="in-progress"]');
    progressTags.forEach(tag => {
        const jobId = tag.getAttribute('data-job-id');
        if (jobId && !analyzingJobs.has(jobId)) {
            console.log('Resuming progress tracking for job', jobId);
            startProgressTracking(jobId);
        }
    });
}

/**
 * Stop and clear all active AI analysis progress polling for every tracked job.
 *
 * Cancels each polling interval, clears the internal tracking map, and leaves no active analyzers running.
 */
function stopAllProgressTracking() {
    analyzingJobs.forEach((intervalId, jobId) => {
        clearInterval(intervalId);
    });
    analyzingJobs.clear();
    console.log('Stopped all progress tracking');
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
    // Initialize progress tracking after job listings are fully loaded and rendered
    loadJobListings().then(() => {
        initProgressTracking();
    });
});