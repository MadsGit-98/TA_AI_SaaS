"""
Celery tasks for the applications app.

Handles:
- Application confirmation emails
- Expired application cleanup
- Duplicate resume detection
- Bulk upload resume processing
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from django.db import transaction
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from apps.applications.models import Applicant, UploadBatch
from apps.jobs.models import JobListing
from services.resume_parsing_service import ResumeParserService, ConfidentialInfoFilter
import uuid
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_application_confirmation_email(self, applicant_id: str):
    """
    Send confirmation email to applicant after successful submission.

    Args:
        applicant_id: UUID of the applicant
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


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_resume_async(self, file_metadata: dict, job_listing_id: str, batch_id: str):
    """
    Process a single resume file from bulk upload asynchronously.

    This task:
    1. Moves file from temp to permanent storage
    2. Extracts text based on file type (PDF or DOCX)
    3. Extracts contact information using ResumeParserService
    4. Redacts confidential information
    5. Creates Applicant instance with extracted data (idempotent - uses get_or_create)
    6. Uses filename as fallback if extraction fails
    7. Updates batch progress via WebSocket (after DB commit)

    Args:
        file_metadata: Dictionary containing file information including 'filename'
        job_listing_id: UUID of the job listing
        batch_id: UUID of the upload batch
    """
    try:
        job_listing = JobListing.objects.get(id=job_listing_id)
        batch = UploadBatch.objects.get(id=batch_id)

        # Move file to permanent storage (outside transaction - file operations)
        # Use file_hash in path for idempotency - same hash = same path
        permanent_path = f'applications/resumes/{job_listing.id}/{file_metadata["file_hash"]}_{file_metadata["filename"]}'

        # Check if file already exists (idempotent - handles retries)
        if not default_storage.exists(permanent_path):
            # Use context manager to ensure file handle is closed
            with default_storage.open(file_metadata['temp_path']) as f:
                file_content = f.read()
            
            # Save to permanent storage - only delete temp file if save succeeds
            default_storage.save(permanent_path, ContentFile(file_content))
            
            # Delete temp file only after successful save
            # This ensures retries can still access the temp file if save fails
            default_storage.delete(file_metadata['temp_path'])
        else:
            logger.debug(f"File already exists at {permanent_path} (retry scenario)")
            # Use context manager to ensure file handle is closed
            with default_storage.open(permanent_path) as f:
                file_content = f.read()

        # Determine file type from extension and extract text
        filename = file_metadata.get('filename', '').lower()
        try:
            if filename.endswith('.pdf'):
                text = ResumeParserService.extract_text_from_pdf(file_content)
            elif filename.endswith('.docx'):
                text = ResumeParserService.extract_text_from_docx(file_content)
            else:
                # Fallback: try DOCX first, then PDF
                try:
                    text = ResumeParserService.extract_text_from_docx(file_content)
                except Exception:
                    text = ResumeParserService.extract_text_from_pdf(file_content)
        except Exception as extraction_error:
            logger.warning(f"Text extraction failed for {file_metadata['filename']}: {extraction_error}")
            text = ""

        # Extract contact information using service method (BEFORE redaction)
        contact_info = ResumeParserService.extract_contact_info(text)
        first_name = contact_info['first_name']
        last_name = contact_info['last_name']
        email = contact_info['email']
        phone = contact_info['phone']

        # Fallback: Use filename if extraction failed
        if not first_name and not last_name:
            first_name, last_name = ResumeParserService.extract_name_from_filename(filename)

        if not email:
            email = ResumeParserService.generate_placeholder_email(filename)

        if not phone:
            phone = ''  # Leave empty if not found

        # Redact confidential information from text
        if text:
            redacted_text = ConfidentialInfoFilter.redact(text)
        else:
            redacted_text = "No text could be extracted from this resume file."

        # Idempotent Applicant creation - use get_or_create with unique file_hash
        # This prevents duplicates on retry
        applicant, created = Applicant.objects.get_or_create(
            job_listing=job_listing,
            resume_file_hash=file_metadata['file_hash'],
            defaults={
                'upload_batch': batch,
                'first_name': first_name[:200] if first_name else 'Unknown',
                'last_name': last_name[:200] if last_name else 'Applicant',
                'email': email[:255] if email else f"unknown_{uuid.uuid4().hex[:8]}@placeholder.local",
                'phone': phone[:50] if phone else '',
                'resume_file': permanent_path,
                'resume_parsed_text': redacted_text,
                'status': Applicant.STATUS_SUBMITTED
            }
        )

        if not created:
            logger.info(f"Applicant already exists for {file_metadata['filename']} (id={applicant.id})")

        # Prepare WebSocket data for sending after transaction commits
        websocket_data = {
            'type': 'upload_progress',
            'file_id': file_metadata['file_id'],
            'filename': file_metadata['filename'],
            'status': 'success',
            'applicant_id': str(applicant.id),
            'extracted_data': {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone
            }
        }

        # Send WebSocket notification after DB transaction commits
        # This ensures retries don't create duplicate Applicants
        def send_websocket_notification():
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'bulk_upload_{batch_id}',
                websocket_data
            )

        transaction.on_commit(send_websocket_notification)

        logger.info(f"Processed resume {file_metadata['filename']} for applicant {applicant.id}")
        return {
            'success': True,
            'applicant_id': str(applicant.id),
            'created': created,
            'extracted_data': {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone
            }
        }

    except Exception as exc:
        # Log full exception details internally for diagnostics
        logger.error(f"Failed to process resume {file_metadata['filename']}: {exc}", exc_info=True)

        # Generic client-facing error message (no internal details exposed)
        client_message = "An internal error occurred while processing the file"

        # Update file status in batch
        try:
            batch = UploadBatch.objects.get(id=batch_id)
            for file_meta in batch.temp_files:
                if file_meta['file_id'] == file_metadata['file_id']:
                    file_meta['status'] = 'failed'
                    file_meta['error'] = client_message
                    break
            batch.save()
        except Exception:
            pass

        # Send WebSocket error update with generic message
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'bulk_upload_{batch_id}',
            {
                'type': 'upload_error',
                'file_id': file_metadata['file_id'],
                'error': 'processing_failed',
                'message': client_message
            }
        )

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))