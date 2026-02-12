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
    alert('Error: Unable to determine job ID from URL. Please navigate to this page from the dashboard.');
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
        } else if (response.status === 404) {
            // If the job doesn't exist (e.g., it was deleted), don't show an error
            // This prevents the error message from showing after deletion
            console.log('Job not found, possibly deleted');
        } else {
            alert('Failed to load job data');
        }
    } catch (error) {
        console.error('Error loading job data:', error);
        alert('An error occurred while loading job data.');
    }
}

// Update job listing
const jobEditForm = document.getElementById('jobEditForm');
if (jobEditForm) {
    jobEditForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Check if jobId is missing before proceeding
        if (window.jobIdMissing) {
            alert('Error: Cannot update job. Job ID is missing.');
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
                const result = await response.json();
                alert('Job listing updated successfully!');
                window.location.href = '/dashboard/';
            } else {
                let errorMessage = `HTTP ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMessage = JSON.stringify(errorData);
                } catch { /* Response not JSON */ }
                alert(`Error updating job listing: ${errorMessage}`);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while updating the job listing.');
        }
    });
}

// Delete job
document.getElementById('deleteButton').addEventListener('click', async function() {
    // Check if jobId is missing before proceeding
    if (window.jobIdMissing) {
        alert('Error: Cannot delete job. Job ID is missing.');
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
            alert('Job deleted successfully!');
            window.location.href = '/dashboard/'; // Redirect to dashboard
        } else {
            const errorData = await response.json();
            alert(`Error deleting job: ${JSON.stringify(errorData)}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while deleting the job.');
    }
});

// Load job data when page loads
document.addEventListener('DOMContentLoaded', loadJobData);

// Set up logout event listener
document.addEventListener('DOMContentLoaded', function() {
    const logoutLink = document.getElementById('logout-link');
    if (logoutLink) {
        logoutLink.addEventListener('click', async function(e) {
            e.preventDefault();

            try {
                const response = await fetch('/api/accounts/auth/logout/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content'),
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