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
    Render the public application form for a specific job.

    This is an unauthenticated view - anyone with the link can apply.
    """
    # Get job listing by application_link (not id)
    job = get_object_or_404(JobListing, application_link=application_link)

    # Check if job is accepting applications
    if job.status != 'Active':
        return render(request, 'applications/job_closed.html', {'job': job})

    # Get screening questions for this job
    screening_questions = job.screening_questions.filter(required=True).order_by('order')

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
    Render success confirmation page after application submission.

    Requires a valid access token to prevent IDOR attacks.
    Only the holder of the unguessable token can view the success page.
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
    Placeholder for application submission endpoint.
    Future implementation will handle resume uploads.
    """
    return JsonResponse({'status': 'placeholder', 'message': 'Application submission endpoint will be implemented in future features'})
