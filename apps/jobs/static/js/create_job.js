// Helper function to show error message
function showError(message) {
    const errorMessage = document.getElementById('job-error-message');
    const errorText = document.getElementById('job-error-text');
    if (errorMessage && errorText) {
        errorText.textContent = message;
        errorMessage.classList.remove('hidden');
    }
}

// Helper function to show success message
function showSuccess(message) {
    const successMessage = document.getElementById('job-success-message');
    const successText = document.getElementById('job-success-text');
    if (successMessage && successText) {
        successText.textContent = message;
        successMessage.classList.remove('hidden');
    }
}

document.getElementById('jobCreationForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    // Client-side validation for date fields
    const startDateInput = document.getElementById('start_date');
    const expirationDateInput = document.getElementById('expiration_date');

    if (startDateInput.value && expirationDateInput.value) {
        const startDate = new Date(startDateInput.value);
        const expirationDate = new Date(expirationDateInput.value);

        if (expirationDate <= startDate) {
            showError('Expiration date must be after start date.');
            return; // Stop the submission
        }
    }

    // Get form data
    const formData = new FormData(e.target);
    const jobData = {
        title: formData.get('title'),
        description: formData.get('description'),
        required_skills: formData.get('required_skills').split(',').map(skill => skill.trim()).filter(skill => skill !== ''),
        required_experience: parseInt(formData.get('required_experience')),
        job_level: formData.get('job_level'),
        start_date: formData.get('start_date'),
        expiration_date: formData.get('expiration_date')
    };

    try {
        const response = await fetch('/dashboard/jobs/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            },
            credentials: 'include',  // Include cookies in request (handles JWT tokens automatically)
            body: JSON.stringify(jobData)
        });

        if (response.ok) {
            const result = await response.json();
            if (result && result.id) {
                showSuccess('Job listing created successfully!');
                setTimeout(() => {
                    window.location.href = '/dashboard/';
                }, 1500);
            } else {
                console.error('Unexpected response format:', result);
                showSuccess('Job listing created successfully but ID not returned. Redirecting to dashboard.');
                setTimeout(() => {
                    window.location.href = '/dashboard/';
                }, 1500);
            }
        } else {
            const errorData = await response.json();
            console.error('Error creating job listing:', errorData); // Send full error to console for debugging

            // Extract user-friendly message from common error field names
            let userMessage = 'Unable to create job listing. Please try again.';

            if (errorData && typeof errorData === 'object') {
                userMessage = errorData.message || errorData.error || errorData.detail || userMessage;

                // If the error message is an array, take the first element
                if (Array.isArray(userMessage)) {
                    userMessage = userMessage[0] || 'Unable to create job listing. Please try again.';
                }
            }

            showError(`Error creating job listing: ${userMessage}`);
        }
    } catch (error) {
        console.error('Error:', error);
        showError('An error occurred while creating the job listing.');
    }
});

// Add event listener for the "Add Screening Questions Later" button
document.addEventListener('DOMContentLoaded', function() {
    const addScreeningQuestionsBtn = document.getElementById('addScreeningQuestionsBtn');
    if (addScreeningQuestionsBtn) {
        addScreeningQuestionsBtn.addEventListener('click', async function(e) {
            e.preventDefault();

            // Perform client-side validation similar to the form submission
            const startDateInput = document.getElementById('start_date');
            const expirationDateInput = document.getElementById('expiration_date');

            if (startDateInput.value && expirationDateInput.value) {
                const startDate = new Date(startDateInput.value);
                const expirationDate = new Date(expirationDateInput.value);

                if (expirationDate <= startDate) {
                    showError('Expiration date must be after start date.');
                    return; // Stop the submission
                }
            }

            // Get form data
            const formData = new FormData(document.getElementById('jobCreationForm'));
            const jobData = {
                title: formData.get('title'),
                description: formData.get('description'),
                required_skills: formData.get('required_skills').split(',').map(skill => skill.trim()).filter(skill => skill !== ''),
                required_experience: parseInt(formData.get('required_experience')),
                job_level: formData.get('job_level'),
                start_date: formData.get('start_date'),
                expiration_date: formData.get('expiration_date')
            };

            // Validate required fields
            if (!jobData.title || !jobData.description || !Array.isArray(jobData.required_skills) || jobData.required_skills.length === 0 || 
                jobData.required_experience === null || jobData.required_experience === undefined || jobData.required_experience === '' ||
                !jobData.job_level || !jobData.start_date || !jobData.expiration_date) {
                showError('Please fill in all required fields before creating the job.');
                return;
            }

            try {
                const response = await fetch('/dashboard/jobs/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                    },
                    credentials: 'include',  // Include cookies in request (handles JWT tokens automatically)
                    body: JSON.stringify(jobData)
                });

                if (response.ok) {
                    const result = await response.json();
                    if (result && result.id) {
                        // Redirect to the add screening questions page with the job ID
                        window.location.href = `/dashboard/${result.id}/add-screening-question/`;
                    } else {
                        console.error('Unexpected response format:', result);
                        showError('Job listing created successfully but ID not returned.');
                        setTimeout(() => {
                            window.location.href = '/dashboard/';
                        }, 1500);
                    }
                } else {
                    const errorText = await response.text(); // Get raw response text
                    let errorData;

                    try {
                        errorData = JSON.parse(errorText); // Try to parse as JSON
                    } catch (e) {
                        // If not JSON, use the raw text
                        errorData = { detail: errorText || 'Unknown error occurred' };
                    }

                    console.error('Error creating job listing:', errorData);

                    let userMessage = 'Unable to create job listing. Please try again.';
                    if (errorData && typeof errorData === 'object') {
                        userMessage = errorData.message || errorData.error || errorData.detail || userMessage;

                        // Handle field-specific errors
                        if (typeof errorData === 'object') {
                            const fieldErrors = [];
                            Object.keys(errorData).forEach(field => {
                                if (Array.isArray(errorData[field])) {
                                    fieldErrors.push(`${field}: ${errorData[field].join(', ')}`);
                                }
                            });

                            if (fieldErrors.length > 0) {
                                userMessage = fieldErrors.join('; ');
                            }
                        }

                        if (Array.isArray(userMessage)) {
                            userMessage = userMessage[0] || userMessage;
                        }
                    }

                    showError(`Error creating job listing: ${userMessage}`);
                }
            } catch (error) {
                console.error('Error creating job listing:', error);
                showError('An error occurred while creating the job listing. Please check your connection and try again.');
            }
        });
    }
});

// Show/hide choices section based on question type
const questionTypeElement = document.getElementById('question_type');
if (questionTypeElement) {
  questionTypeElement.addEventListener('change', function() {
    const choicesSection = document.getElementById('choicesSection');
    const selectedType = this.value;

    if (choicesSection) {
      if (selectedType === 'CHOICE' || selectedType === 'MULTIPLE_CHOICE') {
          choicesSection.classList.remove('hidden');
      } else {
          choicesSection.classList.add('hidden');
      }
    }
  });
}

// Set up logout event listener
document.addEventListener('DOMContentLoaded', function() {
    const logoutLink = document.getElementById('logout-link');
    if (logoutLink) {
        logoutLink.addEventListener('click', async function(e) {
            e.preventDefault();

            // Get CSRF token with null check
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
            
            try {
                const response = await fetch('/api/accounts/auth/logout/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin'  // Include cookies in request
                });

                if (response.status === 204) {
                    // Redirect to home page after successful logout
                    window.location.href = '/';
                } else {
                    console.error('Logout failed');
                    // Even if there's an error, redirect to home page
                    window.location.href = '/';
                }
            } catch (error) {
                console.error('Error during logout:', error);
                // Even if there's an error, redirect to home page
                window.location.href = '/';
            }
        });
    }
});