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

        // Rerun analysis button handler
        const rerunBtn = document.getElementById('rerun-analysis-btn');
        if (rerunBtn) {
            rerunBtn.addEventListener('click', function() {
                const jobId = this.dataset.jobId;
                if (jobId && confirm('Are you sure you want to re-run the AI analysis? This will delete all previous results and start fresh. This action cannot be undone.')) {
                    rerunAnalysis(jobId);
                }
            });
        }
    }

    /**
     * Re-run AI analysis for a job
     * @param {string} jobId - The job ID to re-run analysis for
     */
    function rerunAnalysis(jobId) {
        // Get CSRF token
        const tokenMeta = document.querySelector('meta[name="csrf-token"]');
        const csrfToken = tokenMeta ? tokenMeta.getAttribute('content') : null;

        fetch('/api/analysis/jobs/' + jobId + '/analysis/re-run/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin',
            body: JSON.stringify({ confirm: true })
        })
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            if (data.success) {
                // Show loading indicator if available
                if (window.AnalysisLoadingIndicator) {
                    const indicator = new window.AnalysisLoadingIndicator();
                    indicator.show(jobId);
                } else {
                    // Fallback: redirect to dashboard
                    alert('Analysis re-run started! Redirecting to dashboard...');
                    window.location.href = '/dashboard/';
                }
            } else {
                const errorMsg = data.error && data.error.message ? data.error.message : 'Failed to re-run analysis';
                alert('Error: ' + errorMsg);
            }
        })
        .catch(function(error) {
            console.error('Error re-running analysis:', error);
            alert('Failed to re-run analysis. Please try again.');
        });
    }

    /**
     * Initialize results list page functionality
     */
    function initResultsList() {
        // Filter functionality
        const applyFiltersBtn = document.getElementById('apply-filters');
        if (applyFiltersBtn) {
            applyFiltersBtn.addEventListener('click', function() {
                // Safely get filter elements with null checks
                var categoryEl = document.getElementById('category-filter');
                var minScoreEl = document.getElementById('min-score');
                var maxScoreEl = document.getElementById('max-score');

                var category = categoryEl ? categoryEl.value : '';
                var minScore = minScoreEl ? minScoreEl.value : '';
                var maxScore = maxScoreEl ? maxScoreEl.value : '';

                // Build URL with only non-empty filter values
                var url = new URL(window.location.origin + window.location.pathname);
                if (category) {
                    url.searchParams.set('category', category);
                }
                if (minScore) {
                    url.searchParams.set('min_score', minScore);
                }
                if (maxScore) {
                    url.searchParams.set('max_score', maxScore);
                }

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
        var modalBody = document.getElementById('modal-body-content');
        var modal = document.getElementById('result-detail-modal');

        fetch('/api/analysis/results/' + resultId + '/')
            .then(function(response) {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(function(data) {
                if (data.success) {
                    var content = buildDetailContent(data.data);
                    if (modalBody) {
                        modalBody.innerHTML = content;
                    }
                    if (modal) {
                        modal.style.display = 'flex';
                    }
                } else {
                    // Show API error message to user
                    var errorMsg = data.error && data.error.message ? data.error.message : 'Failed to load result details';
                    if (modalBody) {
                        modalBody.innerHTML = '<div class="error-message"><p>Error: ' + escapeHtml(errorMsg) + '</p></div>';
                    }
                    if (modal) {
                        modal.style.display = 'flex';
                    }
                }
            })
            .catch(function(error) {
                console.error('Error loading result detail:', error);
                // Show network error message to user
                if (modalBody) {
                    modalBody.innerHTML = '<div class="error-message"><p>Error: Unable to load result details. Please try again.</p></div>';
                }
                if (modal) {
                    modal.style.display = 'flex';
                }
            });
    }

    /**
     * Build detail content HTML
     * @param {Object} data - The result data
     * @returns {string} HTML string
     */
    function buildDetailContent(data) {
        // Safe accessor for nested score values with defaults
        function getScore(value) {
            if (value === null || value === undefined || value === '') {
                return 'N/A';
            }
            return escapeHtml(String(value));
        }

        // Extract scores with null-safe access
        var scores = data.scores || {};
        var overall = scores.overall || {};
        var education = scores.education || {};
        var skills = scores.skills || {};
        var experience = scores.experience || {};
        var supplemental = scores.supplemental || {};

        var overallScore = getScore(overall.score);
        var overallCategory = getScore(overall.category);
        var educationScore = getScore(education.score);
        var skillsScore = getScore(skills.score);
        var experienceScore = getScore(experience.score);
        var supplementalScore = getScore(supplemental.score);
        
        var overallJustification = overall.justification ? escapeHtml(overall.justification) : 'N/A';
        var educationJustification = education.justification ? escapeHtml(education.justification) : 'N/A';
        var skillsJustification = skills.justification ? escapeHtml(skills.justification) : 'N/A';
        var experienceJustification = experience.justification ? escapeHtml(experience.justification) : 'N/A';
        var supplementalJustification = supplemental.justification ? escapeHtml(supplemental.justification) : 'N/A';

        return [
            '<div class="detail-container">',
            '    <!-- Applicant Info Header -->',
            '    <div class="detail-header mb-4 pb-4 border-b border-secondary-text">',
            '        <h4 class="text-xl font-bold text-primary-text mb-2">' + escapeHtml(data.applicant.name) + '</h4>',
            '        <div class="flex gap-4 text-sm text-secondary-text">',
            '            <span>Reference: ' + escapeHtml(data.applicant.reference_number) + '</span>',
            '            <span>Status: ' + escapeHtml(data.status) + '</span>',
            '        </div>',
            '    </div>',
            '',
            '    <!-- Compact Score Summary -->',
            '    <div class="detail-scores mb-4 p-4 bg-code-block-bg rounded-lg">',
            '        <h5 class="text-sm font-semibold text-primary-text mb-3">Overall Assessment</h5>',
            '        <div class="flex items-center gap-4 mb-3">',
            '            <div class="text-center">',
            '                <div class="text-3xl font-bold text-primary-text">' + overallScore + '</div>',
            '                <div class="text-xs text-secondary-text">Overall Score</div>',
            '            </div>',
            '            <div class="text-center">',
            '                <div class="text-lg font-semibold text-primary-text">' + overallCategory + '</div>',
            '                <div class="text-xs text-secondary-text">Category</div>',
            '            </div>',
            '        </div>',
            '        <div class="grid grid-cols-4 gap-2 text-center">',
            '            <div class="p-2 bg-white rounded">',
            '                <div class="text-xs text-secondary-text">Education</div>',
            '                <div class="font-mono font-bold text-primary-text">' + educationScore + '</div>',
            '            </div>',
            '            <div class="p-2 bg-white rounded">',
            '                <div class="text-xs text-secondary-text">Skills</div>',
            '                <div class="font-mono font-bold text-primary-text">' + skillsScore + '</div>',
            '            </div>',
            '            <div class="p-2 bg-white rounded">',
            '                <div class="text-xs text-secondary-text">Experience</div>',
            '                <div class="font-mono font-bold text-primary-text">' + experienceScore + '</div>',
            '            </div>',
            '            <div class="p-2 bg-white rounded">',
            '                <div class="text-xs text-secondary-text">Supplemental</div>',
            '                <div class="font-mono font-bold text-primary-text">' + supplementalScore + '</div>',
            '            </div>',
            '        </div>',
            '    </div>',
            '',
            '    <!-- Justifications Accordion -->',
            '    <div class="detail-justifications">',
            '        <h5 class="text-sm font-semibold text-primary-text mb-3">Detailed Justifications</h5>',
            '        <div class="flex flex-col gap-2">',
            '            <div class="border border-secondary-text rounded overflow-hidden">',
            '                <button class="justification-toggle w-full flex justify-between items-center p-3 bg-code-block-bg text-left text-sm font-semibold text-primary-text" type="button" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === \'none\' ? \'block\' : \'none\'">',
            '                    <span>📚 Education Justification</span>',
            '                    <span class="text-xs">▼</span>',
            '                </button>',
            '                <div class="justification-content p-3 bg-white text-sm text-secondary-text" style="display: none;">',
            '                    <p>' + educationJustification + '</p>',
            '                </div>',
            '            </div>',
            '            <div class="border border-secondary-text rounded overflow-hidden">',
            '                <button class="justification-toggle w-full flex justify-between items-center p-3 bg-code-block-bg text-left text-sm font-semibold text-primary-text" type="button" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === \'none\' ? \'block\' : \'none\'">',
            '                    <span>🛠️ Skills Justification</span>',
            '                    <span class="text-xs">▼</span>',
            '                </button>',
            '                <div class="justification-content p-3 bg-white text-sm text-secondary-text" style="display: none;">',
            '                    <p>' + skillsJustification + '</p>',
            '                </div>',
            '            </div>',
            '            <div class="border border-secondary-text rounded overflow-hidden">',
            '                <button class="justification-toggle w-full flex justify-between items-center p-3 bg-code-block-bg text-left text-sm font-semibold text-primary-text" type="button" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === \'none\' ? \'block\' : \'none\'">',
            '                    <span>💼 Experience Justification</span>',
            '                    <span class="text-xs">▼</span>',
            '                </button>',
            '                <div class="justification-content p-3 bg-white text-sm text-secondary-text" style="display: none;">',
            '                    <p>' + experienceJustification + '</p>',
            '                </div>',
            '            </div>',
            '            <div class="border border-secondary-text rounded overflow-hidden">',
            '                <button class="justification-toggle w-full flex justify-between items-center p-3 bg-code-block-bg text-left text-sm font-semibold text-primary-text" type="button" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === \'none\' ? \'block\' : \'none\'">',
            '                    <span>➕ Supplemental Justification</span>',
            '                    <span class="text-xs">▼</span>',
            '                </button>',
            '                <div class="justification-content p-3 bg-white text-sm text-secondary-text" style="display: none;">',
            '                    <p>' + supplementalJustification + '</p>',
            '                </div>',
            '            </div>',
            '            <div class="border border-secondary-text rounded overflow-hidden">',
            '                <button class="justification-toggle w-full flex justify-between items-center p-3 bg-accent-cta text-left text-sm font-semibold text-cta-text" type="button" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === \'none\' ? \'block\' : \'none\'">',
            '                    <span>📊 Overall Justification</span>',
            '                    <span class="text-xs">▼</span>',
            '                </button>',
            '                <div class="justification-content p-3 bg-white text-sm text-primary-text font-medium" style="display: block;">',
            '                    <p>' + overallJustification + '</p>',
            '                </div>',
            '            </div>',
            '        </div>',
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
                // data-accordion now contains the full unique ID (e.g., "education-abc123")
                const contentId = 'accordion-' + this.dataset.accordion;
                const content = document.getElementById(contentId);
                const isActive = this.classList.contains('active');

                // Close all accordions
                document.querySelectorAll('.accordion-header').forEach(function(h) {
                    h.classList.remove('active');
                    h.setAttribute('aria-expanded', 'false');
                });
                document.querySelectorAll('.accordion-content').forEach(function(c) {
                    c.style.display = 'none';
                });

                // Toggle current
                if (!isActive && content) {
                    this.classList.add('active');
                    this.setAttribute('aria-expanded', 'true');
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
        this.displayedMilestones = new Set();

        // Bind cancel button click handler once in constructor
        var self = this;
        if (this.cancelBtn) {
            this.cancelBtn.addEventListener('click', function() {
                self.cancelAnalysis();
            });
        }
    }

    /**
     * Show the loading indicator
     * @param {string} jobId - The job ID to analyze
     */
    AnalysisLoadingIndicator.prototype.show = function(jobId) {
        this.jobId = jobId;
        this.displayedMilestones.clear();
        if (this.container) {
            this.container.style.display = 'block';
        }
        this.addTerminalLine('Starting analysis for job ' + jobId + '...');
        this.startPolling();
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
        if (percentage === 25 && !this.displayedMilestones.has('25')) {
            this.addTerminalLine('Processing... 25% complete');
            this.displayedMilestones.add('25');
        } else if (percentage === 50 && !this.displayedMilestones.has('50')) {
            this.addTerminalLine('Processing... 50% complete');
            this.displayedMilestones.add('50');
        } else if (percentage === 75 && !this.displayedMilestones.has('75')) {
            this.addTerminalLine('Processing... 75% complete');
            this.displayedMilestones.add('75');
        } else if (percentage >= 90 && percentage < 100 && !this.displayedMilestones.has('finalizing')) {
            this.addTerminalLine('Finalizing analysis...');
            this.displayedMilestones.add('finalizing');
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
        var retryCount = 0;
        var maxRetries = 5;

        var pollStatus = function() {
            fetch('/api/analysis/jobs/' + self.jobId + '/analysis/status/', {
                method: 'GET',
                credentials: 'include'  // Include cookies for authentication
            })
                .then(function(response) {
                    if (!response.ok) {
                        throw new Error('Network response was not ok: ' + response.status + ' ' + response.statusText);
                    }
                    return response.json();
                })
                .then(function(data) {
                    retryCount = 0;  // Reset retry count on success

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
                        } else if (data.data.status === 'failed') {
                            self.addTerminalLine('Analysis failed. Check logs for details.');
                            setTimeout(function() { self.hide(); }, 3000);
                            self.stopPolling();
                        }
                    } else {
                        // API returned success=false
                        var errorMsg = data.error ? data.error.message : 'Unknown API error';
                        console.error('API error:', errorMsg);
                        self.addTerminalLine('Error: ' + errorMsg);
                    }
                })
                .catch(function(error) {
                    retryCount++;
                    console.error('Error polling status (attempt ' + retryCount + '):', error);
                    
                    if (retryCount >= maxRetries) {
                        self.addTerminalLine('Error: Failed to fetch status after ' + maxRetries + ' attempts');
                        self.addTerminalLine('The analysis may still be running. Refresh the page to check status.');
                        self.stopPolling();
                    } else {
                        self.addTerminalLine('Warning: Status fetch failed (retry ' + retryCount + '/' + maxRetries + ')');
                    }
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

        fetch('/api/analysis/jobs/' + this.jobId + '/analysis/cancel/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCSRFToken()
            }
        })
        .then(function(response) {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.status + ' ' + response.statusText);
            }
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
