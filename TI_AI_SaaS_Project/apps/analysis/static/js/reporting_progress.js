/**
 * Reporting Page Progress Tracking
 * Handles progress tracking for analysis re-run on the reporting page
 */

(function() {
    'use strict';

    // Track jobs currently being analyzed (jobId -> intervalId mapping)
    const analyzingJobs = new Map();

    /**
     * Reads the CSRF token from the document's meta[name="csrf-token"] tag.
     * @returns {string|null} The token value if the meta tag exists, `null` otherwise.
     */
    function getCsrfToken() {
        const tokenMeta = document.querySelector('meta[name="csrf-token"]');
        return tokenMeta ? tokenMeta.getAttribute('content') : null;
    }

    /**
     * Retrieve the analysis status for the given job ID.
     * @param {string} jobId - The analysis job identifier.
     * @returns {Object|null} The status object returned by the server if successful, `null` otherwise.
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

    /**
     * Begin polling an analysis job's status and update the page progress UI until the job finishes.
     *
     * Polls the server for the given job's status; while the job is "processing" it updates the visible
     * progress indicator, and when the job reaches "completed", "failed", or "cancelled" it stops
     * tracking and reloads the page to reflect the final state.
     *
     * @param {string} jobId - Identifier of the analysis job to track.
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
     * Stop tracking progress for the given analysis job and clear its polling interval.
     * @param {string} jobId - ID of the analysis job whose polling interval will be cleared.
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
     * Update the toolbar progress tag for a given analysis job.
     *
     * Sets the visible text to "Analyzing... {percentage}%". The `jobId` is used only for logging.
     * @param {string} jobId - Analysis job identifier (used for logging).
     * @param {number} percentage - Progress percentage between 0 and 100.
     */
    function updateJobProgress(jobId, percentage) {
        // Find the progress tag in the toolbar
        const progressTag = document.querySelector('[data-progress-type="in-progress"]');
        if (progressTag) {
            // Update the percentage text
            const textSpan = progressTag.querySelector('.text-gray-900');
            if (textSpan) {
                textSpan.textContent = 'Analyzing... ' + percentage + '%';
            }
            console.log('Updated progress for job', jobId, 'to', percentage + '%');
        }
    }

    /**
     * Resume tracking for any analysis job indicated by an in-progress progress tag in the DOM.
     *
     * If an element with data-progress-type="in-progress" and a data-job-id is present and that job
     * is not already being tracked, this function starts progress tracking for that job.
     */
    function initProgressTracking() {
        // Find the progress tag in the toolbar
        const progressTag = document.querySelector('[data-progress-type="in-progress"]');
        if (progressTag) {
            const jobId = progressTag.getAttribute('data-job-id');
            if (jobId && !analyzingJobs.has(jobId)) {
                console.log('Resuming progress tracking for job', jobId);
                startProgressTracking(jobId);
            }
        }
    }

    // Initialize progress tracking on page load
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(() => {
            initProgressTracking();
        }, 100);
        
        // Set up rerun analysis button handler
        const rerunBtn = document.getElementById('rerun-analysis-btn');
        if (rerunBtn) {
            rerunBtn.addEventListener('click', function() {
                const jobId = this.dataset.jobId;
                if (jobId && confirm('Are you sure you want to re-run the AI analysis? This will delete all previous results and start fresh. This action cannot be undone.')) {
                    rerunAnalysis(jobId);
                }
            });
        }
        
        // Set up cancel analysis button handler
        const cancelBtn = document.getElementById('cancel-analysis-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', function() {
                const jobId = this.dataset.jobId;
                if (!jobId) {
                    console.error('Cancel button missing data-job-id attribute');
                    return;
                }
                cancelAnalysis(jobId);
            });
        }
    });

    /**
     * Request a re-run of AI analysis for the specified job; on success, begin progress tracking and reload the page.
     * @param {string} jobId - The job identifier to re-run analysis for (used in the API request path).
     */
    async function rerunAnalysis(jobId) {
        try {
            const response = await fetch(`/api/analysis/jobs/${jobId}/analysis/re-run/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({ confirm: true })
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Re-run analysis request failed:', response.status, errorText);
                throw new Error(`Request failed with status ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                // Start progress tracking
                startProgressTracking(jobId);

                // Reload page to show progress tag
                window.location.reload();
            } else {
                const errorMsg = data.error && data.error.message ? data.error.message : 'Failed to re-run analysis';
                alert('Error: ' + errorMsg);
            }
        } catch (error) {
            console.error('Error re-running analysis:', error);
            alert('Failed to re-run analysis. Please try again.');
        }
    }

    /**
     * Cancel AI analysis for the specified job after user confirmation. On success, stops local progress tracking and reloads the page to reflect the updated job state.
     * @param {string} jobId - ID of the analysis job to cancel.
     */
    async function cancelAnalysis(jobId) {
        if (!confirm('Are you sure you want to cancel the analysis? Results for already processed applicants will be preserved.')) return;

        try {
            const response = await fetch(`/api/analysis/jobs/${jobId}/analysis/cancel/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Cancel analysis request failed:', response.status, errorText);
                throw new Error(`Request failed with status ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                alert(data.data.message || 'Analysis cancelled successfully.');

                // Stop progress tracking
                stopProgressTracking(jobId);

                // Wait a moment to ensure cancellation flag is set in Redis
                // Then reload to get fresh data from server
                setTimeout(() => {
                    window.location.reload();
                }, 500);
            } else {
                const errorMsg = data.error && data.error.message ? data.error.message : 'Failed to cancel analysis';
                alert('Error: ' + errorMsg);
            }
        } catch (error) {
            console.error('Error cancelling analysis:', error);
            alert('Failed to cancel analysis. Please try again.');
        }
    }

    // Expose functions globally for toolbar use
    window.startProgressTracking = startProgressTracking;
    window.initProgressTracking = initProgressTracking;
    window.rerunAnalysis = rerunAnalysis;
    window.cancelAnalysis = cancelAnalysis;

})();
