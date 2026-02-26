"""
API endpoints for Application Submission

Handles:
- Application submission (public, unauthenticated)
- File validation (async duplication check)
- Contact validation (async duplication check)
- Application status retrieval
"""

import logging
from django.db import IntegrityError, transaction
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from apps.applications.models import Applicant
from apps.applications.throttles import (
    ApplicationSubmissionIPThrottle,
    ApplicationValidationIPThrottle,
    ApplicationStatusRateThrottle,
)
from apps.applications.serializers import (
    ApplicantSerializer,
    ApplicantCreateResponseSerializer,
    FileValidationRequestSerializer,
    ContactValidationRequestSerializer,
    ApplicationStatusSerializer,
)
from services.duplication_service import DuplicationService
from apps.applications.tasks import send_application_confirmation_email
from services.resume_parsing_service import ResumeParserService

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ApplicationSubmissionIPThrottle])
def submit_application(request):
    """
    Create a new application for a job listing, performing pre-save duplication checks and returning application metadata on success.
    
    Performs field-level duplicate detection (email, phone, resume) using DuplicationService and, if no duplicates are detected, saves the Applicant inside an atomic transaction to guard against race conditions. Triggers a confirmation email after successful creation.
    
    Returns:
        dict: On success, response includes `id`, `status`, `submitted_at`, `access_token`, and a success `message`. On validation failure, response contains `error: 'validation_failed'` and `details` describing field errors. On duplicate detection, response contains `valid: False`, `checks: {'duplicate_detected': True}`, and an `errors` list with a `duplicate_detected` code.
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
    Validate an uploaded resume file and determine whether it duplicates an existing submission for the given job listing.
    
    Returns:
        A response payload describing validation and duplication results.
        - If the file is valid and not a duplicate: a dictionary with keys
          `valid` (True), `file_size` (int), `file_format` (str), and `checks`
          (dict with `format_valid`: True, `size_valid`: True, `duplicate`: False).
        - If the file fails validation: a dictionary with keys `valid` (False),
          `checks` (validation check results), and `errors` (list of validation error objects).
        - If the file is valid but detected as a duplicate: a dictionary with keys
          `valid` (False), `checks` (including `duplicate`: True), and `errors`
          (list containing a duplicate resume error object).
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([ApplicationStatusRateThrottle])
def get_application_status(request, application_id):
    """
    Retrieve non-PII status information for an application identified by application_id.
    
    Parameters:
        application_id: Identifier of the application to retrieve.
    
    Returns:
        HTTP Response containing the serialized application status (includes fields such as `status` and `submitted_at`) on success; a 404 Response with an error payload if no application with the given ID is found.
    """
    try:
        applicant = Applicant.objects.select_related('job_listing').get(id=application_id)
        serializer = ApplicationStatusSerializer(applicant)
        return Response(serializer.data)
    except Applicant.DoesNotExist:
        return Response(
            {'error': 'not_found', 'message': 'Application not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
