// Helper function to get cookie value
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

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

// Helper function to hide all messages
function hideAllMessages() {
    const errorMessage = document.getElementById('job-error-message');
    const successMessage = document.getElementById('job-success-message');
    if (errorMessage) errorMessage.classList.add('hidden');
    if (successMessage) successMessage.classList.add('hidden');
}

// Get job ID from URL
// The URL pattern is /dashboard/{job_id}/edit/
const pathSegments = window.location.pathname.split('/').filter(segment => segment !== '');
const editIndex = pathSegments.indexOf('edit');
let jobId = null;

if (editIndex > 0) {
    // The job ID is the segment before 'edit'
    jobId = pathSegments[editIndex - 1];
}

// Guard against missing jobId
if (!jobId) {
    console.error('Job ID not found in URL');
    // Try alternative method: extract from the pathname using regex
    const match = window.location.pathname.match(/\/dashboard\/([^\/]+)\/edit\//);
    if (match && match[1]) {
        jobId = match[1];
    }
}

if (!jobId) {
    console.error('Job ID still not found in URL after alternative method');
    showError('Error: Unable to determine job ID from URL. Please navigate to this page from the dashboard.');
    // Set a flag to indicate that initialization should not proceed
    window.jobIdMissing = true;
}

// Load job data
async function loadJobData() {
    // Check if jobId is missing before proceeding
    if (window.jobIdMissing) {
        console.error('Cannot load job data: Job ID is missing');
        return;
    }

    try {
        const response = await fetch(`/dashboard/jobs/${jobId}/`, {
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            const job = await response.json();

            // Populate form fields
            const setFieldValue = (id, value) => {
                const el = document.getElementById(id);
                if (el) el.value = value ?? '';
            };
            const formatDate = (dateStr) => {
                const d = new Date(dateStr);
                return isNaN(d.getTime()) ? '' : d.toISOString().slice(0, 16);
            };

            setFieldValue('title', job.title);
            setFieldValue('description', job.description);
            setFieldValue('required_skills', Array.isArray(job.required_skills) ? job.required_skills.join(', ') : '');
            setFieldValue('required_experience', job.required_experience);
            setFieldValue('job_level', job.job_level);
            setFieldValue('start_date', formatDate(job.start_date));
            setFieldValue('expiration_date', formatDate(job.expiration_date));
            setFieldValue('status', job.status);
            
            // Load screening questions after job data is loaded
            loadScreeningQuestions(jobId);
        } else if (response.status === 404) {
            // If the job doesn't exist (e.g., it was deleted), don't show an error
            // This prevents the error message from showing after deletion
            console.log('Job not found, possibly deleted');
        } else {
            showError('Failed to load job data');
        }
    } catch (error) {
        console.error('Error loading job data:', error);
        showError('An error occurred while loading job data.');
    }
}

// Load screening questions for the job
async function loadScreeningQuestions(jobId) {
    try {
        const response = await fetch(`/dashboard/jobs/${jobId}/screening-questions/`, {
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            const questions = await response.json();
            displayScreeningQuestions(questions);
        } else {
            console.error('Failed to load screening questions:', response.status);
        }
    } catch (error) {
        console.error('Error loading screening questions:', error);
    }
}

// Display screening questions in the UI
function displayScreeningQuestions(questions) {
    const questionsList = document.getElementById('questionsList');
    
    if (!questions || questions.length === 0) {
        questionsList.innerHTML = '<p class="text-gray-500 italic">No screening questions added yet.</p>';
        return;
    }
    
    questionsList.innerHTML = '';

    questions.forEach(question => {
        const questionDiv = document.createElement('div');
        questionDiv.className = 'border border-gray-200 p-4 rounded-md mb-3 bg-gray-50';

        // Format question type for display
        const questionTypeMap = {
            'TEXT': 'Text',
            'YES_NO': 'Yes/No',
            'CHOICE': 'Choice (Single)',
            'MULTIPLE_CHOICE': 'Multiple Choice',
            'FILE_UPLOAD': 'File Upload'
        };

        const questionTypeDisplay = questionTypeMap[question.question_type] || question.question_type;

        // Create the main flex container
        const flexContainer = document.createElement('div');
        flexContainer.className = 'flex justify-between items-start';

        // Create the left side content container
        const contentContainer = document.createElement('div');
        contentContainer.className = 'flex-1';

        // Create the question text element
        const questionTextElement = document.createElement('div');
        questionTextElement.className = 'font-medium';
        questionTextElement.textContent = question.question_text; // Safe assignment

        // Create the meta info element
        const metaInfoElement = document.createElement('div');
        metaInfoElement.className = 'text-sm text-gray-600 mt-1';
        metaInfoElement.textContent = `Type: ${questionTypeDisplay} | ${question.required ? 'Required' : 'Optional'}`;

        // Add the main content to the left side
        contentContainer.appendChild(questionTextElement);
        contentContainer.appendChild(metaInfoElement);

        // Add choices if they exist
        if (question.choices && question.choices.length > 0) {
            const choicesContainer = document.createElement('div');
            choicesContainer.className = 'mt-2 text-sm';

            const choicesLabel = document.createElement('strong');
            choicesLabel.textContent = 'Choices:';
            choicesContainer.appendChild(choicesLabel);

            const choicesList = document.createElement('ul');
            choicesList.className = 'list-disc pl-5 mt-1';

            question.choices.forEach(choice => {
                const choiceItem = document.createElement('li');
                // Handle both string choices and object choices (with text property)
                choiceItem.textContent = typeof choice === 'string' ? choice : (choice.text || '');
                choicesList.appendChild(choiceItem);
            });

            choicesContainer.appendChild(choicesList);
            contentContainer.appendChild(choicesContainer);
        }

        // Create the right side buttons container
        const buttonsContainer = document.createElement('div');
        buttonsContainer.className = 'flex space-x-2';

        // Create the edit button
        const editButton = document.createElement('button');
        editButton.type = 'button';
        editButton.className = 'text-blue-600 hover:text-blue-800 text-sm font-medium';
        editButton.textContent = 'Edit';
        
        // Add click event listener for edit
        editButton.addEventListener('click', function() {
            editScreeningQuestion(question.id, jobId);
        });

        // Create the delete button
        const deleteButton = document.createElement('button');
        deleteButton.type = 'button';
        deleteButton.className = 'text-red-600 hover:text-red-800 text-sm font-medium';
        deleteButton.textContent = 'Delete';
        
        // Add click event listener for delete
        deleteButton.addEventListener('click', function() {
            deleteScreeningQuestion(question.id, jobId, deleteButton);
        });

        // Add buttons to the container
        buttonsContainer.appendChild(editButton);
        buttonsContainer.appendChild(deleteButton);

        // Add content and buttons to the flex container
        flexContainer.appendChild(contentContainer);
        flexContainer.appendChild(buttonsContainer);

        // Add the flex container to the question div
        questionDiv.appendChild(flexContainer);

        // Add the question div to the list
        questionsList.appendChild(questionDiv);
    });
}

// Function to edit a screening question
async function editScreeningQuestion(questionId, jobId) {
    // Redirect to the add screening question page with the question ID for editing
    window.location.href = `/dashboard/${jobId}/add-screening-question/?question_id=${questionId}`;
}

// Function to delete a screening question
async function deleteScreeningQuestion(questionId, jobId, element) {
    if (!confirm('Are you sure you want to delete this screening question?')) return;

    try {
        const response = await fetch(`/dashboard/jobs/${jobId}/screening-questions/${questionId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            // Remove the question element from the UI
            element.closest('.border').remove();
            showSuccess('Screening question deleted successfully!');
        } else {
            showError('Failed to delete screening question');
        }
    } catch (error) {
        console.error('Error deleting screening question:', error);
        showError('An error occurred while deleting the screening question.');
    }
}

// Add event listener for the "Add New Screening Question" button
document.addEventListener('DOMContentLoaded', function() {
    const addNewQuestionBtn = document.getElementById('addNewQuestionBtn');
    if (addNewQuestionBtn && jobId) {
        addNewQuestionBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Redirect to the add screening questions page with the job ID
            window.location.href = `/dashboard/${jobId}/add-screening-question/`;
        });
    } else {
        console.error('Add New Question button not found or Job ID is missing');
    }
});

// Update job listing
const jobEditForm = document.getElementById('jobEditForm');
if (jobEditForm) {
    jobEditForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        hideAllMessages();

        // Check if jobId is missing before proceeding
        if (window.jobIdMissing) {
            showError('Error: Cannot update job. Job ID is missing.');
            return;
        }

        const formData = new FormData(e.target);
        const jobData = {
            title: formData.get('title'),
            description: formData.get('description'),
            required_skills: formData.get('required_skills').split(',').map(skill => skill.trim()).filter(skill => skill !== ''),
            required_experience: parseInt(formData.get('required_experience'), 10) || 0,
            job_level: formData.get('job_level'),
            start_date: formData.get('start_date'),
            expiration_date: formData.get('expiration_date'),
            status: formData.get('status')
        };

        try {
            const response = await fetch(`/dashboard/jobs/${jobId}/`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                },
                credentials: 'include',  // Include cookies in request (handles JWT tokens automatically)
                body: JSON.stringify(jobData)
            });

            if (response.ok) {
                showSuccess('Job listing updated successfully!');
                setTimeout(() => {
                    window.location.href = '/dashboard/';
                }, 1500);
            } else {
                let errorMessage = `HTTP ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMessage = JSON.stringify(errorData);
                } catch { /* Response not JSON */ }
                showError(`Error updating job listing: ${errorMessage}`);
            }
        } catch (error) {
            console.error('Error:', error);
            showError('An error occurred while updating the job listing.');
        }
    });
}

// Delete job
const deleteButton = document.getElementById('deleteButton');
if (deleteButton) {
    deleteButton.addEventListener('click', async function() {
        // Check if jobId is missing before proceeding
        if (window.jobIdMissing) {
            showError('Error: Cannot delete job. Job ID is missing.');
            return;
        }

        if (!confirm('Are you sure you want to delete this job? This action cannot be undone.')) return;

        try {
            const response = await fetch(`/dashboard/jobs/${jobId}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                },
                credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
            });

            if (response.ok) {
                showSuccess('Job deleted successfully!');
                setTimeout(() => {
                    window.location.href = '/dashboard/'; // Redirect to dashboard
                }, 1500);
            } else {
                const errorData = await response.json();
                showError(`Error deleting job: ${JSON.stringify(errorData)}`);
            }
        } catch (error) {
            console.error('Error:', error);
            showError('An error occurred while deleting the job.');
        }
    });
}

// Load job data when page loads
document.addEventListener('DOMContentLoaded', loadJobData);

// Set up logout event listener
document.addEventListener('DOMContentLoaded', function() {
    const logoutLink = document.getElementById('logout-link');
    if (logoutLink) {
        logoutLink.addEventListener('click', async function(e) {
            e.preventDefault();

            // Get CSRF token using the helper function
            const csrfToken = getCookie('csrftoken');
            if (!csrfToken) {
                console.error('CSRF token not found in cookies');
                // Even if there's an error, redirect to home page
                window.location.href = '/';
                return;
            }

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