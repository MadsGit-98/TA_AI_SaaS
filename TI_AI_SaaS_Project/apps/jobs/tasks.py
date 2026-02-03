from celery import shared_task
from django.utils import timezone
from django.conf import settings
from apps.jobs.models import JobListing
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_job_statuses():
    """
    Task to check and update job statuses based on start and expiration dates
    """
    now = timezone.now()

    # Activate jobs whose start date has arrived and are not yet expired
    activated_count = JobListing.objects.filter(
        start_date__lte=now,
        expiration_date__gte=now,
        status='Inactive'
    ).update(status='Active', updated_at=now)

    # Deactivate jobs whose expiration date has passed
    deactivated_count = JobListing.objects.filter(
        expiration_date__lt=now,
        status='Active'
    ).update(status='Inactive', updated_at=now)

    logger.info(f"Checked job statuses at {now}. Activated {activated_count} jobs, deactivated {deactivated_count} jobs.")

    return {
        'timestamp': now.isoformat(),
        'activated_jobs': activated_count,
        'deactivated_jobs': deactivated_count
    }


@shared_task
def cleanup_expired_jobs():
    """
    Task to perform additional cleanup for expired jobs if needed
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