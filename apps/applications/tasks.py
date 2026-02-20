"""
Celery tasks for the applications app.
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
from apps.applications.models import Applicant

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_application_confirmation_email(self, applicant_id: str):
    """
    Send confirmation email to applicant after successful submission.
    
    Args:
        applicant_id: UUID of the applicant
    """
    try:
        applicant = Applicant.objects.get(id=applicant_id)
        
        # Email subject
        subject = f"Application Received - {applicant.job_listing.title}"
        
        # Email context
        context = {
            'applicant': applicant,
            'job_listing': applicant.job_listing,
            'submitted_at': applicant.submitted_at,
        }
        
        # Render HTML and plain text versions
        html_content = render_to_string(
            'applications/emails/confirmation_email.html',
            context
        )
        plain_content = render_to_string(
            'applications/emails/confirmation_email.txt',
            context
        )
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_content,
            from_email='noreply@x-crewter.com',
            to=[applicant.email],
        )
        email.attach_alternative(html_content, 'text/html')
        
        # Send email
        email.send()
        
        logger.info(f"Confirmation email sent to {applicant.email} for application {applicant_id}")
        
    except Applicant.DoesNotExist:
        logger.error(f"Applicant {applicant_id} not found")
        # Don't retry if applicant doesn't exist
        return
    except Exception as exc:
        logger.error(f"Failed to send email to {applicant.email}: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def cleanup_expired_applications():
    """
    Delete applications older than 90 days per data retention policy.
    
    This task:
    1. Queries applications older than 90 days
    2. Deletes associated files from storage
    3. Deletes database records
    4. Logs deletion count
    """
    expiry_date = timezone.now() - timedelta(days=90)
    expired = Applicant.objects.filter(submitted_at__lt=expiry_date)
    
    count = expired.count()
    
    if count == 0:
        logger.info("No expired applications to clean up")
        return
    
    # Delete files from storage first
    for applicant in expired:
        try:
            if applicant.resume_file:
                applicant.resume_file.delete(save=False)
                logger.debug(f"Deleted resume file for applicant {applicant.id}")
        except Exception as e:
            logger.error(f"Failed to delete file for applicant {applicant.id}: {e}")
    
    # Then delete records
    deleted_count, _ = expired.delete()
    
    logger.info(f"Cleaned up {deleted_count} expired applications older than {expiry_date}")


@shared_task
def check_duplicate_resumes():
    """
    Periodic task to check for potential duplicate resumes that may have slipped through.
    
    This is a safety net task that runs daily to identify any duplicates that might
    have been submitted concurrently (before database constraints could catch them).
    """
    from django.db.models import Count
    
    # Find job listings with potential duplicate resumes
    duplicates = Applicant.objects.values('job_listing', 'resume_file_hash') \
        .annotate(count=Count('id')) \
        .filter(count__gt=1)
    
    if duplicates:
        logger.warning(f"Found {len(duplicates)} potential duplicate resume groups")
        # Log for manual review - actual deduplication should be handled manually
        for dup in duplicates:
            logger.warning(
                f"Job {dup['job_listing']}, Hash {dup['resume_file_hash'][:16]}... "
                f"has {dup['count']} submissions"
            )
