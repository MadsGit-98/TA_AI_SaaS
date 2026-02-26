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
        Determine whether a resume with the specified file hash exists for the given job listing.
        
        Parameters:
            job_listing: JobListing instance used to scope the search for existing applicants.
            file_hash (str): SHA-256 hash of the resume file to check.
        
        Returns:
            `true` if a matching applicant exists for the job listing, `false` otherwise.
        """
        return Applicant.objects.filter(
            job_listing=job_listing,
            resume_file_hash=file_hash
        ).exists()

    @staticmethod
    def check_email_duplicate(job_listing, email: str) -> bool:
        """
        Determine whether an applicant with the given email already exists for the specified job listing.
        
        Parameters:
            job_listing: JobListing instance used to scope the duplicate check.
            email (str): Email address to check (comparison is case-insensitive).
        
        Returns:
            True if an applicant with the same email exists for the job listing, False otherwise.
        """
        return Applicant.objects.filter(
            job_listing=job_listing,
            email__iexact=email  # Case-insensitive comparison
        ).exists()

    @staticmethod
    def check_phone_duplicate(job_listing, phone: str) -> bool:
        """
        Determine whether a phone number is already associated with any applicant for the given job listing.
        
        Parameters:
            job_listing: The job listing to scope the search.
            phone (str): Phone number in E.164 format to check.
        
        Returns:
            `true` if an applicant with the specified phone exists for the job listing, `false` otherwise.
        """
        return Applicant.objects.filter(
            job_listing=job_listing,
            phone=phone
        ).exists()

    @staticmethod
    def validate_resume_file(file_content: bytes, filename: str) -> dict:
        """
        Validate a resume file and produce a structured result describing format, size, hash, and any validation errors.
        
        Parameters:
            file_content (bytes): Raw file bytes uploaded for the resume.
            filename (str): Original filename provided by the uploader.
        
        Returns:
            dict: Validation result with the following keys:
                - valid (bool): True if all checks passed, False otherwise.
                - checks (dict): Per-check booleans:
                    - format_valid (bool): True if file extension and magic bytes match an accepted format.
                    - size_valid (bool): True if file size is within allowed bounds.
                - errors (list): List of error objects with keys `field`, `code`, and `message` for each failed check.
                - file_hash (str or None): Calculated hash of the file content, or None if not computed.
                - file_extension (str or None): Lowercased file extension (without dot) derived from filename, or None.
        
        Notes:
            Duplicate detection by file content hash is performed separately via check_resume_duplicate() using the returned `file_hash`.
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

        # Early guard: Validate file_content is not None and is bytes
        if file_content is None or not isinstance(file_content, (bytes, bytearray)):
            result['valid'] = False
            result['errors'].append({
                'field': 'resume',
                'code': 'invalid_file_content',
                'message': 'Invalid file content. Please upload a valid file.'
            })
            return result

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
