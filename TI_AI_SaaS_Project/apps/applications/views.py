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


def application_form_view(request, application_link):
    """
    Render the public, unauthenticated application form for a job identified by its application link.
    
    Retrieves the JobListing by its public application_link (raises 404 if not found). If the job is not in an active state, renders the job_closed template. Otherwise, renders the application_form template with context containing:
    - 'job': the JobListing
    - 'screening_questions': all screening questions for the job ordered by their `order` field
    - 'default_country_code': taken from request.GET['country_code'] if present, otherwise 'US'
    
    Parameters:
        application_link (str): The public, unguessable link identifying the job listing.
    
    Returns:
        HttpResponse: The rendered HTML response (either the application form or job closed page).
    """
    # Get job listing by application_link (not id)
    job = get_object_or_404(JobListing, application_link=application_link)

    # Check if job is accepting applications
    if job.status != 'Active':
        return render(request, 'applications/job_closed.html', {'job': job})

    # Get screening questions for this job (all questions, not just required)
    screening_questions = job.screening_questions.all().order_by('order')

    # Get default country code from request or use US as default
    default_country_code = request.GET.get('country_code', 'US')

    context = {
        'job': job,
        'screening_questions': screening_questions,
        'default_country_code': default_country_code,
    }

    return render(request, 'applications/application_form.html', context)


def application_success_view(request, application_id, access_token):
    """
    Render the application success page for a submitted application when the provided `application_id` and `access_token` identify a valid applicant.
    
    Parameters:
        application_id (int): The Applicant database ID to display.
        access_token (str): Unguessable token that authorizes viewing the success page for the applicant.
    
    Returns:
        HttpResponse: Rendered success page with `applicant` and `job` in the template context.
    
    Raises:
        Http404: If no Applicant exists matching `application_id` and `access_token`.
    """
    # Validate access token to prevent IDOR
    applicant = get_object_or_404(
        Applicant.objects.select_related('job_listing'),
        id=application_id,
        access_token=access_token
    )

    context = {
        'applicant': applicant,
        'job': applicant.job_listing,
    }

    return render(request, 'applications/application_success.html', context)


def applications_submit_view(request):
    """
    Placeholder endpoint for submitting job applications.
    
    This view is a temporary stub; future implementations will handle application data and resume uploads.
    
    Returns:
        JsonResponse: JSON object with `status` set to `"placeholder"` and a `message` indicating the endpoint is not yet implemented.
    """
    return JsonResponse({'status': 'placeholder', 'message': 'Application submission endpoint will be implemented in future features'})
