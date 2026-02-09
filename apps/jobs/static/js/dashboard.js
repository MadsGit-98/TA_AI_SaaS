
// Helper function to escape HTML
function escapeHtml(text) {
    // Coerce input to string, handling null/undefined safely
    text = String(text == null ? '' : text);

    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// Helper function to create job element
function createJobElement(job, container) {
    const jobElement = document.createElement('div');
    jobElement.className = 'border border-gray-200 rounded-lg p-4 bg-white';

    // Format dates
    const startDate = job.start_date ? new Date(job.start_date).toLocaleDateString() : 'Not set';
    const expirationDate = job.expiration_date ? new Date(job.expiration_date).toLocaleDateString() : 'Not set';

    // Create the content using safe DOM manipulation
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'flex justify-between items-start';

    // Left side content
    const leftSide = document.createElement('div');

    const titleElement = document.createElement('h2');
    titleElement.className = 'text-xl font-semibold';
    titleElement.textContent = job.title;
    leftSide.appendChild(titleElement);

    const descElement = document.createElement('p');
    descElement.className = 'text-gray-600';
    const desc = job.description || '';
    const descText = desc.length > 100 ?
        desc.substring(0, 100) + '...' :
        desc;
    descElement.textContent = descText;
    leftSide.appendChild(descElement);

    // Tags container
    const tagsContainer = document.createElement('div');
    tagsContainer.className = 'mt-2 flex flex-wrap gap-2';

    // Job level tag
    const levelTag = document.createElement('span');
    levelTag.className = 'inline-block bg-gray-200 rounded-full px-3 py-1 text-sm font-semibold text-gray-700';
    levelTag.textContent = job.job_level;
    tagsContainer.appendChild(levelTag);

    // Experience tag
    const expTag = document.createElement('span');
    expTag.className = 'inline-block bg-gray-200 rounded-full px-3 py-1 text-sm font-semibold text-gray-700';
    expTag.textContent = job.required_experience + ' yrs exp';
    tagsContainer.appendChild(expTag);

    // Status tag
    const statusTag = document.createElement('span');
    const statusClass = job.status === 'Active' ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800';
    statusTag.className = `inline-block ${statusClass} rounded-full px-3 py-1 text-sm font-semibold`;
    statusTag.textContent = job.status;
    tagsContainer.appendChild(statusTag);

    // Start date tag
    const startTag = document.createElement('span');
    startTag.className = 'inline-block bg-gray-200 rounded-full px-3 py-1 text-sm font-semibold text-gray-700';
    startTag.textContent = 'Starts: ' + startDate;
    tagsContainer.appendChild(startTag);

    // Expiration date tag
    const expDateTag = document.createElement('span');
    expDateTag.className = 'inline-block bg-gray-200 rounded-full px-3 py-1 text-sm font-semibold text-gray-700';
    expDateTag.textContent = 'Expires: ' + expirationDate;
    tagsContainer.appendChild(expDateTag);

    leftSide.appendChild(tagsContainer);

    // Right side buttons
    const rightSide = document.createElement('div');
    rightSide.className = 'flex flex-col space-y-2';

    // Edit button
    const editButton = document.createElement('button');
    editButton.className = 'text-blue-600 hover:text-blue-800 text-sm';
    editButton.textContent = 'Edit';
    editButton.addEventListener('click', () => editJob(job.id));
    rightSide.appendChild(editButton);

    // Copy link button
    const copyButton = document.createElement('button');
    copyButton.className = 'text-blue-600 hover:text-blue-800 text-sm';
    
    // Check if application link exists and is valid
    if (job.application_link && typeof job.application_link === 'string' && job.application_link.trim() !== '') {
        copyButton.textContent = 'Copy Link';
        copyButton.addEventListener('click', () => copyApplicationLink(job.application_link));
    } else {
        copyButton.textContent = 'No Link Available';
        copyButton.disabled = true;
        copyButton.classList.add('opacity-50', 'cursor-not-allowed');
    }
    rightSide.appendChild(copyButton);

    // Conditional status button
    let statusButton;
    if (job.status === 'Active') {
        statusButton = document.createElement('button');
        statusButton.className = 'text-red-600 hover:text-red-800 text-sm';
        statusButton.textContent = 'Deactivate';
        statusButton.addEventListener('click', () => deactivateJob(job.id));
    } else {
        statusButton = document.createElement('button');
        statusButton.className = 'text-green-600 hover:text-green-800 text-sm';
        statusButton.textContent = 'Activate';
        statusButton.addEventListener('click', () => activateJob(job.id));
    }
    rightSide.appendChild(statusButton);

    // Duplicate button
    const duplicateButton = document.createElement('button');
    duplicateButton.className = 'text-purple-600 hover:text-purple-800 text-sm';
    duplicateButton.textContent = 'Duplicate';
    duplicateButton.addEventListener('click', () => duplicateJob(job.id));
    rightSide.appendChild(duplicateButton);

    // Assemble the content
    contentWrapper.appendChild(leftSide);
    contentWrapper.appendChild(rightSide);
    jobElement.appendChild(contentWrapper);

    container.appendChild(jobElement);
}

// Load job listings
async function loadJobListings(page = 1) {
    try {
        // Get filter values
        const statusFilter = document.getElementById('statusFilter').value;
        const dateRangeFilter = document.getElementById('dateRangeFilter').value;
        const jobLevelFilter = document.getElementById('jobLevelFilter').value;
        const searchFilter = document.getElementById('searchFilter').value;

        // Build query string
        let queryString = `?page=${page}`;
        if (statusFilter) queryString += `&status=${encodeURIComponent(statusFilter)}`;
        if (dateRangeFilter) queryString += `&date_range=${encodeURIComponent(dateRangeFilter)}`;
        if (jobLevelFilter) queryString += `&job_level=${encodeURIComponent(jobLevelFilter)}`;
        if (searchFilter) queryString += `&search=${encodeURIComponent(searchFilter)}`;

        const response = await fetch(`/dashboard/jobs/${queryString}`, {
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            const data = await response.json();
            const container = document.getElementById('jobListingsContainer');

            // Check if data has the expected structure with results array
            if (!data.hasOwnProperty('results')) {
                // If there's no 'results' property, check if it's a direct array or an error
                if (data.error || data.detail) {
                    // It's an error response
                    const errorElement = document.createElement('p');
                    errorElement.className = 'text-center text-red-500';
                    errorElement.textContent = `Error: ${data.error || data.detail}`;
                    container.innerHTML = ''; // Clear the container first
                    container.appendChild(errorElement);
                    document.getElementById('paginationContainer').innerHTML = '';
                    return;
                } else if (Array.isArray(data)) {
                    // It's a direct array of jobs (not paginated)
                    if (data.length === 0) {
                        const noJobsElement = document.createElement('p');
                        noJobsElement.className = 'text-center text-gray-500';
                        noJobsElement.textContent = 'No job listings found.';
                        container.innerHTML = ''; // Clear the container first
                        container.appendChild(noJobsElement);
                        document.getElementById('paginationContainer').innerHTML = '';
                        return;
                    }
                    
                    // Process the direct array
                    container.innerHTML = '';
                    data.forEach(job => {
                        createJobElement(job, container);
                    });
                    
                    // No pagination for non-paginated response
                    document.getElementById('paginationContainer').innerHTML = '';
                    return;
                } else {
                    // Unexpected response structure
                    console.error('Unexpected API response structure:', data);
                    const errorElement = document.createElement('p');
                    errorElement.className = 'text-center text-red-500';
                    errorElement.textContent = 'Unexpected API response structure.';
                    container.innerHTML = ''; // Clear the container first
                    container.appendChild(errorElement);
                    document.getElementById('paginationContainer').innerHTML = '';
                    return;
                }
            }

            // Process paginated response
            if (data.results.length === 0) {
                const noJobsElement = document.createElement('p');
                noJobsElement.className = 'text-center text-gray-500';
                noJobsElement.textContent = 'No job listings found.';
                container.innerHTML = ''; // Clear the container first
                container.appendChild(noJobsElement);
                document.getElementById('paginationContainer').innerHTML = '';
                return;
            }

            container.innerHTML = '';
            data.results.forEach(job => {
                createJobElement(job, container);
            });

            // Handle pagination
            renderPagination(data);
        } else {
            console.error('Failed to load job listings');
            const container = document.getElementById('jobListingsContainer');
            const errorElement = document.createElement('p');
            errorElement.className = 'text-center text-red-500';
            errorElement.textContent = 'Failed to load job listings. Please try again.';
            container.innerHTML = ''; // Clear the container first
            container.appendChild(errorElement);
        }
    } catch (error) {
        console.error('Error loading job listings:', error);
    }
}

// Render pagination controls
function renderPagination(data) {
    const container = document.getElementById('paginationContainer');
    container.innerHTML = '';

    if (!data.next && !data.previous) return; // No pagination needed

    const paginationDiv = document.createElement('div');
    paginationDiv.className = 'flex items-center space-x-2';

    // Previous button
    if (data.previous) {
        const prevButton = document.createElement('button');
        prevButton.textContent = 'Previous';
        prevButton.className = 'px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50';
        prevButton.onclick = () => loadJobListings(getPageNumberFromUrl(data.previous));
        paginationDiv.appendChild(prevButton);
    }

    // Next button
    if (data.next) {
        const nextButton = document.createElement('button');
        nextButton.textContent = 'Next';
        nextButton.className = 'px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 ml-2';
        nextButton.onclick = () => loadJobListings(getPageNumberFromUrl(data.next));
        paginationDiv.appendChild(nextButton);
    }

    container.appendChild(paginationDiv);
}

// Helper to extract page number from URL
function getPageNumberFromUrl(url) {
    // Check if URL is a non-empty string
    if (!url || typeof url !== 'string' || url.trim() === '') {
        return 1;
    }

    // Extract query string part after '?'
    const urlParts = url.split('?');
    if (urlParts.length < 2) {
        return 1;
    }

    const urlParams = new URLSearchParams(urlParts[1]);
    const pageParam = urlParams.get('page');

    // Parse the page parameter to number, fallback to 1 if parsing fails
    const pageNumber = parseInt(pageParam, 10);
    return isNaN(pageNumber) ? 1 : pageNumber;
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

// Job management functions
function editJob(jobId) {
    window.location.href = `/dashboard/${jobId}/edit/`;
}

async function activateJob(jobId) {
    if (!confirm('Are you sure you want to activate this job?')) return;

    try {
        const response = await fetch(`/dashboard/jobs/${jobId}/activate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            alert('Job activated successfully!');
            loadJobListings(); // Refresh the list
        } else {
            const errorData = await response.json();
            alert(`Error activating job: ${JSON.stringify(errorData)}`);
        }
    } catch (error) {
        console.error('Error activating job:', error);
        alert('An error occurred while activating the job.');
    }
}

async function deactivateJob(jobId) {
    if (!confirm('Are you sure you want to deactivate this job?')) return;

    try {
        const response = await fetch(`/dashboard/jobs/${jobId}/deactivate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            alert('Job deactivated successfully!');
            loadJobListings(); // Refresh the list
        } else {
            const errorData = await response.json();
            alert(`Error deactivating job: ${JSON.stringify(errorData)}`);
        }
    } catch (error) {
        console.error('Error deactivating job:', error);
        alert('An error occurred while deactivating the job.');
    }
}

async function duplicateJob(jobId) {
    if (!confirm('Are you sure you want to duplicate this job?')) return;

    try {
        const response = await fetch(`/dashboard/jobs/${jobId}/duplicate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'include'  // Include cookies in request (handles JWT tokens automatically)
        });

        if (response.ok) {
            const result = await response.json();
            if (result && (typeof result.id === 'number' || (typeof result.id === 'string' && result.id.trim() !== ''))) {
                alert('Job duplicated successfully!');
                window.location.href = `/dashboard/${result.id}/edit/`; // Redirect to edit the new job
            } else {
                console.error('Invalid or missing ID in duplication response:', result);
                alert('Job duplicated successfully but failed to redirect. Please refresh the page to see the new job.');
            }
        } else {
            const errorData = await response.json();
            alert(`Error duplicating job: ${JSON.stringify(errorData)}`);
        }
    } catch (error) {
        console.error('Error duplicating job:', error);
        alert('An error occurred while duplicating the job.');
    }
}

function copyApplicationLink(link) {
    const fullLink = `${window.location.origin}/apply/${link}`;
    navigator.clipboard.writeText(fullLink)
        .then(() => {
            alert('Application link copied to clipboard!');
        })
        .catch(err => {
            console.error('Failed to copy link: ', err);
            alert('Failed to copy link to clipboard.');
        });
}

// Set up filter event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('statusFilter').addEventListener('change', () => loadJobListings());
    document.getElementById('dateRangeFilter').addEventListener('change', () => loadJobListings());
    document.getElementById('jobLevelFilter').addEventListener('change', () => loadJobListings());
    document.getElementById('searchFilter').addEventListener('input', () => {
        // Debounce the search
        clearTimeout(window.searchTimeout);
        window.searchTimeout = setTimeout(() => loadJobListings(), 500);
    });

    // Load job listings when page loads
    loadJobListings();
});