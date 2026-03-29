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
    5. Creates Applicant instance with extracted data
    6. Uses filename as fallback if extraction fails
    7. Updates batch progress via WebSocket

    Args:
        file_metadata: Dictionary containing file information including 'filename'
        job_listing_id: UUID of the job listing
        batch_id: UUID of the upload batch
    """
    try:
        job_listing = JobListing.objects.get(id=job_listing_id)
        batch = UploadBatch.objects.get(id=batch_id)

        # Move file to permanent storage
        permanent_path = f'applications/resumes/{job_listing.id}/{uuid.uuid4()}_{file_metadata["filename"]}'
        file_content = default_storage.open(file_metadata['temp_path']).read()
        default_storage.save(permanent_path, ContentFile(file_content))
        default_storage.delete(file_metadata['temp_path'])

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

        # Create Applicant with extracted data
        applicant = Applicant.objects.create(
            job_listing=job_listing,
            upload_batch=batch,
            first_name=first_name[:200] if first_name else 'Unknown',  # Respect max_length
            last_name=last_name[:200] if last_name else 'Applicant',  # Respect max_length
            email=email[:255] if email else f"unknown_{uuid.uuid4().hex[:8]}@placeholder.local",  # Respect max_length
            phone=phone[:50] if phone else '',  # Respect max_length
            resume_file=permanent_path,
            resume_file_hash=file_metadata['file_hash'],
            resume_parsed_text=redacted_text,
            status=Applicant.STATUS_SUBMITTED
        )

        # Send WebSocket progress update
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'bulk_upload_{batch_id}',
            {
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
        )

        logger.info(f"Processed resume {file_metadata['filename']} for applicant {applicant.id} "
                   f"(Name: {first_name} {last_name}, Email: {email})")
        return {
            'success': True,
            'applicant_id': str(applicant.id),
            'extracted_data': {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone
            }
        }

    except Exception as exc:
        logger.error(f"Failed to process resume {file_metadata['filename']}: {exc}")

        # Update file status in batch
        try:
            batch = UploadBatch.objects.get(id=batch_id)
            for file_meta in batch.temp_files:
                if file_meta['file_id'] == file_metadata['file_id']:
                    file_meta['status'] = 'failed'
                    file_meta['error'] = str(exc)
                    break
            batch.save()
        except Exception:
            pass

        # Send WebSocket error update
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'bulk_upload_{batch_id}',
            {
                'type': 'upload_error',
                'file_id': file_metadata['file_id'],
                'error': 'processing_failed',
                'message': str(exc)
            }
        )

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))