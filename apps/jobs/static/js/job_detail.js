/**
 * Job Detail Page JavaScript
 * Handles AI analysis actions and modal interactions
 */

(function() {
    'use strict';

    /**
     * Get CSRF token from meta tag
     * @returns {string|null} CSRF token
     */
    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    }

    /**
     * Copy application link to clipboard
     * @param {string} jobId - The job ID to construct the application link
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
     * Open re-run analysis modal
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
     * Confirm re-run analysis
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

                // Reload page to show progress tag
                // WebSocket will auto-initialize and track progress via analysis-websocket.js
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
     * Initiate AI analysis with loading indicator
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
                // Reload page to show progress tag
                // WebSocket will auto-initialize and track progress via analysis-websocket.js
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
     * Cancel AI analysis for a job
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
     * Close modal when clicking outside
     * @param {Event} event - Click event
     */
    function handleModalOutsideClick(event) {
        var modal = document.getElementById('rerun-modal');
        if (modal && event.target === modal) {
            closeRerunModal();
        }
    }

    /**
     * Initialize job detail page
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
    // DEPRECATED: Progress Tracking Functions - Use analysis-websocket.js instead
    // =============================================================================

    // Track jobs currently being analyzed (jobId -> intervalId mapping)
    const analyzingJobs = new Map();

    /**
     * Check analysis status for a job
     * @deprecated Use analysis-websocket.js instead
     */
    async function checkAnalysisStatus(jobId) {
        console.warn('DEPRECATED: checkAnalysisStatus() is deprecated. Use analysis-websocket.js instead.');
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
     * Start progress tracking for a job analysis
     * @deprecated Use analysis-websocket.js instead
     */
    function startProgressTracking(jobId) {
        console.warn('DEPRECATED: startProgressTracking() is deprecated. Use analysis-websocket.js instead.');
        // WebSocket handles progress tracking automatically
        console.log('WebSocket will handle progress tracking automatically');
    }

    /**
     * Stop progress tracking for a job
     * @deprecated Use analysis-websocket.js instead
     */
    function stopProgressTracking(jobId) {
        console.warn('DEPRECATED: stopProgressTracking() is deprecated. Use analysis-websocket.js instead.');
        const intervalId = analyzingJobs.get(jobId);
        if (intervalId) {
            clearInterval(intervalId);
            analyzingJobs.delete(jobId);
            console.log('Stopped progress tracking for job', jobId);
        }
    }

    /**
     * Update the progress tag UI for a specific job
     * @deprecated Use analysis-websocket.js instead
     */
    function updateJobProgress(jobId, percentage) {
        console.warn('DEPRECATED: updateJobProgress() is deprecated. Use analysis-websocket.js instead.');
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
     * Initialize progress tracking for jobs that are already in progress
     * @deprecated Use analysis-websocket.js instead
     */
    function initProgressTracking() {
        console.warn('DEPRECATED: initProgressTracking() is deprecated. Use analysis-websocket.js instead.');
        // WebSocket handles progress tracking automatically on page load
        console.log('WebSocket will handle progress tracking automatically');
    }

    // Expose progress tracking functions globally (deprecated)
    window.startProgressTracking = startProgressTracking;
    window.stopProgressTracking = stopProgressTracking;
    window.initProgressTracking = initProgressTracking;

    // Note: No auto-initialization needed here
    // WebSocket auto-initializes in analysis-websocket.js when page loads

})();
