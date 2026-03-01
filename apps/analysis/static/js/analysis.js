/**
 * AI Analysis Module JavaScript
 * Handles view toggling, filtering, and result details
 */

(function() {
    'use strict';

    /**
     * Initialize reporting page functionality
     */
    function initReportingPage() {
        const toggleBtn = document.getElementById('toggle-view-btn');
        const tableView = document.getElementById('table-view');
        const comparisonView = document.getElementById('comparison-view');

        if (toggleBtn && tableView && comparisonView) {
            toggleBtn.addEventListener('click', function() {
                const isTableVisible = tableView.style.display !== 'none';

                if (isTableVisible) {
                    tableView.style.display = 'none';
                    comparisonView.style.display = 'block';
                    toggleBtn.textContent = 'Switch to Table View';
                } else {
                    tableView.style.display = 'block';
                    comparisonView.style.display = 'none';
                    toggleBtn.textContent = 'Switch to Comparison View';
                }
            });
        }
    }

    /**
     * Initialize results list page functionality
     */
    function initResultsList() {
        // Filter functionality
        const applyFiltersBtn = document.getElementById('apply-filters');
        if (applyFiltersBtn) {
            applyFiltersBtn.addEventListener('click', function() {
                const category = document.getElementById('category-filter').value;
                const minScore = document.getElementById('min-score').value;
                const maxScore = document.getElementById('max-score').value;

                let url = new URL(window.location.href);
                if (category) url.searchParams.set('category', category);
                else url.searchParams.delete('category');
                if (minScore) url.searchParams.set('min_score', minScore);
                else url.searchParams.delete('min_score');
                if (maxScore) url.searchParams.set('max_score', maxScore);
                else url.searchParams.delete('max_score');

                window.location.href = url.toString();
            });
        }

        // View detail modal buttons
        document.querySelectorAll('.btn-view-detail').forEach(function(btn) {
            btn.addEventListener('click', function() {
                const resultId = this.dataset.resultId;
                openResultDetail(resultId);
            });
        });

        // Modal close button
        const modalClose = document.querySelector('.modal-close');
        if (modalClose) {
            modalClose.addEventListener('click', function() {
                const modal = document.getElementById('result-detail-modal');
                if (modal) {
                    modal.style.display = 'none';
                }
            });
        }

        // Refresh button
        const refreshBtn = document.getElementById('refresh-results');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', function() {
                window.location.reload();
            });
        }
    }

    /**
     * Open result detail modal
     * @param {string} resultId - The result ID to fetch details for
     */
    function openResultDetail(resultId) {
        fetch('/analysis/api/analysis/results/' + resultId + '/')
            .then(function(response) {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(function(data) {
                if (data.success) {
                    const content = buildDetailContent(data.data);
                    const modalBody = document.getElementById('modal-body-content');
                    if (modalBody) {
                        modalBody.innerHTML = content;
                    }
                    const modal = document.getElementById('result-detail-modal');
                    if (modal) {
                        modal.style.display = 'flex';
                    }
                }
            })
            .catch(function(error) {
                console.error('Error loading result detail:', error);
            });
    }

    /**
     * Build detail content HTML
     * @param {Object} data - The result data
     * @returns {string} HTML string
     */
    function buildDetailContent(data) {
        return [
            '<div class="detail-header">',
            '    <h4>' + escapeHtml(data.applicant.name) + '</h4>',
            '    <p>Reference: ' + escapeHtml(data.applicant.reference_number) + '</p>',
            '    <p>Status: ' + escapeHtml(data.status) + '</p>',
            '</div>',
            '',
            '<div class="detail-scores">',
            '    <div class="score-card">',
            '        <h5>Overall Score</h5>',
            '        <div class="overall-score">' + data.scores.overall.score + '</div>',
            '        <div class="category">' + escapeHtml(data.scores.overall.category) + '</div>',
            '    </div>',
            '',
            '    <div class="metrics-grid">',
            '        <div class="metric-card">',
            '            <h6>Education</h6>',
            '            <div class="metric-score">' + data.scores.education.score + '</div>',
            '        </div>',
            '        <div class="metric-card">',
            '            <h6>Skills</h6>',
            '            <div class="metric-score">' + data.scores.skills.score + '</div>',
            '        </div>',
            '        <div class="metric-card">',
            '            <h6>Experience</h6>',
            '            <div class="metric-score">' + data.scores.experience.score + '</div>',
            '        </div>',
            '        <div class="metric-card">',
            '            <h6>Supplemental</h6>',
            '            <div class="metric-score">' + data.scores.supplemental.score + '</div>',
            '        </div>',
            '    </div>',
            '</div>',
            '',
            '<div class="detail-justifications">',
            '    <h5>Justifications</h5>',
            '    <div class="justification-item">',
            '        <strong>Overall:</strong>',
            '        <p>' + escapeHtml(data.scores.overall.justification) + '</p>',
            '    </div>',
            '</div>'
        ].join('\n');
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Close modal when clicking outside
     * @param {Event} event - Click event
     */
    function handleModalOutsideClick(event) {
        const modal = document.getElementById('result-detail-modal');
        if (modal && event.target === modal) {
            modal.style.display = 'none';
        }
    }

    /**
     * Initialize all functionality on DOM ready
     */
    function init() {
        initReportingPage();
        initResultsList();

        // Global modal outside click handler
        document.addEventListener('click', handleModalOutsideClick);
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose functions globally if needed
    window.AnalysisModule = {
        openResultDetail: openResultDetail
    };

})();

/**
 * Justifications Accordion Controller
 */
(function() {
    'use strict';

    function initAccordions() {
        document.querySelectorAll('.accordion-header').forEach(function(header) {
            header.addEventListener('click', function() {
                const contentId = 'accordion-' + this.dataset.accordion;
                const content = document.getElementById(contentId);
                const isActive = this.classList.contains('active');

                // Close all accordions
                document.querySelectorAll('.accordion-header').forEach(function(h) {
                    h.classList.remove('active');
                });
                document.querySelectorAll('.accordion-content').forEach(function(c) {
                    c.style.display = 'none';
                });

                // Toggle current
                if (!isActive && content) {
                    this.classList.add('active');
                    content.style.display = 'block';
                }
            });
        });
    }

    // Initialize accordions on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAccordions);
    } else {
        initAccordions();
    }
})();

/**
 * Terminal Loading Indicator Controller
 */
(function() {
    'use strict';

    /**
     * Analysis Loading Indicator Class
     * @constructor
     */
    function AnalysisLoadingIndicator() {
        this.container = document.getElementById('analysis-loading-indicator');
        this.progressFill = document.getElementById('progress-fill');
        this.progressPercentage = document.getElementById('progress-percentage');
        this.statProcessed = document.getElementById('stat-processed');
        this.statTotal = document.getElementById('stat-total');
        this.statRemaining = document.getElementById('stat-remaining');
        this.terminalLines = document.getElementById('terminal-lines');
        this.cancelBtn = document.getElementById('cancel-analysis-btn');

        this.pollingInterval = null;
        this.jobId = null;
    }

    /**
     * Show the loading indicator
     * @param {string} jobId - The job ID to analyze
     */
    AnalysisLoadingIndicator.prototype.show = function(jobId) {
        this.jobId = jobId;
        if (this.container) {
            this.container.style.display = 'block';
        }
        this.addTerminalLine('Starting analysis for job ' + jobId + '...');
        this.startPolling();

        var self = this;
        if (this.cancelBtn) {
            this.cancelBtn.addEventListener('click', function() {
                self.cancelAnalysis();
            });
        }
    };

    /**
     * Hide the loading indicator
     */
    AnalysisLoadingIndicator.prototype.hide = function() {
        if (this.container) {
            this.container.style.display = 'none';
        }
        this.stopPolling();
    };

    /**
     * Update progress display
     * @param {number} processed - Number of processed applicants
     * @param {number} total - Total number of applicants
     */
    AnalysisLoadingIndicator.prototype.updateProgress = function(processed, total) {
        var percentage = total > 0 ? Math.round((processed / total) * 100) : 0;
        var remaining = total - processed;

        if (this.progressFill) {
            this.progressFill.style.width = percentage + '%';
        }
        if (this.progressPercentage) {
            this.progressPercentage.textContent = percentage + '%';
        }
        if (this.statProcessed) {
            this.statProcessed.textContent = processed;
        }
        if (this.statTotal) {
            this.statTotal.textContent = total;
        }
        if (this.statRemaining) {
            this.statRemaining.textContent = remaining;
        }

        // Add status updates at milestones
        if (percentage === 25 || percentage === 50 || percentage === 75) {
            this.addTerminalLine('Processing... ' + percentage + '% complete');
        } else if (percentage >= 90 && percentage < 100) {
            this.addTerminalLine('Finalizing analysis...');
        }
    };

    /**
     * Add a line to the terminal output
     * @param {string} message - The message to display
     */
    AnalysisLoadingIndicator.prototype.addTerminalLine = function(message) {
        if (!this.terminalLines) return;

        var line = document.createElement('div');
        line.className = 'terminal-line';
        line.innerHTML = '<span class="prompt">$</span>' +
            '<span class="command">' + escapeHtml(message) + '</span>';
        this.terminalLines.appendChild(line);
        this.terminalLines.scrollTop = this.terminalLines.scrollHeight;
    };

    /**
     * Start polling for analysis status
     */
    AnalysisLoadingIndicator.prototype.startPolling = function() {
        var self = this;

        var pollStatus = function() {
            fetch('/analysis/api/jobs/' + self.jobId + '/analysis/status/')
                .then(function(response) {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(function(data) {
                    if (data.success) {
                        self.updateProgress(
                            data.data.processed_count,
                            data.data.total_count
                        );

                        if (data.data.status === 'completed') {
                            self.addTerminalLine('Analysis completed successfully!');
                            setTimeout(function() { self.hide(); }, 2000);
                            self.stopPolling();

                            // Trigger page reload or redirect
                            setTimeout(function() {
                                window.location.reload();
                            }, 2500);
                        } else if (data.data.status === 'cancelled') {
                            self.addTerminalLine('Analysis cancelled by user.');
                            setTimeout(function() { self.hide(); }, 2000);
                            self.stopPolling();
                        }
                    }
                })
                .catch(function(error) {
                    console.error('Error polling status:', error);
                    self.addTerminalLine('Error: Failed to fetch status');
                });
        };

        // Initial poll
        pollStatus();

        // Continue polling every 2 seconds
        this.pollingInterval = setInterval(pollStatus, 2000);
    };

    /**
     * Stop polling for analysis status
     */
    AnalysisLoadingIndicator.prototype.stopPolling = function() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    };

    /**
     * Cancel the analysis
     */
    AnalysisLoadingIndicator.prototype.cancelAnalysis = function() {
        if (!confirm('Are you sure you want to cancel the analysis? Progress will be preserved for completed applicants.')) {
            return;
        }

        var self = this;
        this.addTerminalLine('Cancelling analysis...');

        fetch('/analysis/api/jobs/' + this.jobId + '/analysis/cancel/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCSRFToken()
            }
        })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            if (data.success) {
                self.addTerminalLine(data.data.message);
                self.stopPolling();
                setTimeout(function() { self.hide(); }, 2000);
            } else {
                self.addTerminalLine('Error: ' + data.error.message);
            }
        })
        .catch(function(error) {
            console.error('Error cancelling analysis:', error);
            self.addTerminalLine('Error: Failed to cancel analysis');
        });
    };

    /**
     * Get CSRF token from cookie
     * @returns {string|null} CSRF token
     */
    AnalysisLoadingIndicator.prototype.getCSRFToken = function() {
        var name = 'csrftoken';
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Export for use in other scripts
    window.AnalysisLoadingIndicator = AnalysisLoadingIndicator;
})();
