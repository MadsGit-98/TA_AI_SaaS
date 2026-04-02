"""
Celery tasks for the applications app.

Handles:
- Application confirmation emails
- Expired application cleanup
- Duplicate resume detection
- Bulk upload resume processing
"""

import os
import re
import uuid
from celery import shared_task, group, chord
from celery.utils.log import get_task_logger
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, F, Case, When, Value, IntegerField
from django.db import transaction
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from apps.applications.models import Applicant, UploadBatch
from apps.jobs.models import JobListing
from services.resume_parsing_service import ResumeParserService, ConfidentialInfoFilter
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = get_task_logger(__name__)

# Bulk upload constants
BATCH_SIZE = 100  # Number of resumes in a full batch


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
        
        # Check if batch has been cancelled - skip processing if so
        if batch.status == 'cancelled':
            logger.info(f"Batch {batch_id} is cancelled, skipping processing of {file_metadata.get('filename', 'unknown')}")
            return {'success': False, 'error': 'Batch cancelled', 'skipped': True}
    except (JobListing.DoesNotExist, UploadBatch.DoesNotExist) as e:
        logger.error(f"Job listing or batch not found: job_listing_id={job_listing_id}, batch_id={batch_id}, error={e}")
        return {'success': False, 'error': 'Job listing or batch not found'}

    try:
        # Sanitize filename to prevent path traversal attacks
        original_filename = file_metadata.get('filename', 'unnamed_file')
        
        # Extract only the basename to strip any directory components
        safe_filename = os.path.basename(original_filename)
        
        # Remove null bytes and normalize path separators
        safe_filename = safe_filename.replace('\x00', '').replace('\\', '/')
        
        # Split and take only the last component (defense in depth)
        safe_filename = safe_filename.split('/')[-1]
        
        # Remove any remaining path traversal sequences
        while '..' in safe_filename:
            safe_filename = safe_filename.replace('..', '')
        
        # Allow only alphanumeric, dots, hyphens, and underscores
        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', safe_filename)
        
        # Enforce max filename length (leave room for hash prefix)
        max_name_length = 100
        if len(safe_filename) > max_name_length:
            name_parts = safe_filename.rsplit('.', 1)
            if len(name_parts) == 2:
                safe_filename = name_parts[0][:max_name_length-5] + '.' + name_parts[1]
            else:
                safe_filename = safe_filename[:max_name_length]
        
        # Fallback if filename is empty after sanitization
        if not safe_filename:
            safe_filename = 'unnamed_file'
            logger.warning(f"Sanitized filename was empty for batch {batch_id}, using fallback name")
        
        # Log if filename was changed during sanitization
        if safe_filename != original_filename:
            logger.debug(f"Filename sanitized: '{original_filename}' -> '{safe_filename}'")

        # Move file to permanent storage (outside transaction - file operations)
        # Use file_hash in path for idempotency - same hash = same path
        permanent_path = f'applications/resumes/{job_listing.id}/{file_metadata["file_hash"]}_{safe_filename}'

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
        # Use sanitized filename for extension check
        filename_lower = safe_filename.lower()
        try:
            if filename_lower.endswith('.pdf'):
                text = ResumeParserService.extract_text_from_pdf(file_content)
            elif filename_lower.endswith('.docx'):
                text = ResumeParserService.extract_text_from_docx(file_content)
            else:
                # Fallback: try DOCX first, then PDF
                try:
                    text = ResumeParserService.extract_text_from_docx(file_content)
                except Exception:
                    text = ResumeParserService.extract_text_from_pdf(file_content)
        except Exception as extraction_error:
            logger.warning(f"Text extraction failed for {safe_filename}: {extraction_error}")
            text = ""

        # Extract contact information using service method (BEFORE redaction)
        contact_info = ResumeParserService.extract_contact_info(text)
        first_name = contact_info['first_name']
        last_name = contact_info['last_name']
        email = contact_info['email']
        phone = contact_info['phone']

        # Fallback: Use filename if extraction failed
        if not first_name and not last_name:
            first_name, last_name = ResumeParserService.extract_name_from_filename(safe_filename)

        if not email:
            email = ResumeParserService.generate_placeholder_email(safe_filename)

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

        # Send WebSocket notification after DB transaction commits
        # Use 'file_success' event type for the new async processing flow
        websocket_data = {
            'type': 'file_success',
            'file_id': file_metadata['file_id'],
            'filename': file_metadata['filename'],
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
        # Use 'file_error' event type for the new async processing flow
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'bulk_upload_{batch_id}',
            {
                'type': 'file_error',
                'file_id': file_metadata['file_id'],
                'filename': file_metadata.get('filename', 'unknown'),
                'error_code': 'processing_failed',
                'message': client_message
            }
        )

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def process_bulk_upload_batch(self, batch_id: str):
    """
    Orchestrate async bulk upload processing.

    This task:
    1. Sets batch status to 'processing' (already set by API)
    2. Dispatches process_resume_async for each file
    3. Tracks overall progress
    4. Updates JobListing counters when complete
    5. Sends completion WebSocket notification

    Args:
        batch_id: UUID of the upload batch
    """
    logger.info(f"process_bulk_upload_batch started for batch {batch_id}")

    try:
        batch = UploadBatch.objects.select_related('job_listing').get(id=batch_id)
        
        # Idempotency check: skip if batch is already committed or cancelled
        if batch.status in ['committed', 'cancelled']:
            logger.info(f"Batch {batch_id} already in terminal status {batch.status}, skipping processing")
            return
        
        # Recheck status: only process if batch is in 'processing' status
        if batch.status != 'processing':
            logger.warning(f"Batch {batch_id} is not in 'processing' status (current: {batch.status}), skipping")
            return
        
        job_listing = batch.job_listing
        
        logger.info(f"Batch {batch_id}: Retrieved batch with {len(batch.temp_files)} temp files")
        
        # Get files to process (skip files marked with action='skip')
        files_to_process = [
            f for f in batch.temp_files 
            if f.get('action') != 'skip' and f.get('status') != 'failed'
        ]
        
        total_files = len(files_to_process)
        
        logger.info(f"Batch {batch_id}: Found {total_files} files to process out of {len(batch.temp_files)} total files")
        logger.info(f"Batch {batch_id}: File statuses: {[f.get('status') for f in batch.temp_files[:5]]}...")  # Log first 5
        
        if total_files == 0:
            # No files to process - mark as complete immediately
            batch.status = 'committed'
            batch.processing_completed_at = timezone.now()
            batch.commit_summary = {
                'applicants_created': 0,
                'files_failed': 0,
                'total': 0
            }
            batch.save()
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'bulk_upload_{batch_id}',
                {
                    'type': 'processing_complete',
                    'batch_id': batch_id,
                    'summary': {
                        'applicants_created': 0,
                        'files_failed': 0,
                        'total': 0
                    }
                }
            )
            return
        
        # Initialize processing progress
        batch.processing_progress = {
            'total': total_files,
            'processed': 0,
            'failed': 0,
            'current_file': None,
            'status': 'processing'
        }
        batch.processing_started_at = timezone.now()
        batch.save()
        
        # Send processing started notification
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'bulk_upload_{batch_id}',
            {
                'type': 'processing_started',
                'batch_id': batch_id,
                'total_files': total_files
            }
        )
        
        # Process each file asynchronously
        # We use a chord to wait for all tasks to complete before finalizing
        # The process_resume_async task is idempotent and handles its own retries
        if files_to_process:
            # Create a group of tasks to process all files in parallel
            file_tasks = group(
                process_resume_async.s(file_meta, str(job_listing.id), batch_id)
                for file_meta in files_to_process
            )
            
            # Use chord to call finalize_bulk_upload_batch after all tasks complete
            # The chord waits for all group tasks to finish before calling the callback
            chord(file_tasks)(finalize_bulk_upload_batch.s(batch_id))
            
            logger.info(f"Started processing {total_files} files for batch {batch_id} with chord callback")
        else:
            # No files to process - finalize immediately
            logger.info(f"No files to process for batch {batch_id}, finalizing immediately")
            finalize_bulk_upload_batch.delay([], batch_id)
        
    except UploadBatch.DoesNotExist:
        logger.error(f"Batch {batch_id} not found")
        return
    except Exception as exc:
        logger.error(f"Failed to start batch processing for {batch_id}: {exc}", exc_info=True)
        
        # Update batch status to failed
        try:
            batch = UploadBatch.objects.get(id=batch_id)
            batch.status = 'failed'
            batch.processing_completed_at = timezone.now()
            batch.save()
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'bulk_upload_{batch_id}',
                {
                    'type': 'processing_failed',
                    'batch_id': batch_id,
                    'error': 'Failed to start batch processing'
                }
            )
        except Exception:
            pass
        
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def finalize_bulk_upload_batch(results, batch_id: str):
    """
    Finalize a bulk upload batch after all files have been processed.

    This task is called by a Celery chord after all process_resume_async tasks complete.
    The chord passes task results as the first argument, which we ignore since we
    query the database directly for accurate counts.

    This task:
    1. Checks if all files have been processed
    2. Updates JobListing counters using atomic F() expressions
    3. Sets batch status to 'committed'
    4. Sends completion WebSocket notification

    Args:
        results: List of results from process_resume_async tasks (ignored)
        batch_id: UUID of the upload batch (passed by chord callback)
    """
    try:
        batch = UploadBatch.objects.select_related('job_listing').get(id=batch_id)

        # Check if batch is still processing
        if batch.status != 'processing':
            logger.info(f"Batch {batch_id} is not in processing status ({batch.status})")
            return

        # Count actual applicants created for this batch
        # This is more reliable than tracking progress in JSON field
        files_committed = Applicant.objects.filter(upload_batch=batch).count()

        # Count failed files directly from batch.temp_files
        # This is the authoritative source since process_resume_async marks files as 'failed' on error
        failed_count = sum(1 for f in batch.temp_files if f.get('status') == 'failed')
        
        # Count skipped files (user decided to skip during duplicate review)
        skipped_count = sum(1 for f in batch.temp_files if f.get('action') == 'skip')
        
        # Total files that were supposed to be processed (excluding skipped)
        total = len(batch.temp_files) - skipped_count

        # All files processed - finalize
        job_listing = batch.job_listing

        # Update JobListing counters using a single atomic update with conditional batch_count increment
        # This ensures updates are not lost in concurrent scenarios
        if files_committed > 0:
            # Single atomic update with conditional batch_count increment using Case/When
            # Only increment batch_count if files_committed equals BATCH_SIZE (100)
            batch_count_increment = Case(
                When(pk=job_listing.pk, then=F('batch_count') + 1),
                default=F('batch_count'),
                output_field=IntegerField()
            ) if files_committed == BATCH_SIZE else F('batch_count')

            JobListing.objects.filter(pk=job_listing.pk).update(
                total_resumes=F('total_resumes') + files_committed,
                batch_count=batch_count_increment
            )

            # Refresh job_listing to get updated values
            job_listing.refresh_from_db()
            logger.info(f"Updated JobListing {job_listing.id}: total_resumes={job_listing.total_resumes}, batch_count={job_listing.batch_count}")

        # Update batch status
        batch.status = 'committed'
        batch.processing_completed_at = timezone.now()
        batch.commit_summary = {
            'applicants_created': files_committed,
            'files_failed': failed_count,
            'total': total
        }
        batch.save()

        # Send completion notification
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'bulk_upload_{batch_id}',
            {
                'type': 'processing_complete',
                'batch_id': batch_id,
                'summary': {
                    'applicants_created': files_committed,
                    'files_failed': failed_count,
                    'total': total
                }
            }
        )

        logger.info(f"Finalized batch {batch_id}: {files_committed} created, {failed_count} failed")

    except UploadBatch.DoesNotExist:
        logger.error(f"Batch {batch_id} not found")
    except Exception as exc:
        logger.error(f"Failed to finalize batch {batch_id}: {exc}", exc_info=True)