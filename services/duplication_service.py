"""
Duplication Service for Application Submissions

Per Constitution §4: Decoupled services located in project root services/ directory.

Handles:
- Resume file validation (format, size, magic bytes)
- Resume duplication detection (by file hash)
- Contact information duplication detection (email/phone)
"""

import logging
import os
from services.resume_parsing_service import ResumeParserService
from apps.applications.models import Applicant
from apps.applications.utils.file_validation import (
    validate_resume_file as validate_file_util,
    MIN_FILE_SIZE,
    MAX_FILE_SIZE,
)

logger = logging.getLogger(__name__)


class DuplicationService:
    """Service for detecting duplicate applications."""

    @staticmethod
    def check_resume_duplicate(job_listing, file_hash: str) -> bool:
        """
        Check if a resume with the given hash already exists for the job.

        Args:
            job_listing: JobListing instance
            file_hash: SHA-256 hash of resume file

        Returns:
            True if duplicate found, False otherwise
        """
        return Applicant.objects.filter(
            job_listing=job_listing,
            resume_file_hash=file_hash
        ).exists()

    @staticmethod
    def check_email_duplicate(job_listing, email: str) -> bool:
        """
        Check if an email address already exists for the job.

        Args:
            job_listing: JobListing instance
            email: Email address

        Returns:
            True if duplicate found, False otherwise
        """
        return Applicant.objects.filter(
            job_listing=job_listing,
            email__iexact=email  # Case-insensitive comparison
        ).exists()

    @staticmethod
    def check_phone_duplicate(job_listing, phone: str) -> bool:
        """
        Check if a phone number already exists for the job.

        Args:
            job_listing: JobListing instance
            phone: Phone number in E.164 format

        Returns:
            True if duplicate found, False otherwise
        """
        return Applicant.objects.filter(
            job_listing=job_listing,
            phone=phone
        ).exists()

    @staticmethod
    def validate_resume_file(file_content: bytes, filename: str) -> dict:
        """
        Validate resume file and return validation result.

        Args:
            file_content: Raw file bytes
            filename: Original filename

        Returns:
            Dictionary with validation results:
            {
                'valid': bool,
                'checks': {
                    'format_valid': bool,
                    'size_valid': bool
                },
                'errors': list,
                'file_hash': str,
                'file_extension': str
            }

        Note:
            Duplicate checking is performed separately via check_resume_duplicate()
            using the file_hash returned in this result.
        """
        result = {
            'valid': True,
            'checks': {
                'format_valid': True,
                'size_valid': True,
            },
            'errors': [],
            'file_hash': None,
            'file_extension': None
        }

        # Get file extension using robust method
        file_extension = os.path.splitext(filename)[1].lstrip('.').lower() if filename else ''
        result['file_extension'] = file_extension

        # Calculate file hash
        file_hash = ResumeParserService.calculate_file_hash(file_content)
        result['file_hash'] = file_hash

        # Check file size
        file_size = len(file_content)
        if file_size < MIN_FILE_SIZE:
            result['valid'] = False
            result['checks']['size_valid'] = False
            result['errors'].append({
                'field': 'resume',
                'code': 'file_too_small',
                'message': f'File size ({file_size / 1024:.1f}KB) is below minimum (50KB).'
            })

        if file_size > MAX_FILE_SIZE:
            result['valid'] = False
            result['checks']['size_valid'] = False
            result['errors'].append({
                'field': 'resume',
                'code': 'file_too_large',
                'message': f'File size ({file_size / (1024 * 1024):.1f}MB) exceeds maximum (10MB).'
            })

        # Check file format (extension)
        if file_extension not in ['pdf', 'docx']:
            result['valid'] = False
            result['checks']['format_valid'] = False
            result['errors'].append({
                'field': 'resume',
                'code': 'invalid_format',
                'message': f"Unsupported file format '.{file_extension}'. Only PDF and DOCX files are accepted."
            })

        # Check magic bytes if extension is valid
        if file_extension in ['pdf', 'docx']:
            from apps.applications.utils.file_validation import validate_magic_bytes
            if not validate_magic_bytes(file_content, file_extension):
                result['valid'] = False
                result['checks']['format_valid'] = False
                result['errors'].append({
                    'field': 'resume',
                    'code': 'invalid_file_content',
                    'message': 'File content does not match extension. Please upload a valid PDF or DOCX file.'
                })

        return result
