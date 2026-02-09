from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from apps.jobs.models import JobListing


@login_required
def dashboard_view(request):
    """
    Job listings dashboard view
    """
    return render(request, 'dashboard.html', {})


@login_required
def create_job_view(request):
    """
    Create new job listing view
    """
    return render(request, 'jobs/create_job.html', {})


@login_required
def edit_job_view(request, job_id):
    """
    Edit job listing view
    """
    # Fetch the job and verify ownership
    job = get_object_or_404(JobListing, pk=job_id)

    # Verify that the current user owns this job
    if job.created_by != request.user:
        raise PermissionDenied("You do not have permission to edit this job.")

    context = {'job': job}
    return render(request, 'jobs/edit_job.html', context)


@login_required
def add_screening_question_view(request, job_id):
    """
    Add screening question view
    """
    # Fetch the job and verify ownership
    job = get_object_or_404(JobListing, pk=job_id)

    # Verify that the current user owns this job
    if job.created_by != request.user:
        raise PermissionDenied("You do not have permission to add screening questions to this job.")

    context = {'job': job}
    return render(request, 'jobs/add_screening_question.html', context)
