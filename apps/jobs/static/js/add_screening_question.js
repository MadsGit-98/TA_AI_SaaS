// Show/hide choices section based on question type
document.getElementById('question_type').addEventListener('change', function() {
    const choicesSection = document.getElementById('choicesSection');
    const selectedType = this.value;

    if (selectedType === 'CHOICE' || selectedType === 'MULTIPLE_CHOICE') {
        choicesSection.classList.remove('hidden');
    } else {
        choicesSection.classList.add('hidden');
    }
});

// Load suggested questions
async function loadSuggestedQuestions() {
    try {
        const response = await fetch('/dashboard/common-screening-questions/', {
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            const questions = await response.json();
            const container = document.getElementById('suggestedQuestionsContainer');

            if (questions.length === 0) {
                container.innerHTML = '<p class="text-gray-500">No suggested questions available.</p>';
                return;
            }

            container.innerHTML = '';
            questions.forEach(question => {
                const questionDiv = document.createElement('div');
                questionDiv.className = 'border border-gray-200 rounded-lg p-4 bg-white';
                
                // Create the content container
                const contentWrapper = document.createElement('div');
                contentWrapper.className = 'flex justify-between items-start';
                
                // Create the left side content
                const leftSide = document.createElement('div');
                
                const questionTitle = document.createElement('h3');
                questionTitle.className = 'font-medium';
                questionTitle.textContent = question.question_text;
                
                const questionInfo = document.createElement('p');
                questionInfo.className = 'text-sm text-gray-500';
                questionInfo.textContent = `Type: ${question.question_type} | Category: ${question.category}`;
                
                leftSide.appendChild(questionTitle);
                leftSide.appendChild(questionInfo);
                
                // Create the right side button
                const useButton = document.createElement('button');
                useButton.className = 'px-3 py-1 bg-[#080707] text-[#FFFFFF] text-sm rounded hover:bg-black';
                useButton.textContent = 'Use Question';
                
                // Attach click handler safely instead of using onclick attribute
                useButton.addEventListener('click', () => {
                    useSuggestedQuestion(question.question_text, question.question_type);
                });
                
                // Assemble the content
                contentWrapper.appendChild(leftSide);
                contentWrapper.appendChild(useButton);
                questionDiv.appendChild(contentWrapper);
                
                container.appendChild(questionDiv);
            });
        } else {
            console.error('Failed to load suggested questions');
        }
    } catch (error) {
        console.error('Error loading suggested questions:', error);
    }
}

// Function to populate form with suggested question
function useSuggestedQuestion(questionText, questionType) {
    document.getElementById('question_text').value = questionText;
    document.getElementById('question_type').value = questionType;

    // Trigger change event to show/hide choices section if needed
    const event = new Event('change');
    document.getElementById('question_type').dispatchEvent(event);
}

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

// Submit form
document.getElementById('screeningQuestionForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const formData = new FormData(e.target);
    const questionData = {
        question_text: formData.get('question_text'),
        question_type: formData.get('question_type'),
        required: formData.get('required') === 'on'
    };

    // Add choices if applicable
    const questionType = formData.get('question_type');
    if (questionType === 'CHOICE' || questionType === 'MULTIPLE_CHOICE') {
        const choicesText = formData.get('choices');
        if (choicesText.trim()) {
            questionData.choices = choicesText.split('\n').map(choice => choice.trim()).filter(choice => choice !== '');
        } else {
            alert('Choices are required for choice-based questions.');
            return;
        }
    }

    // Get job ID from URL parameters, URL path, or hidden form field
    let jobId = null;
    
    // First, try to get from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    jobId = urlParams.get('job_id');
    
    // If not in URL params, try to extract from URL path
    if (!jobId) {
        // Extract job ID from URL path (expected format: /dashboard/{job_id}/add-screening-question/)
        const pathSegments = window.location.pathname.split('/').filter(segment => segment !== '');
        const dashboardIndex = pathSegments.indexOf('dashboard');
        if (dashboardIndex !== -1 && pathSegments.length > dashboardIndex + 1) {
            const potentialJobId = pathSegments[dashboardIndex + 1];
            // Basic validation to check if it looks like a UUID
            const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
            if (uuidRegex.test(potentialJobId)) {
                jobId = potentialJobId;
            }
        }
    }
    
    // If still not found, try to get from hidden field
    if (!jobId) {
        const jobIdEl = document.getElementById('job_id');
        if (jobIdEl) {
            jobId = jobIdEl.value;
        }
    }

    // Get question ID for editing (if present)
    const questionIdFromUrl = urlParams.get('question_id');
    const questionIdEl = document.getElementById('question_id');
    let questionIdFromHiddenField = '';
    if (questionIdEl) {
        questionIdFromHiddenField = questionIdEl.value;
    }

    const questionId = questionIdFromUrl || questionIdFromHiddenField;

    if (!jobId) {
        console.error('Error: No job ID found. Cannot submit screening question.');
        alert('Error: Job ID is missing. Please go back and try again.');
        return;
    }

    try {
        let response;
        let method;
        let url;

        if (questionId) {
            // Editing an existing question
            method = 'PUT';
            url = `/dashboard/jobs/${jobId}/screening-questions/${questionId}/`;
            response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                credentials: 'include',  // Include cookies in request (handles JWT tokens automatically)
                body: JSON.stringify(questionData)
            });
        } else {
            // Creating a new question
            method = 'POST';
            url = `/dashboard/jobs/${jobId}/screening-questions/`;
            response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                credentials: 'include',  // Include cookies in request (handles JWT tokens automatically)
                body: JSON.stringify(questionData)
            });
        }

        if (response.ok) {
            const result = await response.json();
            if (questionId) {
                alert('Screening question updated successfully!');
            } else {
                alert('Screening question added successfully!');
            }
            // Redirect back to job edit page
            window.location.href = `/dashboard/${jobId}/edit/`;
        } else {
            const rawBody = await response.text();
            let errorData;
            try {
                errorData = JSON.parse(rawBody);
            } catch (e) {
                // If response is not JSON, use the raw text
                errorData = rawBody;
            }

            console.error('Error processing screening question:', errorData);
            alert('Failed to process screening question. Please try again.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while processing the screening question.');
    }
});

// Check if we're editing an existing question
document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const questionId = urlParams.get('question_id');
    
    // Get job ID from URL parameters, URL path, or hidden form field
    let jobId = urlParams.get('job_id');
    
    // If not in URL params, try to extract from URL path
    if (!jobId) {
        // Extract job ID from URL path (expected format: /dashboard/{job_id}/add-screening-question/)
        const pathSegments = window.location.pathname.split('/').filter(segment => segment !== '');
        const dashboardIndex = pathSegments.indexOf('dashboard');
        if (dashboardIndex !== -1 && pathSegments.length > dashboardIndex + 1) {
            const potentialJobId = pathSegments[dashboardIndex + 1];
            // Basic validation to check if it looks like a UUID
            const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
            if (uuidRegex.test(potentialJobId)) {
                jobId = potentialJobId;
            }
        }
    }
    
    // If still not found, try to get from hidden field
    if (!jobId) {
        const jobIdElem = document.getElementById('job_id');
        if (jobIdElem) {
            jobId = jobIdElem.value;
        }
    }

    if (questionId) {
        // We're editing an existing question, load its data
        loadQuestionData(questionId);
    } else if (jobId) {
        // Set the job ID in the hidden field if it's provided in the URL
        document.getElementById('job_id').value = jobId;
    }
});

// Function to load question data for editing
async function loadQuestionData(questionId) {
    // Get job ID from hidden field (should be populated by DOMContentLoaded handler)
    const jobIdElem = document.getElementById('job_id');
    if (!jobIdElem) {
        console.error('Error: Hidden job ID element not found.');
        alert('Error: Required form element is missing. Cannot load question data.');
        return;
    }
    const jobId = jobIdElem.value;

    if (!jobId) {
        console.error('Error: No job ID found for loading question data.');
        alert('Error: Job ID is missing. Cannot load question data.');
        return;
    }

    try {
        const response = await fetch(`/dashboard/jobs/${jobId}/screening-questions/${questionId}/`, {
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            const question = await response.json();

            // Fill the form with the question data
            document.getElementById('question_text').value = question.question_text;
            document.getElementById('question_type').value = question.question_type;
            document.getElementById('required').checked = question.required;

            // Set the question ID in the hidden field
            document.getElementById('question_id').value = question.id;

            // Set the job ID in the hidden field (redundant but safe)
            const jobIdField = document.getElementById('job_id');
            if (jobIdField) {
                jobIdField.value = question.job;
            } else {
                console.warn('Warning: Hidden job ID element not found when setting value from question data.');
            }

            // Show choices section if needed and populate choices
            if (question.question_type === 'CHOICE' || question.question_type === 'MULTIPLE_CHOICE') {
                const choicesSection = document.getElementById('choicesSection');
                if (choicesSection) {
                    choicesSection.classList.remove('hidden');
                }

                if (question.choices && question.choices.length > 0) {
                    // Filter out choices with missing text and map to safe values
                    const validChoices = question.choices
                        .filter(choice => choice && choice.text !== undefined && choice.text !== null)
                        .map(choice => String(choice.text).trim())
                        .filter(text => text !== ''); // Remove empty strings after trimming

                    if (validChoices.length > 0) {
                        const choicesText = validChoices.join('\n');
                        const choicesElement = document.getElementById('choices');
                        if (choicesElement) {
                            choicesElement.value = choicesText;
                        }
                    }
                }
            }

            // Update button text to indicate editing
            const submitButton = document.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.textContent = 'Update Question';
            }
        } else {
            console.error('Failed to load question data:', response.status);
            alert('Failed to load question data for editing.');
        }
    } catch (error) {
        console.error('Error loading question data:', error);
        alert('An error occurred while loading question data.');
    }
}

// Load suggested questions when page loads
document.addEventListener('DOMContentLoaded', loadSuggestedQuestions);

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