# Quickstart Guide: Job Listing Management

## Overview
This guide provides a quick introduction to implementing and using the Job Listing Management feature in the X-Crewter platform. This feature allows Talent Acquisition Specialists to create, manage, and expire job listings with associated screening questions.

## Prerequisites
- Python 3.11
- Django 4.x
- Django REST Framework
- Celery with Redis
- UUID library
- Tailwind CSS

## Setup

### 1. Install Dependencies
```bash
pip install djangorestframework djangorestframework-simplejwt djoser celery redis uuid
```

### 2. Add to INSTALLED_APPS in settings.py
```python
INSTALLED_APPS = [
    # ... other apps
    'apps.jobs',
    'rest_framework',
    'celery',
]
```

### 3. Configure Celery for Automatic Job Activation/Deactivation
Add to your main project's `celery.py`:
```python
from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TI_AI_SaaS_Project.settings')

app = Celery('TI_AI_SaaS_Project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Schedule the job status checker to run every minute
app.conf.beat_schedule = {
    'check-job-statuses': {
        'task': 'apps.jobs.tasks.check_job_statuses',
        'schedule': 60.0,  # Every 60 seconds
    },
}
```

### 4. Configure Redis Broker
In your Django settings:
```python
CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_RESULT_BACKEND = 'redis://localhost:6379'
```

## Implementation Steps

### Step 1: Create the Models
Create the JobListing and ScreeningQuestion models in `apps/jobs/models.py`:

```python
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

class JobListing(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    
    JOB_LEVEL_CHOICES = [
        ('Intern', 'Intern'),
        ('Entry', 'Entry'),
        ('Junior', 'Junior'),
        ('Senior', 'Senior'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=3000)
    required_skills = models.JSONField()
    required_experience = models.IntegerField(validators=[MinValueValidator(0)])
    job_level = models.CharField(max_length=10, choices=JOB_LEVEL_CHOICES)
    start_date = models.DateTimeField()
    expiration_date = models.DateTimeField()
    modification_date = models.DateTimeField(auto_now_add=True)  # Initially equals start_date
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Inactive')
    application_link = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        # Ensure modification date equals start date when first created
        if not self.pk:  # If this is a new object
            self.modification_date = self.start_date
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class ScreeningQuestion(models.Model):
    QUESTION_TYPE_CHOICES = [
        ('TEXT', 'Text'),
        ('YES_NO', 'Yes/No'),
        ('CHOICE', 'Choice'),
        ('MULTIPLE_CHOICE', 'Multiple Choice'),
        ('FILE_UPLOAD', 'File Upload'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_listing = models.ForeignKey(JobListing, on_delete=models.CASCADE, related_name='screening_questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    required = models.BooleanField(default=True)
    order = models.IntegerField(null=True, blank=True)
    choices = models.JSONField(null=True, blank=True)  # For choice-based questions
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.job_listing.title}: {self.question_text}"
```

### Step 2: Create Serializers
Create serializers in `apps/jobs/serializers.py`:

```python
from rest_framework import serializers
from .models import JobListing, ScreeningQuestion

class ScreeningQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScreeningQuestion
        fields = '__all__'

class JobListingSerializer(serializers.ModelSerializer):
    screening_questions = ScreeningQuestionSerializer(many=True, read_only=True)
    
    class Meta:
        model = JobListing
        fields = '__all__'
        read_only_fields = ('id', 'application_link', 'created_at', 'updated_at', 'created_by')

class JobListingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobListing
        fields = [
            'title', 'description', 'required_skills', 'required_experience',
            'job_level', 'start_date', 'expiration_date'
        ]
    
    def validate(self, data):
        start_date = data.get('start_date')
        expiration_date = data.get('expiration_date')
        
        if start_date and expiration_date and start_date > expiration_date:
            raise serializers.ValidationError("Expiration date must be after start date.")
        
        return data
```

### Step 3: Create Views
Create views in `apps/jobs/views.py`:

```python
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import JobListing, ScreeningQuestion
from .serializers import JobListingSerializer, JobListingCreateSerializer, ScreeningQuestionSerializer

class JobListingListView(generics.ListCreateAPIView):
    queryset = JobListing.objects.all()
    serializer_class = JobListingSerializer
    
    def get_queryset(self):
        queryset = JobListing.objects.all()
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class JobListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = JobListing.objects.all()
    serializer_class = JobListingSerializer

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activate_job(request, pk):
    job = get_object_or_404(JobListing, pk=pk)
    job.status = 'Active'
    job.save()
    serializer = JobListingSerializer(job)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deactivate_job(request, pk):
    job = get_object_or_404(JobListing, pk=pk)
    job.status = 'Inactive'
    job.save()
    serializer = JobListingSerializer(job)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def duplicate_job(request, pk):
    original_job = get_object_or_404(JobListing, pk=pk)
    
    # Create a new job with the same details but different ID
    original_job.id = None  # Reset the ID to create a new instance
    original_job.title = f"{original_job.title} (Copy)"
    original_job.status = 'Inactive'  # New copies start as inactive
    original_job.application_link = uuid.uuid4()  # Generate new application link
    original_job.created_by = request.user
    original_job.save()
    
    # Copy associated screening questions
    original_questions = ScreeningQuestion.objects.filter(job_listing_id=pk)
    for question in original_questions:
        question.id = None  # Reset the ID
        question.job_listing = original_job
        question.save()
    
    serializer = JobListingSerializer(original_job)
    return Response(serializer.data, status=status.HTTP_201_CREATED)

class ScreeningQuestionListView(generics.ListCreateAPIView):
    serializer_class = ScreeningQuestionSerializer
    
    def get_queryset(self):
        job_id = self.kwargs['job_id']
        return ScreeningQuestion.objects.filter(job_listing_id=job_id)
    
    def perform_create(self, serializer):
        job_id = self.kwargs['job_id']
        job = get_object_or_404(JobListing, pk=job_id)
        serializer.save(job_listing=job)

class ScreeningQuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ScreeningQuestion.objects.all()
    serializer_class = ScreeningQuestionSerializer
```

### Step 4: Configure URLs
Set up URLs in `apps/jobs/urls.py`:

```python
from django.urls import path
from .views import (
    JobListingListView, JobListingDetailView, 
    activate_job, deactivate_job, duplicate_job,
    ScreeningQuestionListView, ScreeningQuestionDetailView
)

urlpatterns = [
    path('jobs/', JobListingListView.as_view(), name='job-listing-list'),
    path('jobs/<uuid:pk>/', JobListingDetailView.as_view(), name='job-listing-detail'),
    path('jobs/<uuid:pk>/activate/', activate_job, name='job-activate'),
    path('jobs/<uuid:pk>/deactivate/', deactivate_job, name='job-deactivate'),
    path('jobs/<uuid:pk>/duplicate/', duplicate_job, name='job-duplicate'),
    path('jobs/<uuid:job_id>/screening-questions/', ScreeningQuestionListView.as_view(), name='screening-question-list'),
    path('jobs/<uuid:job_id>/screening-questions/<uuid:pk>/', ScreeningQuestionDetailView.as_view(), name='screening-question-detail'),
]
```

Include these URLs in your main `urls.py`:
```python
from django.urls import path, include

urlpatterns = [
    # ... other URLs
    path('api/', include('apps.jobs.urls')),
]
```

### Step 5: Create Celery Task for Automatic Status Updates
Create or update `apps/jobs/tasks.py`:

```python
from celery import shared_task
from django.utils import timezone
from .models import JobListing

@shared_task
def check_job_statuses():
    """
    Task to check and update job statuses based on start and expiration dates
    """
    now = timezone.now()
    
    # Activate jobs whose start date has arrived
    JobListing.objects.filter(
        start_date__lte=now,
        expiration_date__gte=now,
        status='Inactive'
    ).update(status='Active')
    
    # Deactivate jobs whose expiration date has passed
    JobListing.objects.filter(
        expiration_date__lt=now,
        status='Active'
    ).update(status='Inactive')
    
    return f"Checked job statuses at {now}. Updated records as needed."
```

### Step 6: Create Frontend Components
Create a basic template in `apps/jobs/templates/jobs/job_listings.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Listings - X-Crewter</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#FFFFFF] text-[#000000]">
    <div class="container mx-auto px-4 py-8">
        <h1 class="text-3xl font-bold mb-6">Manage Job Listings</h1>
        
        <div class="mb-6">
            <button id="createJobBtn" class="bg-[#080707] text-[#FFFFFF] px-4 py-2 rounded hover:bg-gray-800 transition">
                Create New Job Listing
            </button>
        </div>
        
        <div id="jobListingsContainer">
            <!-- Job listings will be loaded here dynamically -->
        </div>
    </div>

    <script>
        // JavaScript for interacting with the job listings API
        document.addEventListener('DOMContentLoaded', function() {
            loadJobListings();
            
            document.getElementById('createJobBtn').addEventListener('click', function() {
                window.location.href = '/jobs/create/';
            });
        });

        async function loadJobListings() {
            try {
                const response = await fetch('/api/jobs/');
                const jobListings = await response.json();
                
                const container = document.getElementById('jobListingsContainer');
                container.innerHTML = '';
                
                jobListings.results.forEach(job => {
                    const jobElement = document.createElement('div');
                    jobElement.className = 'border border-gray-200 rounded-lg p-4 mb-4';
                    jobElement.innerHTML = `
                        <h2 class="text-xl font-semibold">${job.title}</h2>
                        <p class="text-gray-600">${job.description.substring(0, 100)}...</p>
                        <div class="mt-2">
                            <span class="inline-block bg-gray-200 rounded-full px-3 py-1 text-sm font-semibold mr-2">
                                ${job.job_level}
                            </span>
                            <span class="inline-block bg-gray-200 rounded-full px-3 py-1 text-sm font-semibold mr-2">
                                ${job.required_experience} yrs exp
                            </span>
                            <span class="inline-block ${job.status === 'Active' ? 'bg-green-200' : 'bg-red-200'} rounded-full px-3 py-1 text-sm font-semibold">
                                ${job.status}
                            </span>
                        </div>
                        <div class="mt-3 flex space-x-2">
                            <button onclick="editJob('${job.id}')" class="text-blue-600 hover:text-blue-800">Edit</button>
                            <button onclick="copyApplicationLink('${job.application_link}')" class="text-blue-600 hover:text-blue-800">Copy Link</button>
                            ${job.status === 'Active' 
                                ? `<button onclick="deactivateJob('${job.id}')" class="text-red-600 hover:text-red-800">Deactivate</button>` 
                                : `<button onclick="activateJob('${job.id}')" class="text-green-600 hover:text-green-800">Activate</button>`
                            }
                            <button onclick="duplicateJob('${job.id}')" class="text-purple-600 hover:text-purple-800">Duplicate</button>
                        </div>
                    `;
                    container.appendChild(jobElement);
                });
            } catch (error) {
                console.error('Error loading job listings:', error);
            }
        }

        async function activateJob(jobId) {
            try {
                await fetch(`/api/jobs/${jobId}/activate/`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                        'Content-Type': 'application/json'
                    }
                });
                loadJobListings(); // Refresh the list
            } catch (error) {
                console.error('Error activating job:', error);
            }
        }

        async function deactivateJob(jobId) {
            try {
                await fetch(`/api/jobs/${jobId}/deactivate/`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                        'Content-Type': 'application/json'
                    }
                });
                loadJobListings(); // Refresh the list
            } catch (error) {
                console.error('Error deactivating job:', error);
            }
        }

        async function duplicateJob(jobId) {
            try {
                const response = await fetch(`/api/jobs/${jobId}/duplicate/`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                        'Content-Type': 'application/json'
                    }
                });
                
                if (response.ok) {
                    loadJobListings(); // Refresh the list
                }
            } catch (error) {
                console.error('Error duplicating job:', error);
            }
        }

        function copyApplicationLink(link) {
            navigator.clipboard.writeText(`${window.location.origin}/apply/${link}`)
                .then(() => {
                    alert('Application link copied to clipboard!');
                })
                .catch(err => {
                    console.error('Failed to copy link: ', err);
                });
        }

        function editJob(jobId) {
            window.location.href = `/jobs/edit/${jobId}`;
        }
    </script>
</body>
</html>
```

## Running the Application

1. Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

2. Start the Django development server:
```bash
python manage.py runserver
```

3. In a separate terminal, start the Celery worker:
```bash
celery -A TI_AI_SaaS_Project worker -l info
```

4. In another terminal, start the Celery beat scheduler:
```bash
celery -A TI_AI_SaaS_Project beat -l info
```

## API Usage Examples

### Create a Job Listing
```bash
curl -X POST http://localhost:8000/api/jobs/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "title": "Software Engineer",
    "description": "We are looking for a skilled software engineer...",
    "required_skills": ["Python", "Django", "REST API"],
    "required_experience": 3,
    "job_level": "Senior",
    "start_date": "2023-06-01T09:00:00Z",
    "expiration_date": "2023-07-01T09:00:00Z"
  }'
```

### Get All Job Listings
```bash
curl -X GET http://localhost:8000/api/jobs/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Activate a Job Listing
```bash
curl -X POST http://localhost:8000/api/jobs/JOB_ID_HERE/activate/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Testing

Create tests in `apps/jobs/tests/` following the required structure:
- Unit tests in `apps/jobs/tests/unit/`
- Integration tests in `apps/jobs/tests/integration/`
- E2E tests in `apps/jobs/tests/e2e/`
- Security tests in `apps/jobs/tests/security/`

Example unit test:
```python
from django.test import TestCase
from django.contrib.auth.models import User
from ..models import JobListing

class JobListingModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
    
    def test_create_job_listing(self):
        job = JobListing.objects.create(
            title="Test Job",
            description="Test Description",
            required_skills=["Python"],
            required_experience=2,
            job_level="Senior",
            start_date="2023-06-01T09:00:00Z",
            expiration_date="2023-07-01T09:00:00Z",
            created_by=self.user
        )
        
        self.assertEqual(job.title, "Test Job")
        self.assertEqual(job.status, "Inactive")  # Default status
```