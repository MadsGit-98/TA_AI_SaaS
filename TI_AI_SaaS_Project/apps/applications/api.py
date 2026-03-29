"""
API endpoints for Application Submission

Handles:
- Application submission (public, unauthenticated)
- File validation (async duplication check)
- Contact validation (async duplication check)
- Bulk resume upload (authenticated TAS only)
"""

import logging
import os
import uuid
import re
from django.db import IntegrityError, transaction
from django.db.models import F
from django.core.files.base import ContentFile
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from apps.applications.models import Applicant, UploadBatch
from apps.jobs.models import JobListing
from apps.applications.throttles import (
    ApplicationSubmissionIPThrottle,
    ApplicationValidationIPThrottle,
)
from apps.applications.serializers import (
    ApplicantSerializer,
    ApplicantCreateResponseSerializer,
    FileValidationRequestSerializer,
    ContactValidationRequestSerializer,
    BulkUploadInitSerializer,
    BulkUploadFileSerializer,
    BulkUploadCommitSerializer,
    BulkUploadValidateSerializer,
    BulkUploadDecisionSerializer,
)
from apps.accounts.permissions import IsTAS
from services.duplication_service import DuplicationService
from apps.applications.tasks import send_application_confirmation_email
from services.resume_parsing_service import ResumeParserService, ConfidentialInfoFilter
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def extract_contact_info(text: str) -> dict:
    """
    Extract contact information from parsed resume text.
    
    Args:
        text: Parsed resume text
        
    Returns:
        Dictionary with 'email' and 'phone' keys
    """
    # Simple email extraction
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, text)
    email = emails[0] if emails else None

    # Simple phone extraction (very basic)
    # Note: - is escaped to avoid being interpreted as a character range
    phone_pattern = r'\+?[\d\s\-\(\)]{10,}'
    phones = re.findall(phone_pattern, text)
    phone = phones[0] if phones else None

    return {'email': email, 'phone': phone}


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ApplicationSubmissionIPThrottle])
def submit_application(request):
    """
    Submit a new application (public endpoint).

    Returns:
        201: Application created successfully
        400: Validation error
        409: Duplicate detected (email, phone, or resume already submitted)
        429: Rate limit exceeded
        500: Internal server error
    """
    serializer = ApplicantSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            {'error': 'validation_failed', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check for duplicates before saving
    job_listing = serializer.validated_data.get('job_listing_id')
    email = serializer.validated_data.get('email')
    phone = serializer.validated_data.get('phone')
    resume = serializer.validated_data.get('resume')

    # Check for duplicates (email, phone, or resume)
    # Use generic response to prevent information disclosure about which field is duplicated
    has_duplicate = False
    
    if job_listing and email:
        email_duplicate = DuplicationService.check_email_duplicate(job_listing, email)
        if email_duplicate:
            has_duplicate = True

    if job_listing and phone and not has_duplicate:
        phone_duplicate = DuplicationService.check_phone_duplicate(job_listing, phone)
        if phone_duplicate:
            has_duplicate = True

    if job_listing and resume and not has_duplicate:
        # Calculate file hash for duplicate check
        file_content = resume.read()
        resume.seek(0)
        file_hash = ResumeParserService.calculate_file_hash(file_content)
        resume_duplicate = DuplicationService.check_resume_duplicate(job_listing, file_hash)
        if resume_duplicate:
            has_duplicate = True

    if has_duplicate:
        # Return generic error message to prevent information disclosure
        # about which specific field (email/phone/resume) is duplicated
        return Response(
            {
                'valid': False,
                'checks': {
                    'duplicate_detected': True
                },
                'errors': [
                    {
                        'code': 'duplicate_detected',
                        'message': 'An application with similar contact information has already been submitted for this job listing. Please use different contact details or contact support.'
                    }
                ]
            },
            status=status.HTTP_409_CONFLICT
        )

    # Wrap save in atomic transaction to handle TOCTOU race conditions
    # DB-level unique constraints will catch concurrent duplicate submissions
    try:
        with transaction.atomic():
            applicant = serializer.save()
    except IntegrityError as e:
        # Handle database constraint violations from concurrent submissions
        # Return generic error to prevent information disclosure about which field
        # caused the conflict (email/phone/resume)
        logger.warning(f"IntegrityError during application submission: {str(e)}")
        return Response(
            {
                'valid': False,
                'checks': {
                    'duplicate_detected': True
                },
                'errors': [
                    {
                        'code': 'duplicate_detected',
                        'message': 'An application with similar contact information has already been submitted for this job listing. Please use different contact details or contact support.'
                    }
                ]
            },
            status=status.HTTP_409_CONFLICT
        )

    # Send confirmation email asynchronously
    send_application_confirmation_email.delay(str(applicant.id))

    # Return success response with access token for secure redirect
    response_data = ApplicantCreateResponseSerializer({
        'id': applicant.id,
        'status': applicant.status,
        'submitted_at': applicant.submitted_at,
        'access_token': str(applicant.access_token),
        'message': f"Application submitted successfully. A confirmation email has been sent to {applicant.email}"
    }).data

    return Response(response_data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ApplicationValidationIPThrottle])
def validate_file(request):
    """
    Validate uploaded file and check for duplicates.

    This endpoint allows async file validation before final submission.

    Returns:
        200: File valid, no duplicates
        400: File validation error
        409: Duplicate detected
        429: Rate limit exceeded
    """
    serializer = FileValidationRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'validation_failed', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    job_listing = serializer.validated_data['job_listing_id']
    resume_file = serializer.validated_data['resume']
    
    # Read file content
    file_content = resume_file.read()
    resume_file.seek(0)
    
    # Validate file
    validation_result = DuplicationService.validate_resume_file(file_content, resume_file.name)
    
    if not validation_result['valid']:
        return Response(
            {
                'valid': False,
                'checks': validation_result['checks'],
                'errors': validation_result['errors']
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check for duplicate resume
    file_hash = validation_result['file_hash']
    is_duplicate = DuplicationService.check_resume_duplicate(job_listing, file_hash)
    
    if is_duplicate:
        return Response(
            {
                'valid': False,
                'checks': {
                    'format_valid': True,
                    'size_valid': True,
                    'duplicate': True
                },
                'errors': [
                    {
                        'field': 'resume',
                        'code': 'duplicate_resume',
                        'message': 'This resume has already been submitted for this job listing.'
                    }
                ]
            },
            status=status.HTTP_409_CONFLICT
        )
    
    # File is valid and not a duplicate
    return Response(
        {
            'valid': True,
            'file_size': len(file_content),
            'file_format': validation_result['file_extension'],
            'checks': {
                'format_valid': True,
                'size_valid': True,
                'duplicate': False
            }
        },
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ApplicationValidationIPThrottle])
def validate_contact(request):
    """
    Validate contact information and check for duplicates.

    Returns generic responses to prevent information disclosure about
    which specific field (email/phone) may already exist.

    Returns:
        200: Contact valid, no duplicates
        400: Validation error
        409: Duplicate detected (generic message)
        429: Rate limit exceeded
    """
    serializer = ContactValidationRequestSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            {'error': 'validation_failed', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    job_listing = serializer.validated_data['job_listing_id']
    email = serializer.validated_data['email']
    phone = serializer.validated_data['phone']

    # Check for duplicates
    email_duplicate = DuplicationService.check_email_duplicate(job_listing, email)
    phone_duplicate = DuplicationService.check_phone_duplicate(job_listing, phone)

    if email_duplicate or phone_duplicate:
        # Return generic error message to prevent information disclosure
        # about which specific field is duplicated
        return Response(
            {
                'valid': False,
                'checks': {
                    'duplicate_detected': True
                },
                'errors': [
                    {
                        'code': 'duplicate_detected',
                        'message': 'An application with similar contact information has already been submitted for this job listing. Please use different contact details or contact support.'
                    }
                ]
            },
            status=status.HTTP_409_CONFLICT
        )

    # No duplicates found
    return Response(
        {
            'valid': True,
            'checks': {
                'duplicate_detected': False
            }
        },
        status=status.HTTP_200_OK
    )


# Bulk Upload API Views

class BulkUploadInitView(APIView):
    """
    Initialize a bulk upload session.
    
    POST /api/applications/bulk-upload/init/
    """
    permission_classes = [IsAuthenticated, IsTAS]
    
    def post(self, request):
        serializer = BulkUploadInitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        job_listing = serializer.validated_data['job_listing_id']

        # Check if bulk upload is allowed
        can_upload, message = job_listing.can_upload_more(0)
        if not can_upload:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

        # Atomically increment batch_count to prevent race conditions
        # This ensures unique batch_number even with concurrent init requests
        try:
            with transaction.atomic():
                # Lock the row and increment atomically using F()
                JobListing.objects.filter(pk=job_listing.pk).update(
                    batch_count=F('batch_count') + 1
                )
                # Refresh to get the new value
                job_listing.refresh_from_db()
                
                # Create UploadBatch with the new batch_number
                batch = UploadBatch.objects.create(
                    job_listing=job_listing,
                    batch_number=job_listing.batch_count,
                    uploaded_by=request.user,
                    status='pending'
                )

        except IntegrityError as e:
            # Handle rare race condition where unique constraint is violated
            logger.warning(f"IntegrityError during batch creation (possible race condition): {str(e)}")
            return Response(
                {'error': 'Failed to create batch. Please try again.'},
                status=status.HTTP_409_CONFLICT
            )

        return Response({
            'batch_id': str(batch.id),
            'batch_number': batch.batch_number,
            'max_files': 100,
            'remaining_capacity': 100,
            'status': batch.status
        }, status=status.HTTP_201_CREATED)


class BulkUploadView(APIView):
    """
    Upload a single file to a batch.

    POST /api/applications/bulk-upload/upload/
    """
    permission_classes = [IsAuthenticated, IsTAS]

    def post(self, request):
        serializer = BulkUploadFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        batch = serializer.validated_data['batch_id']
        
        # Check batch state - reject uploads to inactive batches
        if batch.status in ['cancelled', 'committed']:
            return Response(
                {'error': f'Cannot upload to batch with status "{batch.status}". Batch is no longer accepting files.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES.get('file')

        if not file:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Read file content
        file_content = file.read()
        
        # Validate file using existing service
        validation_result = DuplicationService.validate_resume_file(
            file_content,
            file.name
        )
        
        if not validation_result['valid']:
            return Response({
                'error': validation_result['errors'][0]['code'],
                'message': validation_result['errors'][0]['message']
            }, status=status.HTTP_400_BAD_REQUEST)

        # Sanitize filename to prevent path traversal attacks
        # Extract only the basename, remove path separators and null bytes
        original_filename = file.name
        # Get basename to strip any directory components
        safe_name = os.path.basename(original_filename)
        # Remove null bytes and any remaining path separators
        safe_name = safe_name.replace('\x00', '').replace('\\', '/').split('/')[-1]
        # Enforce max filename length (leave room for UUID prefix)
        max_name_length = 100
        if len(safe_name) > max_name_length:
            name_parts = safe_name.rsplit('.', 1)
            if len(name_parts) == 2:
                safe_name = name_parts[0][:max_name_length-5] + '.' + name_parts[1]
            else:
                safe_name = safe_name[:max_name_length]
        # Fallback if filename is empty after sanitization
        if not safe_name:
            safe_name = 'unnamed_file'

        # Store in temp location with sanitized filename
        temp_path = f'{settings.AWS_TEMP_LOCATION}/{batch.id}/{uuid.uuid4()}_{safe_name}'
        default_storage.save(temp_path, ContentFile(file_content))

        # Add to batch (store original filename for display, safe path for storage)
        file_metadata = {
            'file_id': str(uuid.uuid4()),
            'filename': original_filename,
            'file_hash': validation_result['file_hash'],
            'size': len(file_content),
            'temp_path': temp_path,
            'status': 'uploaded'
        }
        batch.add_file(file_metadata)
        
        # Update batch status
        batch.status = 'uploading'
        batch.save()
        
        # Send WebSocket progress update
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'bulk_upload_{batch.id}',
            {
                'type': 'upload_progress',
                'file_id': file_metadata['file_id'],
                'filename': file.name,
                'status': 'success',
                'progress_percent': 100
            }
        )
        
        return Response(file_metadata)


class BulkUploadValidateView(APIView):
    """
    Validate batch and check for duplicates.
    
    POST /api/applications/bulk-upload/validate/
    """
    permission_classes = [IsAuthenticated, IsTAS]
    
    def post(self, request):
        serializer = BulkUploadValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        batch = serializer.validated_data['batch_id']
        
        duplicates = []
        valid_files = []
        
        for file_meta in batch.temp_files:
            # Check file hash duplicate
            if DuplicationService.check_resume_duplicate(
                batch.job_listing,
                file_meta['file_hash']
            ):
                duplicates.append({
                    'file_id': file_meta['file_id'],
                    'filename': file_meta['filename'],
                    'duplicate_type': 'file_hash'
                })
                continue
            
            # Extract contact info for further checks
            try:
                # Read file content using context manager to ensure proper cleanup
                with default_storage.open(file_meta['temp_path']) as f:
                    file_content = f.read()
                
                # Determine file type from extension and extract text
                filename = file_meta.get('filename', '').lower()
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
                contact_info = extract_contact_info(text)
                
                # Check email duplicate
                if contact_info.get('email') and DuplicationService.check_email_duplicate(
                    batch.job_listing,
                    contact_info['email']
                ):
                    duplicates.append({
                        'file_id': file_meta['file_id'],
                        'filename': file_meta['filename'],
                        'duplicate_type': 'email',
                        'email': contact_info['email']
                    })
                    continue
                
                # Check phone duplicate
                if contact_info.get('phone') and DuplicationService.check_phone_duplicate(
                    batch.job_listing,
                    contact_info['phone']
                ):
                    duplicates.append({
                        'file_id': file_meta['file_id'],
                        'filename': file_meta['filename'],
                        'duplicate_type': 'phone',
                        'phone': contact_info['phone']
                    })
                    continue
                
                valid_files.append(file_meta)
            except Exception as e:
                logger.error(f"Error processing file {file_meta['filename']}: {str(e)}")
                file_meta['status'] = 'failed'
                file_meta['error'] = 'Failed to process file'
        
        batch.duplicate_summary = {
            'duplicates': duplicates,
            'valid_files': valid_files
        }
        batch.status = 'awaiting_review'
        batch.save()
        
        # Send WebSocket update
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'bulk_upload_{batch.id}',
            {
                'type': 'validation_complete',
                'total_files': len(batch.temp_files),
                'valid_files': len(valid_files),
                'duplicates': len(duplicates),
                'failed_files': len([f for f in batch.temp_files if f.get('status') == 'failed']),
                'ready_for_review': True
            }
        )
        
        return Response({
            'batch_id': str(batch.id),
            'total_files': len(batch.temp_files),
            'valid_files': len(valid_files),
            'duplicates': duplicates,
            'status': batch.status
        })


class BulkUploadCommitView(APIView):
    """
    Commit a batch and create Applicant instances.

    POST /api/applications/bulk-upload/commit/
    """
    permission_classes = [IsAuthenticated, IsTAS]

    def post(self, request):
        serializer = BulkUploadCommitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        batch = serializer.validated_data['batch_id']

        applicants_created = []
        errors = []

        with transaction.atomic():
            for file_meta in batch.temp_files:
                # Skip files marked for skipping
                if file_meta.get('action') == 'skip':
                    continue

                # Skip failed files
                if file_meta.get('status') == 'failed':
                    continue

                try:
                    # Move file to permanent storage
                    # Sanitize filename again for defense-in-depth
                    safe_filename = os.path.basename(file_meta.get('filename', 'unnamed_file'))
                    safe_filename = safe_filename.replace('\x00', '').replace('\\', '/').split('/')[-1]
                    if not safe_filename:
                        safe_filename = 'unnamed_file'
                    permanent_path = f'applications/resumes/{batch.job_listing.id}/{uuid.uuid4()}_{safe_filename}'

                    # Read file content using context manager to ensure proper cleanup
                    with default_storage.open(file_meta['temp_path']) as f:
                        file_content = f.read()

                    default_storage.save(permanent_path, ContentFile(file_content))
                    default_storage.delete(file_meta['temp_path'])

                    # Determine file type from extension and extract text
                    filename = file_meta.get('filename', '').lower()
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

                    # Extract and redact text
                    redacted_text = ConfidentialInfoFilter.redact(text)

                    # Extract contact info BEFORE redaction
                    contact_info = extract_contact_info(text)

                    # Create Applicant with extracted contact info
                    applicant = Applicant.objects.create(
                        job_listing=batch.job_listing,
                        upload_batch=batch,
                        first_name='',  # Would be extracted from resume
                        last_name='',
                        email=contact_info.get('email') or '',
                        phone=contact_info.get('phone') or '',
                        resume_file=permanent_path,
                        resume_file_hash=file_meta['file_hash'],
                        resume_parsed_text=redacted_text,
                        status=Applicant.STATUS_SUBMITTED
                    )

                    applicants_created.append({
                        'id': str(applicant.id),
                        'reference_number': applicant.reference_number,
                        'filename': file_meta['filename']
                    })

                except Exception as e:
                    # Collect error for reporting - don't silently continue
                    error_info = {
                        'filename': file_meta['filename'],
                        'file_id': file_meta.get('file_id', 'unknown'),
                        'error': str(e)
                    }
                    errors.append(error_info)
                    logger.error(f"Error creating applicant for {file_meta['filename']}: {str(e)}")
                    # Mark file as failed in batch
                    file_meta['status'] = 'failed'
                    file_meta['error'] = str(e)

            # Update JobListing counters
            # Note: batch_count was already atomically incremented when batch was created
            batch.job_listing.total_resumes += len(applicants_created)
            batch.job_listing.save()

            batch.status = 'committed'
            batch.save()

        # Build response with error information if any failures occurred
        response_data = {
            'batch_id': str(batch.id),
            'status': 'committed',
            'applicants_created': len(applicants_created),
            'applicants': applicants_created
        }

        if errors:
            response_data['errors'] = errors
            response_data['files_failed'] = len(errors)
            logger.warning(f"Batch {batch.id} committed with {len(errors)} file failures")

        return Response(response_data)


class BulkUploadCancelView(APIView):
    """
    Cancel a batch and clean up temporary files.

    DELETE /api/applications/bulk-upload/cancel/<batch_id>/
    """
    permission_classes = [IsAuthenticated, IsTAS]

    def delete(self, request, batch_id):
        try:
            batch = UploadBatch.objects.get(
                id=batch_id,
                uploaded_by=request.user
            )

            # Check batch state - reject cancellation of terminal state batches
            if batch.status == 'committed':
                return Response(
                    {'error': 'Cannot cancel a batch that has already been committed. Applicants have been created.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if batch.status == 'cancelled':
                return Response(
                    {'error': 'Batch is already cancelled.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Delete temp files
            files_deleted = 0
            for file_meta in batch.temp_files:
                try:
                    default_storage.delete(file_meta['temp_path'])
                    files_deleted += 1
                except Exception as e:
                    logger.error(f"Error deleting temp file {file_meta['temp_path']}: {str(e)}")

            batch.status = 'cancelled'
            batch.save()

            return Response({
                'batch_id': str(batch.id),
                'status': 'cancelled',
                'files_deleted': files_deleted,
                'message': 'Batch cancelled successfully'
            })

        except UploadBatch.DoesNotExist:
            return Response(
                {'error': 'Batch not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class BulkUploadStatusView(APIView):
    """
    Get batch upload status.
    
    GET /api/applications/bulk-upload/status/<batch_id>/
    """
    permission_classes = [IsAuthenticated, IsTAS]
    
    def get(self, request, batch_id):
        try:
            batch = UploadBatch.objects.get(id=batch_id)
            
            # Check permission
            if batch.uploaded_by != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            return Response({
                'batch_id': str(batch.id),
                'status': batch.status,
                'progress': {
                    'files_uploaded': batch.file_count,
                    'files_total': 100,
                    'files_validated': len(batch.duplicate_summary.get('valid_files', [])) if batch.duplicate_summary else 0,
                    'files_with_errors': len([f for f in batch.temp_files if f.get('status') == 'failed'])
                },
                'files': batch.temp_files[:20]  # Limit to first 20 for performance
            })
            
        except UploadBatch.DoesNotExist:
            return Response(
                {'error': 'Batch not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class BulkUploadSummaryView(APIView):
    """
    Get batch upload summary.
    
    GET /api/applications/bulk-upload/summary/<batch_id>/
    """
    permission_classes = [IsAuthenticated, IsTAS]
    
    def get(self, request, batch_id):
        try:
            batch = UploadBatch.objects.get(id=batch_id)
            
            # Check permission
            if batch.uploaded_by != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if batch.status != 'committed':
                return Response(
                    {'error': 'Batch not yet committed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            applicants = batch.applicants.all()[:100]  # Limit to first 100
            
            return Response({
                'batch_id': str(batch.id),
                'job_listing': {
                    'id': str(batch.job_listing.id),
                    'title': batch.job_listing.title
                },
                'batch_number': batch.batch_number,
                'uploaded_at': batch.uploaded_at,
                'uploaded_by': {
                    'id': str(batch.uploaded_by.id),
                    'name': batch.uploaded_by.get_full_name() or batch.uploaded_by.username
                },
                'summary': {
                    'total_files': batch.file_count,
                    'successful': applicants.count(),
                    'duplicates_skipped': len([f for f in batch.temp_files if f.get('action') == 'skip']),
                    'failed': len([f for f in batch.temp_files if f.get('status') == 'failed'])
                },
                'applicants': [
                    {
                        'id': str(a.id),
                        'reference_number': a.reference_number,
                        'filename': a.resume_file.name.split('/')[-1],
                        'parsing_status': a.get_parsing_status()
                    }
                    for a in applicants
                ]
            })
            
        except UploadBatch.DoesNotExist:
            return Response(
                {'error': 'Batch not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class BulkUploadDecisionView(APIView):
    """
    Submit decisions for duplicate files.
    
    POST /api/applications/bulk-upload/decisions/
    """
    permission_classes = [IsAuthenticated, IsTAS]
    
    def post(self, request):
        serializer = BulkUploadDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        batch = serializer.validated_data['batch_id']
        decisions = serializer.validated_data['decisions']
        
        # Process decisions
        skip_all = False
        include_all = False

        for decision in decisions:
            action = decision['action']

            if action == 'skip_all':
                skip_all = True
                break
            elif action == 'include_all':
                include_all = True
                break
            elif action in ['skip', 'include']:
                file_id = decision['file_id']
                for file_meta in batch.temp_files:
                    if file_meta['file_id'] == file_id:
                        file_meta['action'] = action
                        break

        # Apply skip_all or include_all
        if skip_all:
            for dup in batch.duplicate_summary.get('duplicates', []):
                for file_meta in batch.temp_files:
                    if file_meta['file_id'] == dup['file_id']:
                        file_meta['action'] = 'skip'
        elif include_all:
            for dup in batch.duplicate_summary.get('duplicates', []):
                for file_meta in batch.temp_files:
                    if file_meta['file_id'] == dup['file_id']:
                        file_meta['action'] = 'include'
        
        batch.save()
        
        files_to_process = len([f for f in batch.temp_files if f.get('action') != 'skip'])
        files_skipped = len([f for f in batch.temp_files if f.get('action') == 'skip'])
        
        return Response({
            'batch_id': str(batch.id),
            'decisions_recorded': len(decisions),
            'files_to_process': files_to_process,
            'files_skipped': files_skipped,
            'status': 'ready_to_commit'
        })
