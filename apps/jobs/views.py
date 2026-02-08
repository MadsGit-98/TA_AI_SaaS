from django.shortcuts import render
from django.contrib.auth.decorators import login_required


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
    context = {'job_id': job_id}
    return render(request, 'jobs/edit_job.html', context)


@login_required
def add_screening_question_view(request, job_id):
    """
    Add screening question view
    """
    context = {'job_id': job_id}
    return render(request, 'jobs/add_screening_question.html', context)
