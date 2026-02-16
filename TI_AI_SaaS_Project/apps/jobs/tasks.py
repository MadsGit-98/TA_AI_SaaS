from django.utils import timezone
from datetime import timedelta
from x_crewter.celery import app
from apps.jobs.models import JobListing
import logging

logger = logging.getLogger(__name__)


@app.task
def check_job_statuses():
    """
    Update job listings' statuses based on their start and expiration dates.
    
    Evaluates listings against the current time and a one-day buffer: jobs with start_date within the buffer and not expired are marked Active; jobs with expiration_date within the buffer are marked Inactive. Logs counts of activated and deactivated records.
    
    Returns:
        result (dict): Dictionary with keys:
            - 'timestamp' (str): ISO-formatted current time when the check ran.
            - 'activated_jobs' (int): Number of listings set to Active.
            - 'deactivated_jobs' (int): Number of listings set to Inactive.
    """
    buffered_time = timezone.now() + timedelta(days=1)
    current_time = timezone.now()

    # Activate jobs whose start date has arrived and are not yet expired
    activated_count = JobListing.objects.filter(
        start_date__lte=buffered_time,
        expiration_date__gt=current_time,
        status='Inactive'
    ).update(status='Active', updated_at=current_time)

    # Deactivate jobs whose expiration date has passed
    deactivated_count = JobListing.objects.filter(
        expiration_date__lt=buffered_time,
        status='Active'
    ).update(status='Inactive', updated_at=current_time)

    logger.info(f"Checked job statuses at {current_time}. Activated {activated_count} jobs, deactivated {deactivated_count} jobs.")

    return {
        'timestamp': current_time.isoformat(),
        'activated_jobs': activated_count,
        'deactivated_jobs': deactivated_count
    }


@app.task
def cleanup_expired_jobs():
    """
    Identify active job listings whose expiration_date is earlier than the current time and perform optional cleanup actions.
    
    Materializes the matching queryset and logs each expired job. The function is intended for additional cleanup (archiving, notifications, etc.) but currently only logs expired entries.
    
    Returns:
        dict: {'expired_jobs_count': int} — the number of active job listings with expiration_date before the current time.
    """
    now = timezone.now()

    # This could include archiving old jobs, sending notifications, etc.
    expired_jobs = JobListing.objects.filter(
        expiration_date__lt=now,
        status='Active'
    )

    # Materialize the queryset once to avoid multiple DB queries
    expired_jobs_list = list(expired_jobs)
    expired_count = len(expired_jobs_list)

    logger.info(f"Found {expired_count} jobs that may need cleanup.")

    # Additional cleanup logic can be added here if needed
    # For now, we just log the jobs that have expired
    for job in expired_jobs_list:
        logger.info(f"Job {job.id} ({job.title}) has expired and may need cleanup.")

    return {'expired_jobs_count': expired_count}