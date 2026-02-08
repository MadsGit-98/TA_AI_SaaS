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

    // Get job ID from URL parameters or hidden form field
    const urlParams = new URLSearchParams(window.location.search);
    const jobIdFromUrl = urlParams.get('job_id');
    const jobIdEl = document.getElementById('job_id');
    const jobIdFromHiddenField = jobIdEl ? jobIdEl.value : '';

    const jobId = jobIdFromUrl || jobIdFromHiddenField;

    if (!jobId) {
        console.error('Error: No job ID found. Cannot submit screening question.');
        alert('Error: Job ID is missing. Please go back and try again.');
        return;
    }

    try {
        const response = await fetch(`/dashboard/jobs/${jobId}/screening-questions/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            },
            credentials: 'include',  // Include cookies in request (handles JWT tokens automatically)
            body: JSON.stringify(questionData)
        });

        if (response.ok) {
            const result = await response.json();
            alert('Screening question added successfully!');
            // Redirect back to job detail page or clear form
            document.getElementById('screeningQuestionForm').reset();
            // Hide choices section if it was visible
            document.getElementById('choicesSection').classList.add('hidden');
        } else {
            const rawBody = await response.text();
            let errorData;
            try {
                errorData = JSON.parse(rawBody);
            } catch (e) {
                // If response is not JSON, use the raw text
                errorData = rawBody;
            }

            console.error('Error adding screening question:', errorData);
            alert('Failed to add screening question. Please try again.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while adding the screening question.');
    }
});

// Load suggested questions when page loads
document.addEventListener('DOMContentLoaded', loadSuggestedQuestions);