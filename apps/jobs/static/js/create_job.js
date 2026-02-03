document.getElementById('jobCreationForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    // Client-side validation for date fields
    const startDateInput = document.getElementById('start_date');
    const expirationDateInput = document.getElementById('expiration_date');
    
    if (startDateInput.value && expirationDateInput.value) {
        const startDate = new Date(startDateInput.value);
        const expirationDate = new Date(expirationDateInput.value);
        
        if (expirationDate <= startDate) {
            alert('Expiration date must be after start date.');
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
        const response = await fetch('/api/jobs/jobs/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,  // Assuming JWT token is stored
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            },
            body: JSON.stringify(jobData)
        });

        if (response.ok) {
            const result = await response.json();
            if (result && result.id) {
                alert('Job listing created successfully!');
                window.location.href = `/dashboard/jobs/${result.id}/`;
            } else {
                console.error('Unexpected response format:', result);
                alert('Job listing created successfully but ID not returned. Redirecting to dashboard.');
                window.location.href = '/dashboard/';
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
            
            alert(`Error creating job listing: ${userMessage}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while creating the job listing.');
    }
});

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