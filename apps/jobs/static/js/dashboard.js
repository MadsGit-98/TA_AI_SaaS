
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

/**
 * Show message in modal
 * @param {string} title - Modal title
 * @param {string} message - Modal message
 * @param {string} type - 'success' or 'error' (optional, for future styling)
 * @param {Function} onClose - Optional callback function to execute after closing modal
 */
function showMessageModal(title, message, type, onClose) {
    const modal = document.getElementById('message-modal');
    const titleEl = document.getElementById('message-modal-title');
    const messageEl = document.getElementById('message-modal-message');
    const okBtn = modal?.querySelector('button');

    if (modal && titleEl && messageEl) {
        titleEl.textContent = title;
        messageEl.textContent = message;
        modal.style.display = 'flex';
        
        // Remove old event listeners to prevent duplicates
        if (okBtn) {
            const newOkBtn = okBtn.cloneNode(true);
            okBtn.parentNode.replaceChild(newOkBtn, okBtn);
            
            // Add new event listener with callback
            newOkBtn.addEventListener('click', function() {
                closeMessageModal(onClose);
            });
        }
    } else {
        // Fallback to inline messages if modal not found
        console.warn('Message modal not found, using inline messages');
        if (type === 'error') {
            showError(message);
        } else {
            showSuccess(message);
        }
        // Execute callback after inline message completes
        // Use same duration as showError (5000ms) or showSuccess (3000ms)
        if (onClose && typeof onClose === 'function') {
            const duration = type === 'error' ? 5000 : 3000;
            setTimeout(onClose, duration);
        }
    }
}

/**
 * Close message modal
 * @param {Function} onClose - Optional callback function to execute after closing modal
 */
function closeMessageModal(onClose) {
    const modal = document.getElementById('message-modal');
    if (modal) {
        modal.style.display = 'none';
        // Execute callback if provided
        if (onClose && typeof onClose === 'function') {
            onClose();
        }
    }
}

/**
 * Show confirmation modal
 * @param {string} message - Confirmation message
 * @param {Function} onConfirm - Callback function when confirmed
 * @param {string} title - Modal title (optional, default 'Confirm')
 */
function showConfirmModal(message, onConfirm, title) {
    const modal = document.getElementById('confirm-modal');
    const titleEl = document.getElementById('confirm-modal-title');
    const messageEl = document.getElementById('confirm-modal-message');
    const cancelBtn = document.getElementById('confirm-modal-cancel');
    const confirmBtn = document.getElementById('confirm-modal-confirm');
    
    if (modal && titleEl && messageEl && cancelBtn && confirmBtn) {
        titleEl.textContent = title || 'Confirm';
        messageEl.textContent = message;
        modal.style.display = 'flex';
        
        // Remove old event listeners to prevent duplicates
        const newCancelBtn = cancelBtn.cloneNode(true);
        cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        
        // Add new event listeners
        newCancelBtn.addEventListener('click', function() {
            modal.style.display = 'none';
        });
        
        newConfirmBtn.addEventListener('click', function() {
            modal.style.display = 'none';
            if (onConfirm) onConfirm();
        });
    } else {
        // Fallback to confirm if modal not found
        console.warn('Confirmation modal not found, using confirm');
        if (confirm(message)) {
            if (onConfirm) onConfirm();
        }
    }
}

// Helper function to show error message (kept for backward compatibility)
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

// Helper function to show success message (kept for backward compatibility)
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

// Helper function to create job element
function createJobElement(job, container) {
    const jobElement = document.createElement('div');
    jobElement.className = 'border border-gray-200 rounded-lg p-4 bg-white job-listing-card';
    jobElement.setAttribute('data-job-id', job.id);

    // Format dates
    const startDate = job.start_date ? new Date(job.start_date).toLocaleDateString() : 'Not set';
    const expirationDate = job.expiration_date ? new Date(job.expiration_date).toLocaleDateString() : 'Not set';

    // Create the content using safe DOM manipulation
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'flex justify-between items-start';

    // Left side content
    const leftSide = document.createElement('div');

    // Title and applicant count container
    const titleContainer = document.createElement('div');
    titleContainer.className = 'flex items-center gap-2 mb-2';

    const titleElement = document.createElement('h2');
    titleElement.className = 'text-xl font-semibold';
    titleElement.textContent = job.title;
    titleContainer.appendChild(titleElement);

    // Applicant count badge
    const applicantCount = job.applicant_count || 0;
    const applicantBadge = document.createElement('span');
    applicantBadge.className = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-code-block-bg text-primary-text';
    applicantBadge.textContent = `${applicantCount} applicant${applicantCount !== 1 ? 's' : ''}`;
    applicantBadge.title = `${applicantCount} applicant${applicantCount !== 1 ? 's' : ''} applied to this job`;
    titleContainer.appendChild(applicantBadge);

    leftSide.appendChild(titleContainer);

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
        // For bulk upload type, disable copy functionality but still show the link
        if (job.upload_type === 'bulk') {
            copyButton.disabled = true;
            copyButton.classList.add('opacity-50', 'cursor-not-allowed');
            copyButton.title = 'Link not copiable for bulk upload jobs';
        } else {
            copyButton.addEventListener('click', () => copyApplicationLink(job.application_link));
            copyButton.title = 'Copy application link to clipboard';
        }
    } else {
        copyButton.textContent = 'No Link Available';
        copyButton.disabled = true;
        copyButton.classList.add('opacity-50', 'cursor-not-allowed');
    }
    rightSide.appendChild(copyButton);

    // Conditional status button - Only show for 'form' upload type
    // Bulk upload jobs cannot be activated/deactivated
    if (job.upload_type === 'form') {
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
    }

    // Start Upload button (for bulk upload type jobs)
    if (job.upload_type === 'bulk') {
        const uploadButton = document.createElement('button');
        uploadButton.className = 'text-amber-600 hover:text-amber-800 text-sm font-medium';
        uploadButton.textContent = 'Start Upload';
        uploadButton.title = 'Upload resumes in bulk for this job';
        uploadButton.addEventListener('click', () => {
            window.location.href = `/bulk-upload/${job.id}/`;
        });
        rightSide.appendChild(uploadButton);
    }

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
                        finalizeJobListingsProgressUi([]);
                        return;
                    }
                    
                    // Process the direct array
                    container.innerHTML = '';
                    data.forEach(job => {
                        createJobElement(job, container);
                    });
                    finalizeJobListingsProgressUi(data);
                    
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
                finalizeJobListingsProgressUi([]);
                return;
            }

            container.innerHTML = '';
            data.results.forEach(job => {
                createJobElement(job, container);
            });
            finalizeJobListingsProgressUi(data.results);

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
    showConfirmModal('Are you sure you want to activate this job?', function() {
        fetch(`/dashboard/jobs/${jobId}/activate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'include'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            showMessageModal('Success', 'Job activated successfully!', 'success');
            loadJobListings();
        })
        .catch(error => {
            console.error('Error activating job:', error);
            showMessageModal('Error', 'An error occurred while activating the job.', 'error');
        });
    });
}

async function deactivateJob(jobId) {
    showConfirmModal('Are you sure you want to deactivate this job?', function() {
        fetch(`/dashboard/jobs/${jobId}/deactivate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            credentials: 'include'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            showMessageModal('Success', 'Job deactivated successfully!', 'success');
            loadJobListings();
        })
        .catch(error => {
            console.error('Error deactivating job:', error);
            showMessageModal('Error', 'An error occurred while deactivating the job.', 'error');
        });
    });
}

function copyApplicationLink(link) {
    const fullLink = `${window.location.origin}/apply/${link}`;
    navigator.clipboard.writeText(fullLink)
        .then(() => {
            showMessageModal('Success', 'Application link copied to clipboard!', 'success');
        })
        .catch(err => {
            console.error('Failed to copy link: ', err);
            showMessageModal('Error', 'Failed to copy link to clipboard.', 'error');
        });
}

// AI Analysis functions
async function initiateAnalysis(jobId) {
    showConfirmModal('Are you sure you want to initiate AI analysis for all applicants? This process may take several minutes depending on the number of applicants.', function() {
        fetch(`/api/analysis/jobs/${jobId}/analysis/initiate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'include'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                const applicantCount = data.data.applicant_count;
                const estimatedMinutes = Math.ceil(data.data.estimated_duration_seconds / 60);
                showMessageModal('Success', `AI analysis started for ${applicantCount} applicants. Estimated time: ~${estimatedMinutes} minute(s).`, 'success');
                startProgressTracking(jobId);
                setTimeout(() => {
                    loadJobListings();
                }, 500);
            } else {
                const errorMessage = data.error ? data.error.message : 'Failed to initiate analysis';
                showMessageModal('Error', `Error: ${errorMessage}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error initiating analysis:', error);
            showMessageModal('Error', 'An error occurred while initiating AI analysis.', 'error');
        });
    });
}

/**
 * Cancel AI analysis for a job
 * @param {string} jobId - The job ID to cancel analysis for
 */
async function cancelAnalysis(jobId) {
    if (cancellingJobs.has(jobId)) {
        console.log('Already cancelling job', jobId);
        return;
    }

    showConfirmModal('Are you sure you want to cancel the analysis? Results for already processed applicants will be preserved.', function() {
        markJobAsCancelling(jobId);

        fetch(`/api/analysis/jobs/${jobId}/analysis/cancel/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'include'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showMessageModal('Success', data.data.message || 'Analysis cancellation requested.', 'success');
            } else {
                const errorMessage = data.error ? data.error.message : 'Failed to cancel analysis';
                showMessageModal('Error', `Error: ${errorMessage}`, 'error', function() {
                    // Reload page after user dismisses error modal
                    cancellingJobs.delete(jobId);
                    window.location.reload();
                });
            }
        })
        .catch(error => {
            console.error('Error cancelling analysis:', error);
            showMessageModal('Error', 'An error occurred while cancelling analysis.', 'error', function() {
                // Reload page after user dismisses error modal
                cancellingJobs.delete(jobId);
                window.location.reload();
            });
        });
    });
}

function viewAnalysis(jobId) {
    // Redirect to the analysis reporting page
    window.location.href = `/analysis/reporting/${jobId}/`;
}

// =============================================================================
// WebSocket-based Progress Tracking Functions (replaces polling)
// =============================================================================

// Track jobs currently being analyzed (jobId -> WebSocket subscription)
const analyzingJobs = new Map();

// Track jobs being cancelled (jobId -> {started: timestamp, lastStatus: string})
const cancellingJobs = new Map();

/** Survives full page reload so we can reconnect WebSockets and restore the progress chip. */
const SESSION_TRACKING_KEY = 'dashboard_analysis_tracking_job_ids';

function readTrackedJobIdsFromSession() {
    try {
        const raw = sessionStorage.getItem(SESSION_TRACKING_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch (e) {
        return [];
    }
}

function writeTrackedJobIdsToSession(ids) {
    sessionStorage.setItem(SESSION_TRACKING_KEY, JSON.stringify(ids));
}

function addTrackedJobToSession(jobId) {
    const jid = String(jobId);
    const ids = new Set(readTrackedJobIdsFromSession());
    ids.add(jid);
    writeTrackedJobIdsToSession([...ids]);
}

function removeTrackedJobFromSession(jobId) {
    const jid = String(jobId);
    writeTrackedJobIdsToSession(readTrackedJobIdsFromSession().filter((id) => id !== jid));
}

/**
 * Drop stored ids only when this response includes the job and it is no longer in progress.
 * Jobs not on the current page are kept so pagination does not break resume-after-reload.
 */
function pruneSessionTrackingAgainstJobs(jobs) {
    if (!jobs || !jobs.length) return;
    const byId = new Map(jobs.map((j) => [String(j.id), j]));
    const stored = readTrackedJobIdsFromSession();
    const kept = stored.filter((id) => {
        const job = byId.get(String(id));
        if (!job) return true;
        return job.analysis_in_progress === true;
    });
    if (kept.length !== stored.length) {
        writeTrackedJobIdsToSession(kept);
    }
}

function resumeTrackingFromSessionStorage() {
    readTrackedJobIdsFromSession().forEach((jobId) => {
        if (!jobId || analyzingJobs.has(jobId)) return;
        ensureProgressTagForJob(jobId);
        startProgressTracking(jobId);
    });
}

/**
 * After the job list DOM is rebuilt: prune stale session ids, restore chips for in-memory
 * trackers, attach WS for API-rendered in-progress tags, then resume any jobs stored for reload.
 */
function finalizeJobListingsProgressUi(jobsList) {
    pruneSessionTrackingAgainstJobs(jobsList || []);
    restoreActiveAnalysisTags();
    initProgressTracking();
    resumeTrackingFromSessionStorage();
}

/**
 * Ensure the in-progress tag exists for a job (e.g. right after initiate or if
 * the list refreshed before Redis counters were visible to the jobs API).
 * @param {string} jobId
 */
function ensureProgressTagForJob(jobId) {
    const existing = document.querySelector(
        `[data-progress-type="in-progress"][data-job-id="${jobId}"]`
    );
    if (existing) {
        return;
    }
    const card = document.querySelector(`.job-listing-card[data-job-id="${jobId}"]`);
    if (!card) {
        console.warn('ensureProgressTagForJob: no job card for', jobId);
        return;
    }
    const tagsContainer = card.querySelector('.mt-2.flex.flex-wrap.gap-2');
    if (!tagsContainer) {
        console.warn('ensureProgressTagForJob: no tags container for', jobId);
        return;
    }
    const progressTag = document.createElement('span');
    progressTag.className =
        'inline-flex items-center gap-1.5 px-3 py-1.5 bg-yellow-50 border-l-[3px] border-yellow-400 rounded font-mono text-xs font-semibold text-gray-900 shadow-sm';
    progressTag.title = 'AI Analysis in Progress';
    progressTag.setAttribute('data-job-id', jobId);
    progressTag.setAttribute('data-progress-type', 'in-progress');
    progressTag.innerHTML =
        '<span class="inline-flex items-center justify-center w-4 h-4 text-yellow-600 animate-spin" aria-label="Loading">⟳</span>' +
        '<span class="text-gray-900 tracking-wide uppercase">Analyzing... 0%</span>';
    tagsContainer.appendChild(progressTag);
}

/**
 * After loadJobListings() rebuilds the DOM, re-attach progress chips for any job
 * the client is still tracking over WebSocket (API/Redis can lag or omit flags).
 */
function restoreActiveAnalysisTags() {
    analyzingJobs.forEach(function (_ws, jobId) {
        ensureProgressTagForJob(jobId);
    });
}

/**
 * Start progress tracking for a job analysis using WebSocket
 * @param {string} jobId - The job ID to track
 */
function startProgressTracking(jobId) {
    jobId = String(jobId);
    // Check if already tracking this job
    if (analyzingJobs.has(jobId)) {
        console.log('Already tracking job', jobId);
        return;
    }

    console.log('Starting WebSocket progress tracking for job', jobId);

    if (typeof window.AnalysisWebSocket !== 'function') {
        console.error('AnalysisWebSocket class not found - cannot track job', jobId);
        return;
    }

    // Create WebSocket instance for this job
    const ws = new window.AnalysisWebSocket();
    
    // Set up callbacks
    ws.onProgress(function(data) {
        console.log('Progress update for job', jobId, ':', data);
        
        // Check if this job is being cancelled
        const cancellingInfo = cancellingJobs.get(jobId);
        
        if (cancellingInfo) {
            // Job is in cancellation state - keep showing cancelling tag
            console.log('Job', jobId, 'still cancelling...');
        } else {
            // Normal progress tracking - update percentage
            const percentage = data.progress_percentage || 0;
            updateJobProgress(jobId, percentage);
        }
    });
    
    ws.onCompleted(function(data) {
        console.log('Analysis completed for job', jobId);
        stopProgressTracking(jobId);
        window.location.reload();
    });
    
    ws.onCancelled(function(data) {
        console.log('Analysis cancelled for job', jobId);
        cancellingJobs.delete(jobId);
        stopProgressTracking(jobId);
        window.location.reload();
    });
    
    ws.onFailed(function(data) {
        console.error('Analysis failed for job', jobId, ':', data.error_message);
        stopProgressTracking(jobId);
        window.location.reload();
    });
    
    ws.onStateChanged(function(state) {
        console.log('WebSocket state changed for job', jobId, ':', state);
    });

    ws.connect(jobId);

    ensureProgressTagForJob(jobId);
    
    // Store WebSocket instance
    analyzingJobs.set(jobId, ws);
    addTrackedJobToSession(jobId);
}

/**
 * Stop progress tracking for a job
 * @param {string} jobId - The job ID to stop tracking
 */
function stopProgressTracking(jobId) {
    jobId = String(jobId);
    removeTrackedJobFromSession(jobId);
    const ws = analyzingJobs.get(jobId);
    if (ws) {
        if (ws.close) {
            ws.close();
            console.log('Stopped WebSocket tracking for job', jobId);
        }
        analyzingJobs.delete(jobId);
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
    let progressTags = document.querySelectorAll(
        `[data-progress-type="in-progress"][data-job-id="${jobId}"]`
    );
    if (progressTags.length === 0) {
        ensureProgressTagForJob(jobId);
        progressTags = document.querySelectorAll(
            `[data-progress-type="in-progress"][data-job-id="${jobId}"]`
        );
    }
    console.log('Found', progressTags.length, 'progress tags for job', jobId);
    
    progressTags.forEach(tag => {
        const tagJobId = tag.getAttribute('data-job-id');
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
 * Initialize progress tracking for jobs that are already in progress
 * Called on page load to resume tracking after page refresh
 */
function initProgressTracking() {
    // Find all job cards with in-progress tags
    const progressTags = document.querySelectorAll('[data-progress-type="in-progress"]');
    progressTags.forEach(tag => {
        const jobId = tag.getAttribute('data-job-id');
        if (jobId && !analyzingJobs.has(jobId)) {
            console.log('Resuming WebSocket progress tracking for job', jobId);
            startProgressTracking(jobId);
        }
    });
}

// Stop all progress tracking (useful when navigating away)
function stopAllProgressTracking() {
    analyzingJobs.forEach((wsOrInterval, jobId) => {
        if (wsOrInterval.close) {
            // It's a WebSocket instance
            wsOrInterval.close();
        } else if (wsOrInterval.intervalId) {
            // It's a fallback polling interval
            clearInterval(wsOrInterval.intervalId);
        }
    });
    analyzingJobs.clear();
    writeTrackedJobIdsToSession([]);
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

    // Load job listings when page loads (finalizeJobListingsProgressUi runs inside loadJobListings)
    loadJobListings();
});

// Expose modal functions globally
window.closeMessageModal = closeMessageModal;