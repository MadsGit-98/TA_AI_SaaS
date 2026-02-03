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
const pathSegments = window.location.pathname.split('/').filter(segment => segment !== '');
const jobsIndex = pathSegments.indexOf('jobs');
const jobId = jobsIndex !== -1 && pathSegments[jobsIndex + 1] ? pathSegments[jobsIndex + 1] : null;

// Guard against missing jobId
if (!jobId) {
    console.error('Job ID not found in URL');
}

// Load job data
async function loadJobData() {
    try {
        const response = await fetch(`/api/jobs/jobs/${jobId}/`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
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
            const response = await fetch(`/api/jobs/jobs/${jobId}/`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                },
                body: JSON.stringify(jobData)
            });

            if (response.ok) {
                const result = await response.json();
                alert('Job listing updated successfully!');
                window.location.href = `/dashboard/jobs/${result.id}/`;
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

// Activate job
document.getElementById('activateButton').addEventListener('click', async function() {
    if (!confirm('Are you sure you want to activate this job?')) return;

    try {
        const response = await fetch(`/api/jobs/jobs/${jobId}/activate/`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                'X-CSRFToken': getCookie('csrftoken')
            }
        });

        if (response.ok) {
            alert('Job activated successfully!');
            location.reload(); // Reload to update status
        } else {
            const errorData = await response.json();
            alert(`Error activating job: ${JSON.stringify(errorData)}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while activating the job.');
    }
});

// Deactivate job
document.getElementById('deactivateButton').addEventListener('click', async function() {
    if (!confirm('Are you sure you want to deactivate this job?')) return;

    try {
        const response = await fetch(`/api/jobs/jobs/${jobId}/deactivate/`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                'X-CSRFToken': getCookie('csrftoken')
            }
        });

        if (response.ok) {
            alert('Job deactivated successfully!');
            location.reload(); // Reload to update status
        } else {
            const errorData = await response.json();
            alert(`Error deactivating job: ${JSON.stringify(errorData)}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while deactivating the job.');
    }
});

// Duplicate job
document.getElementById('duplicateButton').addEventListener('click', async function() {
    if (!confirm('Are you sure you want to duplicate this job?')) return;

    try {
        const response = await fetch(`/api/jobs/jobs/${jobId}/duplicate/`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                'X-CSRFToken': getCookie('csrftoken')
            }
        });

        if (response.ok) {
            const result = await response.json();
            alert('Job duplicated successfully!');
            window.location.href = `/dashboard/jobs/${result.id}/edit/`; // Redirect to edit the new job
        } else {
            const errorData = await response.json();
            alert(`Error duplicating job: ${JSON.stringify(errorData)}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while duplicating the job.');
    }
});

// Delete job
document.getElementById('deleteButton').addEventListener('click', async function() {
    if (!confirm('Are you sure you want to delete this job? This action cannot be undone.')) return;

    try {
        const response = await fetch(`/api/jobs/jobs/${jobId}/`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                'X-CSRFToken': getCookie('csrftoken')
            }
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