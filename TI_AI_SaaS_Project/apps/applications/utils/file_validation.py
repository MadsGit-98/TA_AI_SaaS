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
    Validate an uploaded resume's size, extension, and file signature.
    
    Parameters:
        file (UploadedFile): The uploaded file to validate; expected to be a PDF or DOCX.
    
    Returns:
        UploadedFile: The original file if all checks pass.
    
    Raises:
        ValidationError: If the file is smaller than 50 KB, larger than 10 MB, has no or unsupported extension, or its content signature does not match the declared extension.
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
    Check whether the file's leading bytes match the expected signature for the given extension.
    
    Parameters:
        file_content (bytes): Leading bytes of the file (magic bytes) to inspect.
        extension (str): File extension to validate against (e.g., 'pdf', 'docx').
    
    Returns:
        bool: `True` if the leading bytes match the expected signature for `extension`, `False` otherwise.
    """
    if extension == 'pdf':
        return file_content.startswith(PDF_MAGIC_BYTES)
    elif extension == 'docx':
        return file_content.startswith(DOCX_MAGIC_BYTES)
    return False


def format_file_size(size_bytes: int) -> str:
    """
    Convert a file size in bytes to a human-readable string using B, KB, or MB units.
    
    KB and MB values are formatted with one decimal place.
    
    Returns:
        A string representing the size with units: bytes as `B`, kilobytes as `KB` (one decimal), or megabytes as `MB` (one decimal).
    """
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
