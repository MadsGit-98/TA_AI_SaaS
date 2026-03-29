/**
 * Bulk Upload JavaScript
 * Handles drag-and-drop, file upload, WebSocket progress tracking, and polling fallback
 */

class BulkUploadManager {
    constructor(config) {
        this.config = config;
        this.files = [];
        this.batchId = null;
        this.ws = null;
        this.pollingInterval = null;
        this.isUploading = false;
        this.uploadedFiles = [];
        this.duplicates = [];
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.updateLimitsDisplay();
    }

    bindEvents() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const startUploadBtn = document.getElementById('start-upload-btn');
        const cancelUploadBtn = document.getElementById('cancel-upload-btn');
        const validateBtn = document.getElementById('validate-btn');
        const clearAllBtn = document.getElementById('clear-all-btn');
        const commitBtn = document.getElementById('commit-btn');
        const goBackBtn = document.getElementById('go-back-btn');
        const modalClose = document.getElementById('modal-close');
        const skipAllBtn = document.getElementById('skip-all-btn');
        const includeAllBtn = document.getElementById('include-all-btn');
        const confirmDecisionsBtn = document.getElementById('confirm-decisions-btn');

        // Drop zone events
        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => this.handleDragOver(e));
        dropZone.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        dropZone.addEventListener('drop', (e) => this.handleDrop(e));
        fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        // Control buttons
        if (startUploadBtn) {
            startUploadBtn.addEventListener('click', () => this.startUpload());
        }
        if (cancelUploadBtn) {
            cancelUploadBtn.addEventListener('click', () => this.cancelUpload());
        }
        if (validateBtn) {
            validateBtn.addEventListener('click', () => this.validateBatch());
        }
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', () => this.clearAll());
        }
        if (commitBtn) {
            commitBtn.addEventListener('click', () => this.commitBatch());
        }
        if (goBackBtn) {
            goBackBtn.addEventListener('click', () => this.goBack());
        }

        // Modal events
        if (modalClose) {
            modalClose.addEventListener('click', () => this.closeModal());
        }
        if (skipAllBtn) {
            skipAllBtn.addEventListener('click', () => this.skipAll());
        }
        if (includeAllBtn) {
            includeAllBtn.addEventListener('click', () => this.includeAll());
        }
        if (confirmDecisionsBtn) {
            confirmDecisionsBtn.addEventListener('click', () => this.confirmDecisions());
        }

        // Close modal on outside click
        const modal = document.getElementById('duplicate-modal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal();
                }
            });
        }
    }

    // Drag and Drop Handlers
    handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        e.currentTarget.classList.add('drag-over');
    }

    handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        e.currentTarget.classList.remove('drag-over');
    }

    handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        e.currentTarget.classList.remove('drag-over');
        
        const droppedFiles = Array.from(e.dataTransfer.files);
        this.addFiles(droppedFiles);
    }

    handleFileSelect(e) {
        const selectedFiles = Array.from(e.target.files);
        this.addFiles(selectedFiles);
        e.target.value = ''; // Reset input
    }

    addFiles(newFiles) {
        const controls = document.getElementById('upload-controls');
        const fileListSection = document.getElementById('file-list-section');
        
        for (const file of newFiles) {
            // Validate file
            const validation = this.validateFile(file);
            if (!validation.valid) {
                alert(`File "${file.name}": ${validation.error}`);
                continue;
            }

            // Check for duplicates in current selection
            const exists = this.files.some(f => f.name === file.name && f.size === file.size);
            if (exists) {
                continue;
            }

            this.files.push({
                file: file,
                id: null,
                status: 'pending',
                progress: 0
            });
        }

        this.updateFileList();
        
        if (this.files.length > 0) {
            controls.style.display = 'flex';
            fileListSection.style.display = 'block';
        }
        
        this.updateLimitsDisplay();
    }

    validateFile(file) {
        const { minFileSize, maxFileSize } = this.config;
        
        // Check file type
        const ext = file.name.split('.').pop().toLowerCase();
        if (!['pdf', 'docx'].includes(ext)) {
            return {
                valid: false,
                error: 'Only PDF and DOCX files are accepted'
            };
        }

        // Check file size
        if (file.size < minFileSize) {
            return {
                valid: false,
                error: `File size (${this.formatFileSize(file.size)}) is below minimum (${this.formatFileSize(minFileSize)})`
            };
        }

        if (file.size > maxFileSize) {
            return {
                valid: false,
                error: `File size (${this.formatFileSize(file.size)}) exceeds maximum (${this.formatFileSize(maxFileSize)})`
            };
        }

        return { valid: true };
    }

    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    updateFileList() {
        const fileList = document.getElementById('file-list');
        const totalFiles = document.getElementById('total-files');
        const fileCount = document.getElementById('file-count');
        
        fileList.innerHTML = '';
        
        this.files.forEach((fileObj, index) => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.innerHTML = `
                <div class="file-info">
                    <svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                    <span class="file-name">${fileObj.file.name}</span>
                    <span class="file-size">${this.formatFileSize(fileObj.file.size)}</span>
                    ${fileObj.status !== 'pending' ? `<span class="file-status ${fileObj.status}">${fileObj.status}</span>` : ''}
                </div>
                ${fileObj.status === 'pending' ? `
                    <div class="file-actions">
                        <button class="btn-remove" onclick="bulkUpload.removeFile(${index})">&times;</button>
                    </div>
                ` : ''}
            `;
            fileList.appendChild(item);
        });
        
        if (totalFiles) totalFiles.textContent = this.files.length;
        if (fileCount) fileCount.textContent = this.files.length;
    }

    removeFile(index) {
        this.files.splice(index, 1);
        this.updateFileList();
        
        if (this.files.length === 0) {
            document.getElementById('upload-controls').style.display = 'none';
            document.getElementById('file-list-section').style.display = 'none';
        }
        
        this.updateLimitsDisplay();
    }

    updateLimitsDisplay() {
        const remaining = this.config.maxFilesPerBatch - this.files.length;
        const limitBadges = document.querySelectorAll('.limit-badge');
        if (limitBadges.length >= 3) {
            limitBadges[2].querySelector('.limit-value').textContent = 
                `${this.files.length}/${this.config.maxFilesPerBatch}`;
        }
    }

    async startUpload() {
        if (this.isUploading) return;
        
        this.isUploading = true;
        const startBtn = document.getElementById('start-upload-btn');
        startBtn.disabled = true;
        startBtn.textContent = 'Uploading...';

        try {
            // Initialize batch
            await this.initBatch();
            
            // Connect WebSocket
            this.connectWebSocket();
            
            // Upload files
            const progressSection = document.getElementById('progress-section');
            progressSection.style.display = 'block';
            
            for (let i = 0; i < this.files.length; i++) {
                await this.uploadFile(i);
            }
            
            // Show actions
            document.getElementById('upload-actions').style.display = 'flex';
            startBtn.textContent = 'Upload Complete';
            
        } catch (error) {
            console.error('Upload error:', error);
            alert('Upload failed: ' + error.message);
            startBtn.disabled = false;
            startBtn.textContent = `Start Upload (${this.files.length} files)`;
        }
        
        this.isUploading = false;
    }

    async initBatch() {
        const response = await fetch('/api/applications/bulk-upload/init/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.config.csrfToken
            },
            body: JSON.stringify({
                job_listing_id: this.config.jobListingId
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to initialize batch');
        }
        
        const data = await response.json();
        this.batchId = data.batch_id;
        
        // Update WebSocket URL with batch ID
        this.config.wsUrl = this.config.wsUrl + this.batchId + '/';
    }

    connectWebSocket() {
        try {
            this.ws = new WebSocket(this.config.wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.startPolling();
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket closed');
                if (!this.wsClosedManually) {
                    this.startPolling();
                }
            };
            
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
            this.startPolling();
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'file_progress':
                this.updateFileProgress(data.file_id, data.status, data.progress_percent);
                break;
            case 'batch_progress':
                this.updateBatchProgress(data);
                break;
            case 'validation_complete':
                this.handleValidationComplete(data);
                break;
            case 'error':
                this.handleError(data);
                break;
        }
    }

    startPolling() {
        console.log('Starting polling fallback');
        this.pollingInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/applications/bulk-upload/status/${this.batchId}/`, {
                    method: 'GET',
                    headers: {
                        'X-CSRFToken': this.config.csrfToken
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    this.updateBatchProgress(data.progress);
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 2000);
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    async uploadFile(index) {
        const fileObj = this.files[index];
        const formData = new FormData();
        formData.append('batch_id', this.batchId);
        formData.append('file', fileObj.file);
        
        try {
            const response = await fetch('/api/applications/bulk-upload/upload/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.config.csrfToken
                },
                body: formData
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || error.error || 'Upload failed');
            }
            
            const data = await response.json();
            fileObj.id = data.file_id;
            fileObj.status = 'success';
            fileObj.hash = data.file_hash;
            
            this.updateFileList();
            this.updateProgress();
            
        } catch (error) {
            console.error('File upload error:', error);
            fileObj.status = 'error';
            fileObj.error = error.message;
            this.updateFileList();
        }
    }

    updateProgress() {
        const uploaded = this.files.filter(f => f.status === 'success').length;
        const total = this.files.length;
        const percent = Math.round((uploaded / total) * 100);
        
        document.getElementById('progress-fill').style.width = percent + '%';
        document.getElementById('progress-text').textContent = percent + '%';
        document.getElementById('uploaded-count').textContent = uploaded;
    }

    updateFileProgress(fileId, status, progress) {
        const fileObj = this.files.find(f => f.id === fileId);
        if (fileObj) {
            fileObj.status = status;
            fileObj.progress = progress;
            this.updateFileList();
        }
    }

    updateBatchProgress(progress) {
        if (progress) {
            document.getElementById('uploaded-count').textContent = progress.files_uploaded || 0;
            document.getElementById('validated-count').textContent = progress.files_validated || 0;
            document.getElementById('error-count').textContent = progress.files_with_errors || 0;
        }
    }

    async validateBatch() {
        const validateBtn = document.getElementById('validate-btn');
        validateBtn.disabled = true;
        validateBtn.textContent = 'Checking...';
        
        try {
            const response = await fetch('/api/applications/bulk-upload/validate/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.config.csrfToken
                },
                body: JSON.stringify({
                    batch_id: this.batchId
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Validation failed');
            }
            
            const data = await response.json();
            
            if (data.duplicates && data.duplicates.length > 0) {
                this.showDuplicateModal(data);
            } else {
                this.showCommitSection(data);
            }
            
        } catch (error) {
            console.error('Validation error:', error);
            alert('Validation failed: ' + error.message);
        } finally {
            validateBtn.disabled = false;
            validateBtn.textContent = 'Check for Duplicates';
        }
    }

    showDuplicateModal(data) {
        const modal = document.getElementById('duplicate-modal');
        const duplicateList = document.getElementById('duplicate-list');
        const duplicateCount = document.getElementById('duplicate-count');
        
        this.duplicates = data.duplicates;
        duplicateCount.textContent = data.duplicates.length;
        
        duplicateList.innerHTML = '';
        data.duplicates.forEach((dup, index) => {
            const item = document.createElement('div');
            item.className = 'duplicate-item';
            item.innerHTML = `
                <div class="duplicate-info">
                    <div class="duplicate-filename">${dup.filename}</div>
                    <div class="duplicate-type">Duplicate type: ${dup.duplicate_type}</div>
                </div>
                <div class="duplicate-item-actions">
                    <button class="btn btn-sm btn-secondary" onclick="bulkUpload.setDecision('${dup.file_id}', 'skip')">Skip</button>
                    <button class="btn btn-sm btn-primary" onclick="bulkUpload.setDecision('${dup.file_id}', 'include')">Include</button>
                </div>
            `;
            duplicateList.appendChild(item);
        });
        
        modal.style.display = 'flex';
    }

    setDecision(fileId, action) {
        // Store decision for later submission
        if (!this.decisions) {
            this.decisions = [];
        }
        
        const existingIndex = this.decisions.findIndex(d => d.file_id === fileId);
        if (existingIndex >= 0) {
            this.decisions[existingIndex].action = action;
        } else {
            this.decisions.push({ file_id: fileId, action: action });
        }
    }

    skipAll() {
        this.duplicates.forEach(dup => {
            this.setDecision(dup.file_id, 'skip');
        });
        alert('All duplicates marked as Skip');
    }

    includeAll() {
        this.duplicates.forEach(dup => {
            this.setDecision(dup.file_id, 'include');
        });
        alert('All duplicates marked as Include');
    }

    async confirmDecisions() {
        if (!this.decisions || this.decisions.length === 0) {
            alert('Please make decisions for all duplicates');
            return;
        }
        
        try {
            const response = await fetch('/api/applications/bulk-upload/decisions/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.config.csrfToken
                },
                body: JSON.stringify({
                    batch_id: this.batchId,
                    decisions: this.decisions
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to save decisions');
            }
            
            this.closeModal();
            
            const data = await response.json();
            this.showCommitSection({
                total_files: data.files_to_process,
                files_skipped: data.files_skipped
            });
            
        } catch (error) {
            console.error('Decision error:', error);
            alert('Failed to save decisions: ' + error.message);
        }
    }

    closeModal() {
        const modal = document.getElementById('duplicate-modal');
        modal.style.display = 'none';
    }

    showCommitSection(data) {
        const commitSection = document.getElementById('commit-section');
        const filesToCommit = document.getElementById('files-to-commit');
        
        filesToCommit.textContent = data.total_files || this.files.length;
        commitSection.style.display = 'block';
        
        // Hide validate button
        document.getElementById('validate-btn').style.display = 'none';
    }

    async commitBatch() {
        const commitBtn = document.getElementById('commit-btn');
        commitBtn.disabled = true;
        commitBtn.textContent = 'Processing...';
        
        try {
            const response = await fetch('/api/applications/bulk-upload/commit/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.config.csrfToken
                },
                body: JSON.stringify({
                    batch_id: this.batchId
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Commit failed');
            }
            
            const data = await response.json();
            
            // Redirect to summary page
            window.location.href = `/applications/bulk-upload/summary/${this.batchId}/`;
            
        } catch (error) {
            console.error('Commit error:', error);
            alert('Commit failed: ' + error.message);
            commitBtn.disabled = false;
            commitBtn.textContent = 'Commit and Create Applicants';
        }
    }

    goBack() {
        document.getElementById('commit-section').style.display = 'none';
        document.getElementById('validate-btn').style.display = 'inline-block';
    }

    cancelUpload() {
        if (confirm('Are you sure you want to cancel this upload? All uploaded files will be deleted.')) {
            if (this.batchId) {
                fetch(`/api/applications/bulk-upload/cancel/${this.batchId}/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': this.config.csrfToken
                    }
                }).catch(console.error);
            }
            
            this.closeWebSocket();
            this.stopPolling();
            this.files = [];
            this.batchId = null;
            this.updateFileList();
            document.getElementById('upload-controls').style.display = 'none';
            document.getElementById('file-list-section').style.display = 'none';
            document.getElementById('progress-section').style.display = 'none';
            document.getElementById('upload-actions').style.display = 'none';
            document.getElementById('commit-section').style.display = 'none';
        }
    }

    clearAll() {
        if (confirm('Are you sure you want to clear all files?')) {
            this.files = [];
            this.updateFileList();
            document.getElementById('upload-controls').style.display = 'none';
            document.getElementById('file-list-section').style.display = 'none';
        }
    }

    closeWebSocket() {
        this.wsClosedManually = true;
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    handleError(data) {
        console.error('Upload error:', data.message);
        alert('Error: ' + data.message);
    }

    handleValidationComplete(data) {
        console.log('Validation complete:', data);
    }
}

// Initialize on page load
let bulkUpload;
document.addEventListener('DOMContentLoaded', function() {
    if (window.bulkUploadConfig) {
        bulkUpload = new BulkUploadManager(window.bulkUploadConfig);
    }
});
