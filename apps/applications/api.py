"""
API endpoints for Application Submission

Handles:
- Application submission (public, unauthenticated)
- File validation (async duplication check)
- Contact validation (async duplication check)
- Application status retrieval
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from apps.applications.models import Applicant
from apps.applications.serializers import (
    ApplicantSerializer,
    ApplicantCreateResponseSerializer,
    DuplicateCheckResponseSerializer,
    FileValidationRequestSerializer,
    ContactValidationRequestSerializer,
)
from apps.applications.services.duplication_service import DuplicationService
from apps.applications.tasks import send_application_confirmation_email

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def submit_application(request):
    """
    Submit a new application (public endpoint).
    
    Returns:
        201: Application created successfully
        400: Validation error
        409: Duplicate detected
        429: Rate limit exceeded
    """
    serializer = ApplicantSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'validation_failed', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        applicant = serializer.save()
        
        # Send confirmation email asynchronously
        send_application_confirmation_email.delay(str(applicant.id))
        
        # Return success response
        response_data = ApplicantCreateResponseSerializer({
            'id': applicant.id,
            'status': applicant.status,
            'submitted_at': applicant.submitted_at,
            'message': f"Application submitted successfully. A confirmation email has been sent to {applicant.email}"
        }).data
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Failed to create application: {str(e)}")
        return Response(
            {'error': 'internal_error', 'message': 'Failed to submit application. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def validate_file(request):
    """
    Validate uploaded file and check for duplicates.
    
    This endpoint allows async file validation before final submission.
    
    Returns:
        200: File valid, no duplicates
        400: File validation error
        409: Duplicate detected
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
def validate_contact(request):
    """
    Validate contact information and check for duplicates.
    
    Returns:
        200: Contact valid, no duplicates
        409: Duplicate detected
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
        errors = []
        if email_duplicate:
            errors.append({
                'field': 'email',
                'code': 'duplicate_email',
                'message': 'An application with this email address has already been submitted for this job listing.'
            })
        if phone_duplicate:
            errors.append({
                'field': 'phone',
                'code': 'duplicate_phone',
                'message': 'An application with this phone number has already been submitted for this job listing.'
            })
        
        return Response(
            {
                'valid': False,
                'checks': {
                    'email_duplicate': email_duplicate,
                    'phone_duplicate': phone_duplicate
                },
                'errors': errors
            },
            status=status.HTTP_409_CONFLICT
        )
    
    # No duplicates found
    return Response(
        {
            'valid': True,
            'checks': {
                'email_duplicate': False,
                'phone_duplicate': False
            }
        },
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def get_application_status(request, application_id):
    """
    Get application status by ID.
    
    Used for post-submission confirmation page.
    """
    try:
        applicant = Applicant.objects.select_related('job_listing').get(id=application_id)
        serializer = ApplicantSerializer(applicant)
        return Response(serializer.data)
    except Applicant.DoesNotExist:
        return Response(
            {'error': 'not_found', 'message': 'Application not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
