"""
Template Views for Applications App

Renders HTML templates for:
- Application form
- Success confirmation page
"""

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from apps.jobs.models import JobListing
from apps.applications.models import Applicant


def application_form_view(request, job_id):
    """
    Render the public application form for a specific job.
    
    This is an unauthenticated view - anyone with the link can apply.
    """
    # Get job listing
    job = get_object_or_404(JobListing, id=job_id)
    
    # Check if job is accepting applications
    if job.status != 'Active':
        return render(request, 'applications/job_closed.html', {'job': job})
    
    # Get screening questions for this job
    screening_questions = job.screening_questions.filter(required=True).order_by('order')
    
    context = {
        'job': job,
        'screening_questions': screening_questions,
    }
    
    return render(request, 'applications/application_form.html', context)


def application_success_view(request, application_id):
    """
    Render success confirmation page after application submission.
    """
    # Get application
    applicant = get_object_or_404(Applicant.objects.select_related('job_listing'), id=application_id)
    
    context = {
        'applicant': applicant,
        'job': applicant.job_listing,
    }
    
    return render(request, 'applications/application_success.html', context)


def applications_submit_view(request):
    """
    Placeholder for application submission endpoint.
    Future implementation will handle resume uploads.
    """
    return JsonResponse({'status': 'placeholder', 'message': 'Application submission endpoint will be implemented in future features'})
