/**
 * Bulk Upload JavaScript
 * Handles drag-and-drop and file upload for bulk resume upload
 * Uses the exact same approach as application-form.js
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const startUploadBtn = document.getElementById('start-upload-btn');
    const cancelUploadBtn = document.getElementById('cancel-upload-btn');
    const validateBtn = document.getElementById('validate-btn');
    const clearAllBtn = document.getElementById('clear-all-btn');
    const commitBtn = document.getElementById('commit-btn');
    const goBackBtn = document.getElementById('go-back-btn');
    const uploadControls = document.getElementById('upload-controls');
    const fileListSection = document.getElementById('file-list-section');
    const fileList = document.getElementById('file-list');
    const fileCount = document.getElementById('file-count');
    const totalFiles = document.getElementById('total-files');  // Progress section
    const totalFilesList = document.getElementById('total-files-list');  // File list header
    const filesPerBatch = document.getElementById('files-per-batch');
    const progressSection = document.getElementById('progress-section');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const uploadedCount = document.getElementById('uploaded-count');
    const validatedCount = document.getElementById('validated-count');
    const errorCount = document.getElementById('error-count');
    const uploadActions = document.getElementById('upload-actions');
    const commitSection = document.getElementById('commit-section');
    const filesToCommit = document.getElementById('files-to-commit');
    const duplicateModal = document.getElementById('duplicate-modal');
    const duplicateCount = document.getElementById('duplicate-count');
    const duplicateList = document.getElementById('duplicate-list');
    const skipAllBtn = document.getElementById('skip-all-btn');
    const includeAllBtn = document.getElementById('include-all-btn');
    const confirmDecisionsBtn = document.getElementById('confirm-decisions-btn');
    const modalClose = document.getElementById('modal-close');
    const aiDisclaimer = document.getElementById('ai-disclaimer');

    // Config from data attributes
    const configElement = document.getElementById('bulk-upload-config');
    const config = configElement ? {
        jobListingId: configElement.getAttribute('data-job-listing-id'),
        csrfToken: configElement.getAttribute('data-csrf-token'),
        wsProtocol: configElement.getAttribute('data-ws-protocol'),
        wsHost: configElement.getAttribute('data-ws-host'),
        maxFilesPerBatch: parseInt(configElement.getAttribute('data-max-files-per-batch'), 10) || 100,
        maxBatchCount: parseInt(configElement.getAttribute('data-max-batch-count'), 10) || 3,
        maxTotalResumes: parseInt(configElement.getAttribute('data-max-total-resumes'), 10) || 300,
        minFileSize: parseInt(configElement.getAttribute('data-min-file-size'), 10) || 51200,
        maxFileSize: parseInt(configElement.getAttribute('data-max-file-size'), 10) || 10485760,
        // Get remaining capacity from server-rendered values
        remainingCapacity: parseInt(configElement.getAttribute('data-remaining-capacity'), 10) || 300
    } : {};

    // File validation constants
    const MIN_FILE_SIZE = config.minFileSize || 50 * 1024; // 50KB
    const MAX_FILE_SIZE = config.maxFileSize || 10 * 1024 * 1024; // 10MB
    const ALLOWED_EXTENSIONS = ['pdf', 'docx'];

    // State
    let files = [];
    let batchId = null;
    let ws = null;
    let isUploading = false;
    let uploadedFiles = [];
    let duplicates = [];
    let decisions = [];
    let isProcessing = false;  // Track if async processing is in progress
    let processedFileIds = new Set();  // Track processed file IDs to prevent double-counting

    // Bail out early if critical elements are missing
    if (!dropZone || !fileInput) {
        console.warn('Bulk upload elements not found');
        return;
    }

    // Initialize click handler for drop zone
    dropZone.addEventListener('click', function() {
        fileInput.click();
    });

    // Handle file selection
    fileInput.addEventListener('change', function(e) {
        const selectedFiles = Array.from(e.target.files);
        if (selectedFiles.length > 0) {
            addFiles(selectedFiles);
        }
        // Reset input to allow selecting same file again
        e.target.value = '';
    });

    // Drag and drop handlers
    dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', function(e) {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        const droppedFiles = Array.from(e.dataTransfer.files);
        if (droppedFiles.length > 0) {
            addFiles(droppedFiles);
        }
    });

    // Button handlers
    if (startUploadBtn) {
        startUploadBtn.addEventListener('click', function() {
            startUpload();
        });
    }

    if (cancelUploadBtn) {
        cancelUploadBtn.addEventListener('click', function() {
            cancelUpload();
        });
    }

    if (validateBtn) {
        validateBtn.addEventListener('click', function() {
            validateBatch();
        });
    }

    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', function() {
            clearAll();
        });
    }

    if (commitBtn) {
        commitBtn.addEventListener('click', function() {
            commitBatch();
        });
    }

    if (goBackBtn) {
        goBackBtn.addEventListener('click', function() {
            window.location.href = '/dashboard/';
        });
    }

    // Modal handlers
    if (modalClose) {
        modalClose.addEventListener('click', function() {
            closeModal();
        });
    }

    if (skipAllBtn) {
        skipAllBtn.addEventListener('click', function() {
            skipAll();
        });
    }

    if (includeAllBtn) {
        includeAllBtn.addEventListener('click', function() {
            includeAll();
        });
    }

    if (confirmDecisionsBtn) {
        confirmDecisionsBtn.addEventListener('click', function() {
            confirmDecisions();
        });
    }

    // Close modal on outside click
    if (duplicateModal) {
        duplicateModal.addEventListener('click', function(e) {
            if (e.target === duplicateModal) {
                closeModal();
            }
        });
    }

    /**
     * Validate file locally
     */
    function validateFile(file) {
        // Check file extension
        const extension = file.name.split('.').pop().toLowerCase();
        if (!ALLOWED_EXTENSIONS.includes(extension)) {
            return {
                valid: false,
                error: `Unsupported file format '.${extension}'. Only PDF and DOCX files are accepted.`
            };
        }

        // Check file size
        if (file.size < MIN_FILE_SIZE) {
            return {
                valid: false,
                error: `File size (${formatFileSize(file.size)}) is below minimum (50KB). Please upload a larger file.`
            };
        }

        if (file.size > MAX_FILE_SIZE) {
            return {
                valid: false,
                error: `File size (${formatFileSize(file.size)}) exceeds maximum (10MB). Please upload a smaller file.`
            };
        }

        return { valid: true };
    }

    /**
     * Format file size
     */
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    /**
     * Add files to the list
     */
    function addFiles(newFiles) {
        // Calculate effective remaining capacity - use server-provided value, capped by maxTotalResumes
        // This ensures we respect both the global limit (300) and the current job's remaining capacity
        const effectiveRemaining = Math.min(config.maxTotalResumes, config.remainingCapacity);
        
        // Check server-provided remaining capacity first
        if (effectiveRemaining <= 0) {
            alert('Maximum resume limit reached. Cannot add more files.');
            return;
        }

        for (const file of newFiles) {
            // Check if we've reached the effective capacity
            if (files.length >= effectiveRemaining) {
                alert(`Maximum resume limit (${effectiveRemaining}) reached. Cannot add more files.`);
                break;
            }

            // Validate file
            const validation = validateFile(file);
            if (!validation.valid) {
                alert(`File "${file.name}": ${validation.error}`);
                continue;
            }

            // Check for duplicates in current selection
            const exists = files.some(f => f.name === file.name && f.size === file.size);
            if (exists) {
                continue;
            }

            files.push({
                file: file,
                id: null,
                status: 'pending',
                progress: 0
            });
        }

        updateFileList();

        if (files.length > 0) {
            if (uploadControls) uploadControls.style.display = 'flex';
            if (fileListSection) fileListSection.style.display = 'block';
        }

        updateLimitsDisplay();
    }

    /**
     * Update file list display
     */
    function updateFileList() {
        if (!fileList) return;

        fileList.innerHTML = '';

        files.forEach((fileObj, index) => {
            const item = document.createElement('div');
            item.className = 'file-item flex justify-between items-center p-3 bg-code-block-bg rounded';

            const infoDiv = document.createElement('div');
            infoDiv.className = 'file-info flex items-center gap-3 flex-1';

            // File icon
            const iconSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            iconSvg.setAttribute('class', 'w-6 h-6 text-secondary-text');
            iconSvg.setAttribute('viewBox', '0 0 24 24');
            iconSvg.setAttribute('fill', 'none');
            iconSvg.setAttribute('stroke', 'currentColor');
            iconSvg.setAttribute('stroke-width', '2');
            iconSvg.innerHTML = `
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
            `;
            infoDiv.appendChild(iconSvg);

            // File name
            const nameSpan = document.createElement('span');
            nameSpan.className = 'file-name font-semibold text-primary-text text-sm';
            nameSpan.textContent = fileObj.file.name;
            infoDiv.appendChild(nameSpan);

            // File size
            const sizeSpan = document.createElement('span');
            sizeSpan.className = 'file-size text-secondary-text text-xs ml-2';
            sizeSpan.textContent = formatFileSize(fileObj.file.size);
            infoDiv.appendChild(sizeSpan);

            item.appendChild(infoDiv);

            // Remove button for pending files
            if (fileObj.status === 'pending') {
                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'file-actions';

                const removeBtn = document.createElement('button');
                removeBtn.className = 'btn-remove text-red-600 hover:text-red-800 text-xl px-2';
                removeBtn.textContent = '×';
                removeBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    removeFile(index);
                });

                actionsDiv.appendChild(removeBtn);
                item.appendChild(actionsDiv);
            }

            fileList.appendChild(item);
        });

        if (totalFilesList) totalFilesList.textContent = files.length;
        if (fileCount) fileCount.textContent = files.length;
    }

    /**
     * Remove file from list
     */
    function removeFile(index) {
        files.splice(index, 1);
        updateFileList();

        if (files.length === 0) {
            if (uploadControls) uploadControls.style.display = 'none';
            if (fileListSection) fileListSection.style.display = 'none';
        }

        updateLimitsDisplay();
    }

    /**
     * Update limits display
     */
    function updateLimitsDisplay() {
        if (filesPerBatch) {
            filesPerBatch.textContent = `${files.length}/${config.maxFilesPerBatch}`;
        }
        
        // Update button text to show file count
        if (startUploadBtn) {
            startUploadBtn.textContent = `Start Upload (${files.length} files)`;
        }
    }

    /**
     * Start upload process
     */
    async function startUpload() {
        if (isUploading) return;
        if (files.length === 0) {
            alert('Please select files to upload');
            return;
        }
        
        // Check if upload would exceed max files per batch
        if (files.length > config.maxFilesPerBatch) {
            alert(`Maximum ${config.maxFilesPerBatch} files allowed per upload. Please remove ${files.length - config.maxFilesPerBatch} files.`);
            return;
        }

        isUploading = true;
        startUploadBtn.disabled = true;
        startUploadBtn.textContent = 'Uploading...';

        try {
            // Initialize batch
            await initBatch();

            // Show progress section
            if (progressSection) progressSection.style.display = 'block';

            // Connect WebSocket
            connectWebSocket();

            // Upload all files
            for (let i = 0; i < files.length; i++) {
                await uploadFile(i);
            }

            // Show validation button
            if (uploadActions) uploadActions.style.display = 'flex';
            startUploadBtn.textContent = 'Upload Complete';

        } catch (error) {
            console.error('Upload error:', error);
            alert('Upload failed: ' + error.message);
            startUploadBtn.disabled = false;
            startUploadBtn.textContent = `Start Upload (${files.length} files)`;
        }

        isUploading = false;
    }

    /**
     * Initialize batch
     */
    async function initBatch() {
        const response = await fetch('/api/applications/bulk-upload/init/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': config.csrfToken
            },
            body: JSON.stringify({
                job_listing_id: config.jobListingId
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to initialize batch');
        }

        const data = await response.json();
        batchId = data.batch_id;
        console.log('Batch initialized:', batchId);
    }

    /**
     * Upload single file
     */
    async function uploadFile(index) {
        const fileObj = files[index];
        const formData = new FormData();
        formData.append('batch_id', batchId);
        formData.append('file', fileObj.file);

        try {
            const response = await fetch('/api/applications/bulk-upload/upload/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': config.csrfToken
                },
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || error.message || 'Upload failed');
            }

            const data = await response.json();
            fileObj.id = data.file_id;
            fileObj.hash = data.file_hash;
            fileObj.status = 'success';

            updateFileList();

        } catch (error) {
            console.error('File upload error:', error);
            fileObj.status = 'error';
            fileObj.error = error.message;
            updateFileList();
        }
    }

    /**
     * Connect WebSocket for real-time progress
     */
    function connectWebSocket() {
        if (!batchId) return;

        // Close existing WebSocket if open to prevent duplicate connections
        if (ws) {
            if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
                console.log('Closing existing WebSocket connection before creating new one');
                ws.close();
            }
            ws = null;
        }

        const wsUrl = `${config.wsProtocol || 'ws'}://${config.wsHost || window.location.host}/ws/bulk-upload/${batchId}/`;

        try {
            ws = new WebSocket(wsUrl);

            ws.onopen = function() {
                console.log('WebSocket connected');
            };

            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    handleWebSocketMessage(data);
                } catch (error) {
                    console.error('Failed to parse WebSocket message:', error);
                }
            };

            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
            };

            ws.onclose = function() {
                console.log('WebSocket closed');
            };

        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
        }
    }

    /**
     * Handle WebSocket message
     */
    function handleWebSocketMessage(data) {
        switch (data.type) {
            case 'file_progress':
                updateFileProgress(data.file_id, data.status, data.progress_percent);
                break;
            case 'batch_progress':
                updateBatchProgress(data);
                break;
            case 'validation_complete':
                handleValidationComplete(data);
                break;
            case 'processing_started':
                handleProcessingStarted(data);
                break;
            case 'file_success':
                handleFileSuccess(data);
                break;
            case 'file_error':
                handleFileError(data);
                break;
            case 'processing_complete':
                handleProcessingComplete(data);
                break;
            case 'processing_failed':
                handleProcessingFailed(data);
                break;
            case 'error':
                handleError(data);
                break;
        }
    }

    /**
     * Handle processing started
     */
    function handleProcessingStarted(data) {
        console.log('Processing started:', data);
        
        // Update status message only - counters already initialized by showProcessingUI
        const statusMessage = document.getElementById('processing-status');
        if (statusMessage) {
            statusMessage.textContent = `Processing ${data.total_files} files...`;
            statusMessage.style.display = 'block';
        }
        
        // Note: We don't reset counters here - showProcessingUI() already did that
        // Just ensure totalFiles is set (in case showProcessingUI wasn't called)
        if (totalFiles && !totalFiles.textContent) {
            totalFiles.textContent = data.total_files;
        }
    }

    /**
     * Handle file success
     */
    function handleFileSuccess(data) {
        console.log('File success:', data.filename);
        
        // Prevent double-processing of the same file
        if (processedFileIds.has(data.file_id)) {
            console.log('File already processed:', data.file_id);
            return;
        }
        processedFileIds.add(data.file_id);

        // Update progress
        const currentProcessed = parseInt(uploadedCount?.textContent || '0');
        if (uploadedCount) uploadedCount.textContent = currentProcessed + 1;

        // Update progress bar - use different variable name to avoid shadowing
        const totalFilesCount = parseInt(totalFiles?.textContent || '1');
        const processed = currentProcessed + 1;
        const percent = Math.min(100, Math.round((processed / totalFilesCount) * 100));  // Cap at 100%
        if (progressFill) progressFill.style.width = percent + '%';
        if (progressText) progressText.textContent = percent + '%';

        // Mark file as processed in the list
        const fileObj = files.find(f => f.id === data.file_id);
        if (fileObj) {
            fileObj.status = 'processed';
            updateFileList();
        }
    }

    /**
     * Handle file error
     */
    function handleFileError(data) {
        console.error('File error:', data.filename, data.message);
        
        // Prevent double-processing of the same file
        if (processedFileIds.has(data.file_id)) {
            console.log('File already processed:', data.file_id);
            return;
        }
        processedFileIds.add(data.file_id);

        // Update error count
        const currentErrors = parseInt(errorCount?.textContent || '0');
        if (errorCount) errorCount.textContent = currentErrors + 1;

        // Update processed count
        const currentProcessed = parseInt(uploadedCount?.textContent || '0');
        if (uploadedCount) uploadedCount.textContent = currentProcessed + 1;

        // Update progress bar - use different variable name to avoid shadowing
        const totalFilesCount = parseInt(totalFiles?.textContent || '1');
        const processed = currentProcessed + 1;
        const percent = Math.min(100, Math.round((processed / totalFilesCount) * 100));  // Cap at 100%
        if (progressFill) progressFill.style.width = percent + '%';
        if (progressText) progressText.textContent = percent + '%';

        // Mark file as failed in the list
        const fileObj = files.find(f => f.id === data.file_id);
        if (fileObj) {
            fileObj.status = 'failed';
            fileObj.error = data.message;
            updateFileList();
        }
    }

    /**
     * Handle processing complete
     */
    function handleProcessingComplete(data) {
        console.log('Processing complete:', data);
        
        // Reset processing state
        isProcessing = false;
        processedFileIds.clear();

        const summary = data.summary || {};
        const applicantsCreated = summary.applicants_created || 0;
        const filesFailed = summary.files_failed || 0;

        // Show success modal with timeout and redirect
        let message = `${applicantsCreated} resumes uploaded successfully.`;
        if (filesFailed > 0) {
            message += ` ${filesFailed} file(s) failed.`;
        }

        showSuccessModal(
            'Bulk Upload Complete',
            message,
            () => {
                window.location.href = '/dashboard/';
            }
        );

        // Close WebSocket
        if (ws) {
            ws.close();
            ws = null;
        }
    }

    /**
     * Handle processing failed
     */
    function handleProcessingFailed(data) {
        console.error('Processing failed:', data);
        
        // Reset processing state
        isProcessing = false;
        processedFileIds.clear();

        const statusMessage = document.getElementById('processing-status');
        if (statusMessage) {
            statusMessage.textContent = 'Processing failed: ' + (data.error || 'Unknown error');
            statusMessage.style.color = 'red';
        }
        
        alert('Processing failed: ' + (data.error || 'Unknown error'));
        
        // Close WebSocket
        if (ws) {
            ws.close();
            ws = null;
        }
    }

    /**
     * Update file progress
     */
    function updateFileProgress(fileId, status, progress) {
        const fileObj = files.find(f => f.id === fileId);
        if (fileObj) {
            fileObj.status = status;
            fileObj.progress = progress || 100;
            updateFileList();
        }
    }

    /**
     * Update batch progress
     */
    function updateBatchProgress(data) {
        const filesUploaded = data.files_uploaded || 0;
        const filesValidated = data.files_validated || 0;
        const filesWithErrors = data.files_with_errors || 0;
        const filesTotal = files.length;

        // Update progress bar
        const percent = filesTotal > 0 ? Math.round((filesUploaded / filesTotal) * 100) : 0;
        if (progressFill) progressFill.style.width = percent + '%';
        if (progressText) progressText.textContent = percent + '%';
        if (uploadedCount) uploadedCount.textContent = filesUploaded;
        if (validatedCount) validatedCount.textContent = filesValidated;
        if (errorCount) errorCount.textContent = filesWithErrors;
    }

    /**
     * Handle validation complete
     */
    function handleValidationComplete(data) {
        console.log('Validation complete:', data);
    }

    /**
     * Handle error
     */
    function handleError(data) {
        console.error('WebSocket error:', data);
        alert('Error: ' + (data.message || data.error || 'An error occurred'));
    }

    /**
     * Validate batch
     */
    async function validateBatch() {
        if (!batchId) {
            alert('No batch initialized');
            return;
        }

        validateBtn.disabled = true;
        validateBtn.textContent = 'Checking...';

        try {
            const response = await fetch('/api/applications/bulk-upload/validate/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': config.csrfToken
                },
                body: JSON.stringify({
                    batch_id: batchId
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Validation failed');
            }

            const data = await response.json();

            if (data.duplicates && data.duplicates.length > 0) {
                showDuplicateModal(data);
            } else {
                showCommitSection(data);
            }

        } catch (error) {
            console.error('Validation error:', error);
            alert('Validation failed: ' + error.message);
        } finally {
            validateBtn.disabled = false;
            validateBtn.textContent = 'Check for Duplicates';
        }
    }

    /**
     * Show duplicate modal
     */
    function showDuplicateModal(data) {
        duplicates = data.duplicates || [];
        
        if (duplicateCount) duplicateCount.textContent = duplicates.length;
        if (duplicateList) duplicateList.innerHTML = '';

        duplicates.forEach((dup, index) => {
            const item = document.createElement('div');
            item.className = 'duplicate-item flex justify-between items-center p-3 bg-code-block-bg rounded mb-2';

            const infoDiv = document.createElement('div');
            infoDiv.className = 'duplicate-info flex-1';

            const filenameDiv = document.createElement('div');
            filenameDiv.className = 'duplicate-filename font-semibold text-primary-text text-sm';
            filenameDiv.textContent = dup.filename;
            infoDiv.appendChild(filenameDiv);

            const typeDiv = document.createElement('div');
            typeDiv.className = 'duplicate-type text-secondary-text text-xs';
            typeDiv.textContent = 'Duplicate type: ' + (dup.duplicate_type || 'unknown');
            infoDiv.appendChild(typeDiv);

            item.appendChild(infoDiv);

            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'duplicate-item-actions flex gap-2';

            const skipBtn = document.createElement('button');
            skipBtn.className = 'btn btn-sm btn-secondary bg-code-block-bg text-primary-text px-3 py-1 rounded text-xs hover:bg-gray-300';
            skipBtn.textContent = 'Skip';
            skipBtn.addEventListener('click', function() {
                setDecision(dup.file_id, 'skip');
            });
            actionsDiv.appendChild(skipBtn);

            const includeBtn = document.createElement('button');
            includeBtn.className = 'btn btn-sm btn-primary bg-accent-cta text-cta-text px-3 py-1 rounded text-xs hover:brightness-110';
            includeBtn.textContent = 'Include';
            includeBtn.addEventListener('click', function() {
                setDecision(dup.file_id, 'include');
            });
            actionsDiv.appendChild(includeBtn);

            item.appendChild(actionsDiv);
            duplicateList.appendChild(item);
        });

        if (duplicateModal) duplicateModal.style.display = 'flex';
    }

    /**
     * Set decision for duplicate
     */
    function setDecision(fileId, action) {
        const existingIndex = decisions.findIndex(d => d.file_id === fileId);
        if (existingIndex >= 0) {
            decisions[existingIndex].action = action;
        } else {
            decisions.push({ file_id: fileId, action: action });
        }
    }

    /**
     * Skip all duplicates
     */
    function skipAll() {
        duplicates.forEach(dup => {
            setDecision(dup.file_id, 'skip');
        });
        alert('All duplicates marked as Skip');
    }

    /**
     * Include all duplicates
     */
    function includeAll() {
        duplicates.forEach(dup => {
            setDecision(dup.file_id, 'include');
        });
        alert('All duplicates marked as Include');
    }

    /**
     * Confirm decisions
     */
    async function confirmDecisions() {
        if (decisions.length !== duplicates.length) {
            alert(`Please make decisions for all ${duplicates.length} duplicates (currently ${decisions.length} decisions made)`);
            return;
        }

        try {
            const response = await fetch('/api/applications/bulk-upload/decisions/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': config.csrfToken
                },
                body: JSON.stringify({
                    batch_id: batchId,
                    decisions: decisions
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to save decisions');
            }

            const data = await response.json();
            closeModal();
            showCommitSection({
                total_files: data.files_to_process || files.length,
                files_skipped: data.files_skipped || 0
            });

        } catch (error) {
            console.error('Decision error:', error);
            alert('Failed to save decisions: ' + error.message);
        }
    }

    /**
     * Close modal
     */
    function closeModal() {
        if (duplicateModal) duplicateModal.style.display = 'none';
    }

    /**
     * Show commit section
     */
    function showCommitSection(data) {
        if (filesToCommit) filesToCommit.textContent = data.total_files || files.length;
        if (commitSection) commitSection.style.display = 'block';
        if (uploadActions) uploadActions.style.display = 'none';
        
        // Show AI disclaimer
        if (aiDisclaimer) aiDisclaimer.style.display = 'block';
    }

    /**
     * Commit batch - triggers async processing
     */
    async function commitBatch() {
        if (!batchId) {
            alert('No batch initialized');
            return;
        }

        commitBtn.disabled = true;
        commitBtn.textContent = 'Starting Processing...';

        try {
            const response = await fetch('/api/applications/bulk-upload/commit/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': config.csrfToken
                },
                body: JSON.stringify({
                    batch_id: batchId
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Commit failed');
            }

            const data = await response.json();

            if (data.status === 'processing') {
                // Processing started - show progress UI
                commitBtn.textContent = 'Processing...';
                
                // Show processing status section FIRST (before WebSocket connects)
                showProcessingUI(data.total_files);

                // Connect WebSocket for real-time updates
                // Note: handleProcessingStarted will NOT reset counters since showProcessingUI already did
                connectWebSocket();

                // Note: We don't close the modal or redirect here.
                // The user will see real-time progress via WebSocket
                // and will be notified when processing is complete.
            }

        } catch (error) {
            console.error('Commit error:', error);
            alert('Commit failed: ' + error.message);
            commitBtn.disabled = false;
            commitBtn.textContent = 'Commit and Create Applicants';
        }
    }

    /**
     * Show processing UI with progress bar
     */
    function showProcessingUI(totalCount) {
        // Reset processed file tracking
        processedFileIds.clear();
        isProcessing = true;
        
        // Hide commit section
        if (commitSection) commitSection.style.display = 'none';

        // Show progress section
        if (progressSection) progressSection.style.display = 'block';

        // Initialize progress bar
        if (progressFill) progressFill.style.width = '0%';
        if (progressText) progressText.textContent = '0%';
        if (totalFiles) totalFiles.textContent = totalCount;
        if (uploadedCount) uploadedCount.textContent = '0';
        if (validatedCount) validatedCount.textContent = '0';
        if (errorCount) errorCount.textContent = '0';

        // Show status message
        const statusMessage = document.getElementById('processing-status');
        if (statusMessage) {
            statusMessage.textContent = 'Processing started... You will receive real-time updates.';
            statusMessage.style.display = 'block';
        }
    }

    /**
     * Show success modal with auto-close
     * @param {string} title - Modal title
     * @param {string} message - Modal message
     * @param {Function} onClose - Callback function to execute after closing
     */
    function showSuccessModal(title, message, onClose) {
        const modal = document.getElementById('message-modal');
        const titleEl = document.getElementById('message-modal-title');
        const messageEl = document.getElementById('message-modal-message');
        const okBtn = document.getElementById('message-modal-ok');

        if (modal && titleEl && messageEl) {
            titleEl.textContent = title;
            messageEl.textContent = message;
            modal.style.display = 'flex';

            // Auto-close after 5 seconds - capture timeout ID so we can clear it on manual close
            const autoCloseId = setTimeout(function() {
                closeMessageModal(onClose);
            }, 5000);

            // Set up OK button to close modal and call callback
            if (okBtn) {
                // Remove any existing listeners by cloning
                const newOkBtn = okBtn.cloneNode(true);
                okBtn.parentNode.replaceChild(newOkBtn, okBtn);
                newOkBtn.addEventListener('click', function() {
                    // Clear the auto-close timeout to prevent double-calling closeMessageModal
                    clearTimeout(autoCloseId);
                    closeMessageModal(onClose);
                });
            }
        } else {
            // Fallback: just redirect
            setTimeout(function() {
                window.location.href = '/dashboard/';
            }, 5000);
        }
    }

    /**
     * Close message modal
     * @param {Function} onClose - Callback function to execute after closing
     */
    function closeMessageModal(onClose) {
        const modal = document.getElementById('message-modal');
        if (modal) {
            modal.style.display = 'none';
            if (onClose && typeof onClose === 'function') {
                onClose();
            }
        }
    }

    /**
     * Cancel upload
     */
    async function cancelUpload() {
        if (!batchId) {
            // Just clear local state
            clearAll();
            return;
        }

        try {
            const response = await fetch('/api/applications/bulk-upload/cancel/' + batchId + '/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': config.csrfToken
                }
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Cancel failed');
            }

        } catch (error) {
            console.error('Cancel error:', error);
        } finally {
            clearAll();
        }
    }

    /**
     * Clear all files
     */
    function clearAll() {
        files = [];
        batchId = null;
        decisions = [];
        duplicates = [];
        isProcessing = false;
        processedFileIds.clear();

        if (ws) {
            ws.close();
            ws = null;
        }

        updateFileList();
        
        if (uploadControls) uploadControls.style.display = 'none';
        if (fileListSection) fileListSection.style.display = 'none';
        if (progressSection) progressSection.style.display = 'none';
        if (uploadActions) uploadActions.style.display = 'none';
        if (commitSection) commitSection.style.display = 'none';
        if (aiDisclaimer) aiDisclaimer.style.display = 'none';
        if (duplicateModal) duplicateModal.style.display = 'none';

        if (startUploadBtn) {
            startUploadBtn.disabled = false;
            startUploadBtn.textContent = 'Start Upload (0 files)';
        }
    }
});
