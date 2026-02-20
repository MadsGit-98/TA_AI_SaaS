/**
 * Application Form JavaScript
 * 
 * Handles:
 * - File upload with drag-and-drop
 * - File validation (format, size)
 * - Async duplication checks
 * - Form validation and submission
 * - Error handling and user feedback
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize form elements
    const form = document.getElementById('application-form');
    const fileUploadArea = document.getElementById('file-upload-area');
    const resumeInput = document.getElementById('resume');
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    const removeFileBtn = document.getElementById('remove-file');
    const fileError = document.getElementById('file-error');
    const fileSuccess = document.getElementById('file-success');
    const submitBtn = document.getElementById('submit-btn');
    
    // File validation constants
    const MIN_FILE_SIZE = 50 * 1024; // 50KB
    const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
    const ALLOWED_TYPES = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    const ALLOWED_EXTENSIONS = ['pdf', 'docx'];
    
    // State
    let selectedFile = null;
    let fileValidated = false;
    let validationTimeout = null;
    
    // Initialize file upload area click handler
    fileUploadArea.addEventListener('click', function() {
        resumeInput.click();
    });
    
    // Handle file selection
    resumeInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            handleFileSelect(file);
        }
    });
    
    // Drag and drop handlers
    fileUploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        fileUploadArea.classList.add('drag-over');
    });
    
    fileUploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        fileUploadArea.classList.remove('drag-over');
    });
    
    fileUploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        fileUploadArea.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file) {
            handleFileSelect(file);
        }
    });
    
    // Remove file handler
    removeFileBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        removeFile();
    });
    
    // Form validation on input
    form.addEventListener('input', function(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            validateField(e.target);
            checkFormValidity();
        }
    });
    
    form.addEventListener('change', function(e) {
        if (e.target.type === 'radio') {
            checkFormValidity();
        }
    });
    
    // Form submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (!validateForm()) {
            return;
        }
        
        submitApplication();
    });
    
    /**
     * Handle file selection
     */
    function handleFileSelect(file) {
        // Clear previous state
        clearFileMessages();
        
        // Validate file
        const validationResult = validateFile(file);
        
        if (!validationResult.valid) {
            showFileError(validationResult.error);
            return;
        }
        
        // Display file info
        selectedFile = file;
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);
        fileInfo.classList.remove('hidden');
        fileInfo.classList.add('flex');
        
        // Validate file with server (async duplication check)
        validateFileWithServer(file);
    }
    
    /**
     * Validate file locally
     */
    function validateFile(file) {
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
        
        // Check file extension
        const extension = file.name.split('.').pop().toLowerCase();
        if (!ALLOWED_EXTENSIONS.includes(extension)) {
            return {
                valid: false,
                error: `Unsupported file format '.${extension}'. Only PDF and DOCX files are accepted.`
            };
        }
        
        return { valid: true };
    }
    
    /**
     * Validate file with server (async duplication check)
     */
    function validateFileWithServer(file) {
        // Clear previous timeout
        if (validationTimeout) {
            clearTimeout(validationTimeout);
        }
        
        // Debounce validation
        validationTimeout = setTimeout(async function() {
            const jobListingId = document.querySelector('input[name="job_listing_id"]').value;
            
            const formData = new FormData();
            formData.append('job_listing_id', jobListingId);
            formData.append('resume', file);
            
            try {
                const response = await fetch('/api/applications/validate-file/', {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': getCsrfToken()
                    }
                });
                
                const data = await response.json();
                
                if (response.status === 200) {
                    fileValidated = true;
                    showFileSuccess('File validated successfully');
                    checkFormValidity();
                } else if (response.status === 409) {
                    // Duplicate detected
                    fileValidated = false;
                    showFileError('This resume has already been submitted for this job listing.');
                    showDuplicateModal('This resume has already been submitted for this job listing. Please upload a different resume or contact support if you believe this is an error.');
                } else if (response.status === 400) {
                    fileValidated = false;
                    const error = data.errors && data.errors[0] ? data.errors[0].message : 'File validation failed';
                    showFileError(error);
                }
            } catch (error) {
                console.error('File validation error:', error);
                showFileError('Failed to validate file. Please try again.');
            }
        }, 500);
    }
    
    /**
     * Remove selected file
     */
    function removeFile() {
        selectedFile = null;
        fileValidated = false;
        resumeInput.value = '';
        fileInfo.classList.add('hidden');
        fileInfo.classList.remove('flex');
        clearFileMessages();
        checkFormValidity();
    }
    
    /**
     * Validate individual field
     */
    function validateField(field) {
        const errorElement = document.getElementById(`${field.name}-error`);
        
        if (field.validity.valid) {
            if (errorElement) {
                errorElement.textContent = '';
            }
            field.classList.remove('border-red-600');
            field.classList.add('border-code-block-bg');
            return true;
        } else {
            if (errorElement) {
                if (field.validity.valueMissing) {
                    errorElement.textContent = 'This field is required';
                } else if (field.validity.typeMismatch) {
                    if (field.type === 'email') {
                        errorElement.textContent = 'Please enter a valid email address';
                    }
                }
            }
            field.classList.remove('border-code-block-bg');
            field.classList.add('border-red-600');
            return false;
        }
    }
    
    /**
     * Validate entire form
     */
    function validateForm() {
        let isValid = true;
        
        // Validate all required fields
        const requiredFields = form.querySelectorAll('[required]');
        requiredFields.forEach(function(field) {
            if (field.type === 'radio') {
                // Handle radio buttons
                const radioGroup = form.querySelectorAll(`input[name="${field.name}"]`);
                let groupValid = false;
                radioGroup.forEach(function(radio) {
                    if (radio.checked) {
                        groupValid = true;
                    }
                });
                if (!groupValid) {
                    isValid = false;
                    const errorElement = document.getElementById(`question_${field.name.split('_')[1]}-error`);
                    if (errorElement) {
                        errorElement.textContent = 'Please select an answer';
                    }
                }
            } else {
                if (!validateField(field)) {
                    isValid = false;
                }
            }
        });
        
        // Check file validation
        if (!selectedFile) {
            isValid = false;
            showFileError('Please upload your resume');
        } else if (!fileValidated) {
            isValid = false;
            showFileError('Please wait for file validation to complete');
        }
        
        return isValid;
    }
    
    /**
     * Check form validity and enable/disable submit button
     */
    function checkFormValidity() {
        const requiredFields = form.querySelectorAll('[required]');
        let allFilled = true;
        
        requiredFields.forEach(function(field) {
            if (field.type === 'radio') {
                const radioGroup = form.querySelectorAll(`input[name="${field.name}"]`);
                let groupFilled = false;
                radioGroup.forEach(function(radio) {
                    if (radio.checked) {
                        groupFilled = true;
                    }
                });
                if (!groupFilled) {
                    allFilled = false;
                }
            } else {
                if (!field.value.trim()) {
                    allFilled = false;
                }
            }
        });
        
        // Enable submit button only if all fields filled and file validated
        submitBtn.disabled = !(allFilled && selectedFile && fileValidated);
    }
    
    /**
     * Submit application
     */
    async function submitApplication() {
        // Disable submit button
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Submitting...';
        
        const formData = new FormData(form);
        
        // Append file
        if (selectedFile) {
            formData.append('resume', selectedFile);
        }
        
        // Process screening answers
        const screeningAnswers = [];
        const answerElements = form.querySelectorAll('textarea[name="screening_answers"]');
        answerElements.forEach(function(textarea) {
            screeningAnswers.push({
                question_id: textarea.dataset.questionId,
                answer: textarea.value
            });
        });
        
        // Handle radio button answers
        const radioGroups = {};
        form.querySelectorAll('input[type="radio"]:checked').forEach(function(radio) {
            const questionId = radio.name.split('_')[1];
            if (!radioGroups[questionId]) {
                radioGroups[questionId] = radio.value;
            }
        });
        
        // Add radio answers to screening answers
        Object.keys(radioGroups).forEach(function(questionId) {
            screeningAnswers.push({
                question_id: questionId,
                answer: radioGroups[questionId]
            });
        });
        
        // Convert to JSON and append
        formData.append('screening_answers', JSON.stringify(screeningAnswers));
        
        try {
            const response = await fetch('/api/applications/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCsrfToken()
                }
            });
            
            const data = await response.json();
            
            if (response.status === 201) {
                // Success - redirect to success page
                window.location.href = `/applications/success/${data.id}/`;
            } else if (response.status === 409) {
                // Duplicate detected
                submitBtn.disabled = false;
                submitBtn.textContent = 'Submit Application';
                
                if (data.duplicate_type === 'resume') {
                    showFileError(data.message);
                    showDuplicateModal(data.message);
                } else if (data.duplicate_type === 'email') {
                    const emailError = document.getElementById('email-error');
                    if (emailError) {
                        emailError.textContent = data.message;
                    }
                    showDuplicateModal(data.message);
                } else if (data.duplicate_type === 'phone') {
                    const phoneError = document.getElementById('phone-error');
                    if (phoneError) {
                        phoneError.textContent = data.message;
                    }
                    showDuplicateModal(data.message);
                }
            } else if (response.status === 400) {
                // Validation error
                submitBtn.disabled = false;
                submitBtn.textContent = 'Submit Application';
                
                if (data.details) {
                    // Display validation errors
                    Object.keys(data.details).forEach(function(fieldName) {
                        const errors = data.details[fieldName];
                        const errorElement = document.getElementById(`${fieldName}-error`);
                        if (errorElement && errors && errors[0]) {
                            errorElement.textContent = errors[0];
                        }
                    });
                }
                
                if (data.error === 'validation_failed') {
                    showFileError('Please correct the errors above and try again');
                }
            } else {
                // Server error
                submitBtn.disabled = false;
                submitBtn.textContent = 'Submit Application';
                showFileError('An error occurred. Please try again later.');
            }
        } catch (error) {
            console.error('Submission error:', error);
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Application';
            showFileError('An error occurred. Please check your connection and try again.');
        }
    }
    
    /**
     * Utility functions
     */
    function formatFileSize(bytes) {
        if (bytes < 1024) {
            return bytes + ' B';
        } else if (bytes < 1024 * 1024) {
            return (bytes / 1024).toFixed(1) + ' KB';
        } else {
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }
    }
    
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }
    
    function showFileError(message) {
        fileError.textContent = message;
        fileError.classList.remove('hidden');
        fileSuccess.classList.add('hidden');
    }
    
    function showFileSuccess(message) {
        fileSuccess.textContent = message;
        fileSuccess.classList.remove('hidden');
        fileError.classList.add('hidden');
    }
    
    function clearFileMessages() {
        fileError.textContent = '';
        fileError.classList.add('hidden');
        fileSuccess.classList.add('hidden');
    }
    
    function showDuplicateModal(message) {
        const modal = document.getElementById('duplicate-modal');
        const messageElement = document.getElementById('duplicate-message');
        messageElement.textContent = message;
        modal.classList.remove('hidden');
    }
});

// Close modal function (global scope)
function closeModal() {
    const modal = document.getElementById('duplicate-modal');
    modal.classList.add('hidden');
}
