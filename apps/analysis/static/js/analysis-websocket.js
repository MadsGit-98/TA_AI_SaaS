/**
 * WebSocket Client for AI Analysis Status Updates
 * 
 * Provides real-time analysis progress monitoring via WebSocket connection
 * with automatic reconnection, fallback to polling, and cross-tab synchronization.
 */

(function() {
    'use strict';

    /**
     * WebSocket Connection Manager Class
     * Handles connection lifecycle, reconnection, and message handling
     */
    function AnalysisWebSocket() {
        this.socket = null;
        this.jobId = null;
        this.userId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.baseDelay = 1000; // 1 second
        this.maxDelay = 30000; // 30 seconds
        this.reconnectTimer = null;
        this.connectionState = 'disconnected'; // disconnected, connecting, connected, reconnecting, failed, fallback_mode
        this.fallbackPollingInterval = null;
        this.fallbackPollingDelay = 5000; // 5 seconds
        this.callbacks = {
            onProgress: null,
            onCompleted: null,
            onCancelled: null,
            onFailed: null,
            onStateChanged: null
        };
        
        // Get CSRF token helper
        this.getCsrfToken = function() {
            const tokenMeta = document.querySelector('meta[name="csrf-token"]');
            return tokenMeta ? tokenMeta.getAttribute('content') : null;
        };
    }

    /**
     * Initialize WebSocket connection
     * @param {string} jobId - Job ID to subscribe to
     * @returns {boolean} - True if connection initiated
     */
    AnalysisWebSocket.prototype.connect = function(jobId) {
        var self = this;
        
        if (this.connectionState === 'connected' || this.connectionState === 'connecting') {
            console.log('WebSocket already connected or connecting');
            return false;
        }
        
        this.jobId = jobId;
        this.setConnectionState('connecting');
        
        // Construct WebSocket URL
        var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        var wsUrl = protocol + '//' + window.location.host + '/ws/analysis-notifications/';
        
        try {
            this.socket = new WebSocket(wsUrl);
            
            this.socket.onopen = function(event) {
                console.log('WebSocket connected:', event);
                self.reconnectAttempts = 0;
                self.setConnectionState('connected');
                
                // Subscribe to job updates by sending subscription message
                self.subscribeToJob(jobId);
            };
            
            this.socket.onmessage = function(event) {
                try {
                    var message = JSON.parse(event.data);
                    self.handleMessage(message);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            
            this.socket.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
            
            this.socket.onclose = function(event) {
                console.log('WebSocket closed:', event.code, event.reason);
                self.handleClose(event.code);
            };
            
            return true;
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.setConnectionState('failed');
            this.fallbackToPolling();
            return false;
        }
    };

    /**
     * Subscribe to job analysis updates
     * @param {string} jobId - Job ID to subscribe to
     */
    AnalysisWebSocket.prototype.subscribeToJob = function(jobId) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            // Send subscription message to server
            var subscribeMessage = {
                type: 'subscribe',
                job_id: jobId
            };
            this.socket.send(JSON.stringify(subscribeMessage));
            console.log('Subscribed to job:', jobId);
        } else {
            console.warn('Cannot subscribe - WebSocket not connected');
        }
    };

    /**
     * Handle incoming WebSocket messages
     * @param {Object} message - Parsed message object
     */
    AnalysisWebSocket.prototype.handleMessage = function(message) {
        var self = this;
        var type = message.type;
        var data = message.data;
        
        console.log('Received message:', type, data);
        
        switch (type) {
            case 'subscribed':
                // Acknowledgment from server that we're subscribed to job updates
                console.log('Successfully subscribed to job:', data.job_id);
                break;
                
            case 'analysis_progress':
                if (self.callbacks.onProgress) {
                    self.callbacks.onProgress(data);
                }
                break;
                
            case 'analysis_completed':
                if (self.callbacks.onCompleted) {
                    self.callbacks.onCompleted(data);
                }
                break;
                
            case 'analysis_cancelled':
                if (self.callbacks.onCancelled) {
                    self.callbacks.onCancelled(data);
                }
                break;
                
            case 'analysis_failed':
                if (self.callbacks.onFailed) {
                    self.callbacks.onFailed(data);
                }
                break;
                
            default:
                console.warn('Unknown message type:', type);
        }
    };

    /**
     * Handle WebSocket close event
     * @param {number} closeCode - WebSocket close code
     */
    AnalysisWebSocket.prototype.handleClose = function(closeCode) {
        var self = this;
        
        this.setConnectionState('disconnected');
        
        // Don't reconnect if closed intentionally (code 1000)
        if (closeCode === 1000) {
            console.log('WebSocket closed intentionally');
            return;
        }
        
        // Don't reconnect if authentication failed (code 4003)
        if (closeCode === 4003) {
            console.error('WebSocket authentication failed - redirecting to login');
            return;
        }
        
        // Attempt reconnection
        this.attemptReconnect();
    };

    /**
     * Attempt to reconnect with exponential backoff
     */
    AnalysisWebSocket.prototype.attemptReconnect = function() {
        var self = this;
        
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this.setConnectionState('failed');
            this.fallbackToPolling();
            return;
        }
        
        this.reconnectAttempts++;
        this.setConnectionState('reconnecting');
        
        // Calculate delay with exponential backoff
        var delay = Math.min(this.baseDelay * Math.pow(2, this.reconnectAttempts - 1), this.maxDelay);
        
        console.log('Reconnecting in ' + delay + 'ms (attempt ' + this.reconnectAttempts + '/' + this.maxReconnectAttempts + ')');
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
        
        this.reconnectTimer = setTimeout(function() {
            self.connect(self.jobId);
        }, delay);
    };

    /**
     * Fallback to HTTP polling if WebSocket fails
     */
    AnalysisWebSocket.prototype.fallbackToPolling = function() {
        var self = this;
        
        if (this.fallbackPollingInterval) {
            return; // Already polling
        }
        
        this.setConnectionState('fallback_mode');
        console.log('Falling back to HTTP polling');
        
        // Start polling
        this.fallbackPollingInterval = setInterval(function() {
            if (self.jobId) {
                self.pollAnalysisStatus(self.jobId);
            }
        }, this.fallbackPollingDelay);
    };

    /**
     * Poll analysis status via HTTP
     * @param {string} jobId - Job ID to poll
     */
    AnalysisWebSocket.prototype.pollAnalysisStatus = function(jobId) {
        var self = this;
        
        fetch('/api/analysis/jobs/' + jobId + '/analysis/status/', {
            method: 'GET',
            credentials: 'include'
        })
        .then(function(response) {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Network response was not ok');
        })
        .then(function(data) {
            if (data.success) {
                // Convert polling response to WebSocket message format
                var status = data.data.status;
                
                if (status === 'processing') {
                    if (self.callbacks.onProgress) {
                        self.callbacks.onProgress({
                            job_id: jobId,
                            status: 'processing',
                            progress_percentage: data.data.progress_percentage,
                            processed_count: data.data.processed_count,
                            total_count: data.data.total_count
                        });
                    }
                } else if (status === 'completed') {
                    if (self.callbacks.onCompleted) {
                        self.callbacks.onCompleted({
                            job_id: jobId,
                            status: 'completed',
                            processed_count: data.data.processed_count,
                            total_count: data.data.total_count,
                            analyzed_count: data.data.results_summary ? 
                                (data.data.results_summary.analyzed_count || 0) : 0,
                            unprocessed_count: data.data.results_summary ? 
                                (data.data.results_summary.unprocessed_count || 0) : 0
                        });
                    }
                } else if (status === 'cancelled') {
                    if (self.callbacks.onCancelled) {
                        self.callbacks.onCancelled({
                            job_id: jobId,
                            status: 'cancelled',
                            processed_count: data.data.processed_count,
                            total_count: data.data.total_count,
                            preserved_count: data.data.processed_count
                        });
                    }
                }
            }
        })
        .catch(function(error) {
            console.error('Polling error:', error);
        });
    };

    /**
     * Set connection state and notify callback
     * @param {string} state - New connection state
     */
    AnalysisWebSocket.prototype.setConnectionState = function(state) {
        this.connectionState = state;
        console.log('Connection state:', state);
        
        if (this.callbacks.onStateChanged) {
            this.callbacks.onStateChanged(state);
        }
    };

    /**
     * Register callback for progress updates
     * @param {Function} callback - Callback function
     */
    AnalysisWebSocket.prototype.onProgress = function(callback) {
        this.callbacks.onProgress = callback;
    };

    /**
     * Register callback for completion events
     * @param {Function} callback - Callback function
     */
    AnalysisWebSocket.prototype.onCompleted = function(callback) {
        this.callbacks.onCompleted = callback;
    };

    /**
     * Register callback for cancellation events
     * @param {Function} callback - Callback function
     */
    AnalysisWebSocket.prototype.onCancelled = function(callback) {
        this.callbacks.onCancelled = callback;
    };

    /**
     * Register callback for failure events
     * @param {Function} callback - Callback function
     */
    AnalysisWebSocket.prototype.onFailed = function(callback) {
        this.callbacks.onFailed = callback;
    };

    /**
     * Register callback for connection state changes
     * @param {Function} callback - Callback function
     */
    AnalysisWebSocket.prototype.onStateChanged = function(callback) {
        this.callbacks.onStateChanged = callback;
    };

    /**
     * Close WebSocket connection
     */
    AnalysisWebSocket.prototype.close = function() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        
        if (this.fallbackPollingInterval) {
            clearInterval(this.fallbackPollingInterval);
            this.fallbackPollingInterval = null;
        }
        
        if (this.socket) {
            this.socket.close(1000, 'Client closed');
            this.socket = null;
        }
        
        this.setConnectionState('disconnected');
    };

    /**
     * Get current connection state
     * @returns {string} Current state
     */
    AnalysisWebSocket.prototype.getConnectionState = function() {
        return this.connectionState;
    };

    // Export to global scope
    window.AnalysisWebSocket = AnalysisWebSocket;

    /**
     * Initialize WebSocket on page load
     * Expects window.JOB_ID to be set by the template (for single-job pages)
     * For multi-job pages (dashboard), WebSocket is initialized manually per job
     */
    function initAnalysisWebSocket() {
        var jobId = window.JOB_ID || window.JOB_DETAIL_CONFIG?.jobId;
        
        if (!jobId) {
            // No JOB_ID found - this is likely a multi-job page (dashboard)
            // WebSocket will be initialized manually for each job via startProgressTracking()
            console.log('No JOB_ID found - skipping auto-initialization (multi-job page detected)');
            return;
        }
        
        var ws = new AnalysisWebSocket();
        
        // Set up callbacks
        ws.onProgress(function(data) {
            console.log('Progress update:', data);
            // Update UI with progress data
            if (window.updateAnalysisProgress) {
                window.updateAnalysisProgress(data);
            }
        });
        
        ws.onCompleted(function(data) {
            console.log('Analysis completed:', data);
            // Reload page to show results
            setTimeout(function() {
                window.location.reload();
            }, 2000);
        });
        
        ws.onCancelled(function(data) {
            console.log('Analysis cancelled:', data);
            // Reload page to show updated state
            setTimeout(function() {
                window.location.reload();
            }, 1000);
        });
        
        ws.onFailed(function(data) {
            console.error('Analysis failed:', data);
            alert('Analysis failed: ' + data.error_message);
        });
        
        ws.onStateChanged(function(state) {
            console.log('Connection state changed:', state);
            // Update UI with connection state
            if (window.updateConnectionState) {
                window.updateConnectionState(state);
            }
        });
        
        // Connect to WebSocket
        ws.connect(jobId);
        
        // Store WebSocket instance globally
        window.analysisWebSocket = ws;
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAnalysisWebSocket);
    } else {
        initAnalysisWebSocket();
    }

})();
