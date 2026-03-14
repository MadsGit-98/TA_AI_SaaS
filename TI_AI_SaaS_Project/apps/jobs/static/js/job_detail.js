/**
 * Job Detail Page JavaScript
 * Handles AI analysis actions and modal interactions
 */

(function() {
    'use strict';

    /**
     * Retrieve the CSRF token from the meta tag named "csrf-token".
     * @returns {string|null} The CSRF token if present, `null` otherwise.
     */
    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    }

    /**
     * Copy the application link for the specified job to the clipboard.
     *
     * Alerts the user on success or failure; logs the underlying error to the console when copying fails.
     * @param {string} jobId - Job identifier used to build the application URL.
     */
    function copyApplicationLink(jobId) {
        if (!jobId) {
            alert('No application link available');
            return;
        }
        var fullLink = window.location.origin + '/apply/' + jobId;
        navigator.clipboard.writeText(fullLink).then(function() {
            alert('Application link copied to clipboard!');
        }).catch(function(err) {
            console.error('Failed to copy link:', err);
            alert('Failed to copy link');
        });
    }

    /**
     * Show the rerun analysis modal dialog.
     *
     * If the modal element with id "rerun-modal" is not found, a warning is logged to the console.
     */
    function openRerunModal() {
        var modal = document.getElementById('rerun-modal');
        if (modal) {
            modal.style.display = 'flex';
        } else {
            console.warn('Rerun modal element not found');
        }
    }

    /**
     * Close re-run analysis modal
     */
    function closeRerunModal() {
        var modal = document.getElementById('rerun-modal');
        if (modal) {
            modal.style.display = 'none';
        } else {
            console.warn('Rerun modal element not found');
        }
    }

    /**
     * Request a re-run of the current job's analysis and begin progress tracking.
     *
     * Sends a confirmation POST for the job identified by window.JOB_DETAIL_CONFIG.jobId.
     * On success, closes the rerun modal, starts progress tracking for that job, and reloads the page to show progress. If the job ID is missing or the request fails, logs an error and shows an alert with a descriptive message.
     */
    function confirmRerunAnalysis() {
        // Validate JOB_DETAIL_CONFIG exists and has jobId
        if (!window.JOB_DETAIL_CONFIG || !window.JOB_DETAIL_CONFIG.jobId) {
            console.error('Job ID not found in JOB_DETAIL_CONFIG');
            alert('Error: Job information is not available. Please refresh the page and try again.');
            return;
        }

        var jobId = window.JOB_DETAIL_CONFIG.jobId;

        fetch('/api/analysis/jobs/' + jobId + '/analysis/re-run/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({ confirm: true })
        })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            if (data.success) {
                // Close modal
                closeRerunModal();

                // Start progress tracking
                startProgressTracking(jobId);

                // Reload page to show progress tag
                window.location.reload();
            } else {
                alert('Error: ' + (data.error?.message || 'Failed to re-run analysis'));
            }
        })
        .catch(function(error) {
            console.error('Error re-running analysis:', error);
            alert('Failed to re-run analysis. Please try again.');
        });
    }

    /**
     * Initiates analysis for the current job, starts progress tracking, and reloads the page on success.
     *
     * Looks up the job ID on window.JOB_DETAIL_CONFIG, sends a POST to the analysis-initiate endpoint for that job,
     * and, if the response indicates success, starts progress tracking for the job and reloads the page.
     * If the job ID is missing or the request fails, shows an alert to the user.
     */
    function initiateAnalysis() {
        // Validate JOB_DETAIL_CONFIG exists and has jobId
        if (!window.JOB_DETAIL_CONFIG || !window.JOB_DETAIL_CONFIG.jobId) {
            console.error('Job ID not found in JOB_DETAIL_CONFIG');
            alert('Error: Job information is not available. Please refresh the page and try again.');
            return;
        }

        var jobId = window.JOB_DETAIL_CONFIG.jobId;

        fetch('/api/analysis/jobs/' + jobId + '/analysis/initiate/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'include'
        })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            if (data.success) {
                // Start progress tracking
                startProgressTracking(jobId);
                
                // Reload page to show progress tag
                window.location.reload();
            } else {
                alert('Error: ' + (data.error?.message || 'Failed to start analysis'));
            }
        })
        .catch(function(error) {
            console.error('Error initiating analysis:', error);
            alert('Failed to start analysis. Please try again.');
        });
    }

    /**
     * Cancel the analysis for the current job after user confirmation.
     *
     * Validates that window.JOB_DETAIL_CONFIG.jobId exists, prompts the user to confirm cancellation (informing that already processed results are preserved), sends a cancellation request to the server including the CSRF token, stops client-side progress tracking for the job on success, and reloads the page after a short delay. Displays an alert on failure or network error.
     */
    function cancelAnalysis() {
        // Validate JOB_DETAIL_CONFIG exists and has jobId
        if (!window.JOB_DETAIL_CONFIG || !window.JOB_DETAIL_CONFIG.jobId) {
            console.error('Job ID not found in JOB_DETAIL_CONFIG');
            alert('Error: Job information is not available. Please refresh the page and try again.');
            return;
        }

        var jobId = window.JOB_DETAIL_CONFIG.jobId;

        if (!confirm('Are you sure you want to cancel the analysis? Results for already processed applicants will be preserved.')) {
            return;
        }

        fetch('/api/analysis/jobs/' + jobId + '/analysis/cancel/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'include'
        })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            if (data.success) {
                // Stop progress tracking
                stopProgressTracking(jobId);
                
                // Wait a moment to ensure cancellation flag is set in Redis
                // Then reload to get fresh data from server
                setTimeout(() => {
                    window.location.reload();
                }, 500);
            } else {
                alert('Error: ' + (data.error?.message || 'Failed to cancel analysis'));
            }
        })
        .catch(function(error) {
            console.error('Error cancelling analysis:', error);
            alert('Failed to cancel analysis. Please try again.');
        });
    }

    /**
     * Close the rerun modal if the click occurred on the modal overlay.
     * @param {Event} event - Click event whose target is checked; if it equals the modal element the modal will be closed.
     */
    function handleModalOutsideClick(event) {
        var modal = document.getElementById('rerun-modal');
        if (modal && event.target === modal) {
            closeRerunModal();
        }
    }

    /**
     * Initialize event handlers and UI behaviors for the job detail page.
     *
     * Attaches click handlers for the application link copy button (if present), the rerun modal outside-click close behavior (if present), and the logout link (if present). The logout handler sends a POST logout request and then navigates to the site root regardless of the request outcome.
     */
    function init() {
        // Attach copy link button handler
        var copyLinkBtn = document.getElementById('copy-link-btn');
        if (copyLinkBtn) {
            copyLinkBtn.addEventListener('click', function() {
                var link = this.dataset.applicationLink;
                copyApplicationLink(link);
            });
        }

        // Attach modal outside click handler
        var modal = document.getElementById('rerun-modal');
        if (modal) {
            modal.addEventListener('click', handleModalOutsideClick);
        }

        // Set up logout event listener
        var logoutLink = document.getElementById('logout-link');
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
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose functions globally (for potential external use)
    window.openRerunModal = openRerunModal;
    window.closeRerunModal = closeRerunModal;
    window.confirmRerunAnalysis = confirmRerunAnalysis;
    window.initiateAnalysis = initiateAnalysis;
    window.cancelAnalysis = cancelAnalysis;

    // =============================================================================
    // Progress Tracking Functions
    // =============================================================================

    // Track jobs currently being analyzed (jobId -> intervalId mapping)
    const analyzingJobs = new Map();

    /**
     * Retrieve the current analysis status for the given job.
     * @param {string} jobId - The job identifier.
     * @returns {Object|null} Status payload when available, `null` when not available or on error.
     */
    async function checkAnalysisStatus(jobId) {
        try {
            const response = await fetch(`/api/analysis/jobs/${jobId}/analysis/status/`, {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                },
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

    /**
     * Begin periodic polling to track analysis progress for a job and update the UI until the job reaches a terminal state.
     *
     * Polls the analysis status every 6 seconds; while status is "processing" it updates on-page progress indicators,
     * and when status becomes "completed", "failed", or "cancelled" it stops tracking and reloads the page.
     *
     * @param {string} jobId - The job identifier to track (used to match DOM progress elements and API requests).
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
                const status = await checkAnalysisStatus(jobId);

                if (status && status.status === 'processing') {
                    // Update progress tag for this job
                    const percentage = status.progress_percentage || 0;
                    updateJobProgress(jobId, percentage);
                } else if (status && (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled')) {
                    // Stop tracking and reload the page
                    console.log('Analysis completed/failed/cancelled for job', jobId, 'status:', status.status);
                    stopProgressTracking(jobId);
                    window.location.reload(); // Refresh to show updated state
                }
            } catch (error) {
                console.error('Error in progress tracking for job', jobId, error);
            }
        }, 6000); // Poll every 6 seconds (10 requests/minute, within 600/hour limit)

        analyzingJobs.set(jobId, intervalId);
    }

    /**
     * Stop progress tracking for a job
     * @param {string} jobId - The job ID to stop tracking
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
     * Update the visible progress text for in-progress elements belonging to a job.
     *
     * Locates elements with `data-progress-type="in-progress"` and `data-job-id` equal to the provided `jobId` and sets their child element with class `.text-gray-900` to "Analyzing... {percentage}%".
     * @param {string} jobId - The job identifier to match against element `data-job-id`.
     * @param {number} percentage - Progress percentage (0 to 100) to display.
     */
    function updateJobProgress(jobId, percentage) {
        // Find all progress tags and update the one for this job
        const progressTags = document.querySelectorAll('[data-progress-type="in-progress"]');
        progressTags.forEach(tag => {
            if (tag.getAttribute('data-job-id') === jobId) {
                // Update the percentage text
                const textSpan = tag.querySelector('.text-gray-900');
                if (textSpan) {
                    textSpan.textContent = 'Analyzing... ' + percentage + '%';
                }
                console.log('Updated progress for job', jobId, 'to', percentage + '%');
            }
        });
    }

    /**
     * Resume progress polling for jobs marked in-progress in the DOM.
     *
     * Scans the document for elements with `data-progress-type="in-progress"` and starts progress tracking
     * for each associated `data-job-id` that is not already being tracked.
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

    // Expose progress tracking functions globally
    window.startProgressTracking = startProgressTracking;
    window.initProgressTracking = initProgressTracking;

    // Initialize progress tracking on page load
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(() => {
            initProgressTracking();
        }, 100);
    });

})();
