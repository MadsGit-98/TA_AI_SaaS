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
    Send a confirmation email to an applicant for their job submission.
    
    Builds an email using the applicant and related job listing data, renders plain-text and HTML templates, and sends the message. If the applicant record does not exist the task logs an error and exits without retrying; on other failures the task triggers a Celery retry with exponential backoff.
    
    Parameters:
        applicant_id (str): UUID of the applicant whose confirmation email should be sent.
    """
    applicant = None
    email = "<unknown>"
    try:
        applicant = Applicant.objects.get(id=applicant_id)
        email = applicant.email

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

        logger.info(f"Confirmation email sent for application {applicant_id}")

    except Applicant.DoesNotExist:
        logger.error(f"Applicant {applicant_id} not found")
        # Don't retry if applicant doesn't exist
        return
    except Exception as exc:
        logger.error(f"Failed to send email to {email} (applicant_id={applicant_id}): {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def cleanup_expired_applications():
    """
    Remove applicant records and associated resume files older than 90 days.
    
    This task identifies applicants whose `submitted_at` is more than 90 days ago, deletes any associated resume files from storage, removes the database records, and logs the number of deleted records.
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
    Identify potential duplicate resume submissions by grouping applicants by job listing and resume file hash and log groups with more than one submission for manual review.
    
    Logs a warning with the number of duplicate groups found. For each group, logs the job listing id, a truncated resume file hash (or '<no_hash>' if missing), and the number of submissions.
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
            # Safely handle missing or None resume_file_hash
            resume_hash = dup.get('resume_file_hash') or '<no_hash>'
            logger.warning(
                f"Job {dup['job_listing']}, Hash {resume_hash[:16] if resume_hash != '<no_hash>' else resume_hash}... "
                f"has {dup['count']} submissions"
            )
