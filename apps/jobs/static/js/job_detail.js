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
     * @param {string} link - The application link to copy
     */
    function copyApplicationLink(link) {
        if (!link) {
            alert('No application link available');
            return;
        }
        navigator.clipboard.writeText(link).then(function() {
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
        document.getElementById('rerun-modal').style.display = 'flex';
    }

    /**
     * Close re-run analysis modal
     */
    function closeRerunModal() {
        document.getElementById('rerun-modal').style.display = 'none';
    }

    /**
     * Confirm re-run analysis
     */
    function confirmRerunAnalysis() {
        var jobId = window.JOB_DETAIL_CONFIG.jobId;
        
        fetch('/dashboard/jobs/' + jobId + '/analysis/re-run/', {
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
                alert(data.data.message);
                closeRerunModal();
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
     * Initiate AI analysis
     */
    function initiateAnalysis() {
        var jobId = window.JOB_DETAIL_CONFIG.jobId;
        
        fetch('/dashboard/jobs/' + jobId + '/analysis/initiate/', {
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
                alert('AI analysis started! ' + data.data.applicant_count + ' applicants will be analyzed.');
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
        // Attach modal outside click handler
        var modal = document.getElementById('rerun-modal');
        if (modal) {
            modal.addEventListener('click', handleModalOutsideClick);
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose functions globally
    window.copyApplicationLink = copyApplicationLink;
    window.openRerunModal = openRerunModal;
    window.closeRerunModal = closeRerunModal;
    window.confirmRerunAnalysis = confirmRerunAnalysis;
    window.initiateAnalysis = initiateAnalysis;

})();
