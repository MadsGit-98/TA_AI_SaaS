/**
 * Reporting Page Progress Tracking
 * Handles progress tracking for analysis re-run on the reporting page
 * 
 * DEPRECATED: This file now uses WebSocket-based updates via analysis-websocket.js
 * The polling mechanism has been deprecated in favor of real-time WebSocket updates
 */

(function() {
    'use strict';

    // Track jobs currently being analyzed (jobId -> WebSocket instance mapping)
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
     * Show message in modal (reuses job_detail.html modal if available)
     * @param {string} title - Modal title
     * @param {string} message - Modal message
     */
    function showMessageModal(title, message) {
        // Try to use the global message modal first
        const modal = document.getElementById('message-modal');
        const titleEl = document.getElementById('message-modal-title');
        const messageEl = document.getElementById('message-modal-message');

        if (modal && titleEl && messageEl) {
            titleEl.textContent = title;
            messageEl.textContent = message;
            modal.style.display = 'flex';
        } else {
            // Fallback to alert if modal not found
            console.warn('Message modal not found, using alert');
            // Use setTimeout to avoid blocking the UI
            setTimeout(() => {
                alert(title + ': ' + message);
            }, 100);
        }
    }

    /**
     * Close message modal
     */
    function closeMessageModal() {
        const modal = document.getElementById('message-modal');
        if (modal) {
            modal.style.display = 'none';
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

    /**
     * Check analysis status for a job (DEPRECATED - use WebSocket instead)
     * @deprecated Use analysis-websocket.js instead
     * @param {string} jobId - The job ID to check
     * @returns {Promise<Object|null>} Status data or null
     */
    async function checkAnalysisStatus(jobId) {
        console.warn('DEPRECATED: checkAnalysisStatus() is deprecated. Use analysis-websocket.js instead.');
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
     * Start progress tracking for a job analysis using WebSocket
     * @param {string} jobId - The job ID to track
     */
    function startProgressTracking(jobId) {
        // Check if already tracking this job
        if (analyzingJobs.has(jobId)) {
            console.log('Already tracking job', jobId);
            return;
        }

        console.log('Starting WebSocket progress tracking for job', jobId);

        // Check if AnalysisWebSocket is available
        if (typeof window.AnalysisWebSocket !== 'function') {
            console.warn('AnalysisWebSocket not available - falling back to polling for job', jobId);
            // Fallback to polling if WebSocket is not available
            startFallbackPolling(jobId);
            return;
        }

        // Create WebSocket instance for this job
        const ws = new window.AnalysisWebSocket();

        // Set up callbacks
        ws.onProgress(function(data) {
            console.log('Progress update for job', jobId, ':', data);
            const percentage = data.progress_percentage || 0;
            updateJobProgress(jobId, percentage);
        });

        ws.onCompleted(function(data) {
            console.log('Analysis completed for job', jobId);
            stopProgressTracking(jobId);
            window.location.reload();
        });

        ws.onCancelled(function(data) {
            console.log('Analysis cancelled for job', jobId);
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
            if (state === 'fallback_mode') {
                console.log('WebSocket unavailable, using fallback polling');
                // Close the existing WebSocket before starting fallback polling
                const existingWs = analyzingJobs.get(jobId);
                if (existingWs && existingWs.close && typeof existingWs.close === 'function') {
                    existingWs.close();
                    console.log('Closed WebSocket for job', jobId, 'before fallback');
                }
                // Remove the old WebSocket from the map
                analyzingJobs.delete(jobId);
                // Start fallback polling
                startFallbackPolling(jobId);
            }
        });

        // Connect to WebSocket
        ws.connect(jobId);

        // Store WebSocket instance
        analyzingJobs.set(jobId, ws);
    }

    /**
     * Fallback polling when WebSocket is unavailable (DEPRECATED)
     * @deprecated Use WebSocket instead
     * @param {string} jobId - The job ID to track
     */
    function startFallbackPolling(jobId) {
        console.warn('DEPRECATED: Using fallback polling. WebSocket is recommended.');
        
        const intervalId = setInterval(async () => {
            try {
                const status = await checkAnalysisStatus(jobId);

                if (status && status.status === 'processing') {
                    const percentage = status.progress_percentage || 0;
                    updateJobProgress(jobId, percentage);
                } else if (status && (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled')) {
                    stopProgressTracking(jobId);
                    clearInterval(intervalId);
                    window.location.reload();
                }
            } catch (error) {
                console.error('Error in fallback polling for job', jobId, error);
            }
        }, 6000);

        analyzingJobs.set(jobId, { intervalId: intervalId, isFallback: true });
    }

    /**
     * Stop progress tracking for a job
     * @param {string} jobId - The job ID to stop tracking
     */
    function stopProgressTracking(jobId) {
        const wsOrInterval = analyzingJobs.get(jobId);
        if (wsOrInterval) {
            if (wsOrInterval.close && typeof wsOrInterval.close === 'function') {
                // It's a WebSocket instance
                wsOrInterval.close();
                console.log('Stopped WebSocket tracking for job', jobId);
            } else if (wsOrInterval.intervalId) {
                // It's a fallback polling interval
                clearInterval(wsOrInterval.intervalId);
                console.log('Stopped fallback polling for job', jobId);
            }
            analyzingJobs.delete(jobId);
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
            // Update the percentage text - matches job_detail.html structure
            // Structure: <div data-progress-type="in-progress">
            //              <span class="...animate-spin">⟳</span>
            //              <span class="text-gray-900 tracking-wide uppercase">Analyzing... 25%</span>
            //            </div>
            const textSpan = progressTag.querySelector('span.text-gray-900');
            if (textSpan) {
                textSpan.textContent = 'Analyzing... ' + percentage + '%';
                console.log('Updated progress for job', jobId, 'to', percentage + '%');
            } else {
                console.warn('Could not find text span in progress tag for job', jobId);
            }
        } else {
            console.log('Progress tag not found for job', jobId);
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
                console.log('Resuming WebSocket progress tracking for job', jobId);
                startProgressTracking(jobId);
            }
        }
    }

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

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Re-run analysis request failed:', response.status, errorText);
                throw new Error(`Request failed with status ${response.status}`);
            }

            const data = await response.json();

            if (data.success) {
                console.log('Re-run analysis started for job', jobId);
                
                // Reload page immediately to show progress tag and cancel button
                // The backend sets analysis_rerunning=True when the task starts
                // After reload, initProgressTracking() will find the tag and start WebSocket tracking
                // The WebSocket will receive real-time progress updates
                window.location.reload();
            } else {
                const errorMsg = data.error && data.error.message ? data.error.message : 'Failed to re-run analysis';
                showMessageModal('Error', errorMsg);
            }
        } catch (error) {
            console.error('Error re-running analysis:', error);
            showMessageModal('Error', 'Failed to re-run analysis. Please try again.');
        }
    }

    /**
     * Cancel AI analysis for a job
     * @param {string} jobId - The job ID to cancel analysis for
     */
    async function cancelAnalysis(jobId) {
        showConfirmModal('Are you sure you want to cancel the analysis? Results for already processed applicants will be preserved.', async function() {
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
                    console.log('Analysis cancelled for job', jobId);
                    showMessageModal('Success', data.data.message || 'Analysis cancelled successfully.');

                    // Stop progress tracking
                    stopProgressTracking(jobId);

                    // Wait a moment to ensure cancellation flag is set in Redis
                    // Then reload to get fresh data from server
                    setTimeout(() => {
                        window.location.reload();
                    }, 500);
                } else {
                    const errorMsg = data.error && data.error.message ? data.error.message : 'Failed to cancel analysis';
                    showMessageModal('Error', errorMsg);
                }
            } catch (error) {
                console.error('Error cancelling analysis:', error);
                showMessageModal('Error', 'Failed to cancel analysis. Please try again.');
            }
        });
    }

    // Initialize event handlers on page load
    document.addEventListener('DOMContentLoaded', function() {
        // Initialize progress tracking for jobs already in progress
        setTimeout(() => {
            initProgressTracking();
        }, 100);

        // Set up rerun analysis button handler
        const rerunBtn = document.getElementById('rerun-analysis-btn');
        if (rerunBtn) {
            rerunBtn.addEventListener('click', function() {
                const jobId = this.dataset.jobId;
                if (jobId) {
                    showConfirmModal('Are you sure you want to re-run the AI analysis? This will delete all previous results and start fresh. This action cannot be undone.', function() {
                        rerunAnalysis(jobId);
                    });
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

    // Expose functions globally for external use
    window.startProgressTracking = startProgressTracking;
    window.stopProgressTracking = stopProgressTracking;
    window.initProgressTracking = initProgressTracking;
    window.rerunAnalysis = rerunAnalysis;
    window.cancelAnalysis = cancelAnalysis;
    window.closeMessageModal = closeMessageModal;

})();
