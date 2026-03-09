/**
 * Reporting Page Progress Tracking
 * Handles progress tracking for analysis re-run on the reporting page
 */

(function() {
    'use strict';

    // Track jobs currently being analyzed (jobId -> intervalId mapping)
    const analyzingJobs = new Map();

    /**
     * Helper function to get CSRF token from meta tag
     * @returns {string|null} CSRF token
     */
    function getCsrfToken() {
        const tokenMeta = document.querySelector('meta[name="csrf-token"]');
        return tokenMeta ? tokenMeta.getAttribute('content') : null;
    }

    /**
     * Check analysis status for a job
     * @param {string} jobId - The job ID to check
     * @returns {Promise<Object|null>} Status data or null
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
     * Start progress tracking for a job analysis
     * @param {string} jobId - The job ID to track
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
                } else if (status && (status.status === 'completed' || status.status === 'failed')) {
                    // Stop tracking and reload the page
                    console.log('Analysis completed/failed for job', jobId, 'status:', status.status);
                    stopProgressTracking(jobId);
                    window.location.reload(); // Refresh to show "Analysis Done" state
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
     * Update the progress tag UI for a specific job
     * @param {string} jobId - The job ID to update
     * @param {number} percentage - The progress percentage (0-100)
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
     * Initialize progress tracking for jobs that are already in progress
     * Called on page load to resume tracking after page refresh
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
    });

    /**
     * Re-run AI analysis for a job
     * @param {string} jobId - The job ID to re-run analysis for
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

    // Expose functions globally for toolbar use
    window.startProgressTracking = startProgressTracking;
    window.initProgressTracking = initProgressTracking;
    window.rerunAnalysis = rerunAnalysis;

})();
