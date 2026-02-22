"""
File validation utilities for resume uploads.
"""

from pathlib import Path
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile


# File size constants (in bytes)
MIN_FILE_SIZE = 50 * 1024  # 50KB
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Allowed MIME types
ALLOWED_MIME_TYPES = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]

# Allowed extensions
ALLOWED_EXTENSIONS = ['pdf', 'docx']

# Magic bytes signatures
PDF_MAGIC_BYTES = b'%PDF'
DOCX_MAGIC_BYTES = b'PK\x03\x04'  # ZIP signature (Docx is a ZIP file)


def validate_resume_file(file: UploadedFile) -> UploadedFile:
    """
    Validate resume file format and size.
    
    Args:
        file: Uploaded file object
        
    Returns:
        The same file object if valid
        
    Raises:
        ValidationError: If file is invalid
    """
    # Check file size
    file_size = file.size
    if file_size < MIN_FILE_SIZE:
        raise ValidationError(
            f"File size ({format_file_size(file_size)}) is below minimum (50KB). "
            "Please upload a larger file."
        )
    if file_size > MAX_FILE_SIZE:
        raise ValidationError(
            f"File size ({format_file_size(file_size)}) exceeds maximum (10MB). "
            "Please upload a smaller file."
        )
    
    # Check file extension using pathlib for robustness
    file_extension = Path(file.name).suffix.lower().lstrip('.')
    if not file_extension:
        raise ValidationError(
            "File has no extension. "
            "Only PDF and DOCX files are accepted."
        )
    if file_extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file format '.{file_extension}'. "
            "Only PDF and DOCX files are accepted."
        )
    
    # Validate magic bytes (file signature)
    # Read only the first 4 bytes for magic byte check to avoid loading entire file into memory
    magic_bytes = file.read(4)
    file.seek(0)  # Reset file pointer for downstream processing

    if not validate_magic_bytes(magic_bytes, file_extension):
        raise ValidationError(
            "File content does not match extension. "
            "Please ensure you're uploading a valid PDF or DOCX file."
        )

    return file


def validate_magic_bytes(file_content: bytes, extension: str) -> bool:
    """
    Validate file content using magic bytes.
    
    Args:
        file_content: Raw file bytes
        extension: File extension
        
    Returns:
        True if magic bytes match
    """
    if extension == 'pdf':
        return file_content.startswith(PDF_MAGIC_BYTES)
    elif extension == 'docx':
        return file_content.startswith(DOCX_MAGIC_BYTES)
    return False


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
