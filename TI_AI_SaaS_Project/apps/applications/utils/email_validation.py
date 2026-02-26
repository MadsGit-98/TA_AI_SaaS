"""
Email validation utilities.
"""

import logging
import hashlib
from django.core.exceptions import ValidationError
from email_validator import validate_email as email_validate, EmailNotValidError

logger = logging.getLogger(__name__)


def _mask_email(email: str) -> str:
    """
    Create a masked representation of an email address for logging.
    
    Keeps first character of local part and domain for debugging
    while protecting user privacy.
    
    Args:
        email: Email address to mask
        
    Returns:
        Masked email string (e.g., 'j***@example.com')
    """
    if '@' not in email:
        # If email is malformed, hash it for logging
        return f"***@*** (hash: {hashlib.sha256(email.encode()).hexdigest()[:8]})"
    
    local_part, domain = email.rsplit('@', 1)
    
    if len(local_part) > 0:
        # Keep first character, mask the rest
        masked_local = local_part[0] + '***'
    else:
        masked_local = '***'
    
    return f"{masked_local}@{domain}"


def validate_email(email: str) -> str:
    """
    Validate email format and MX record.

    Args:
        email: Email address to validate

    Returns:
        Normalized email address

    Raises:
        ValidationError: If email is invalid
    """
    try:
        # Validate email format and check MX record
        valid = email_validate(
            email,
            check_deliverability=True,  # Check MX record
            test_environment=False  # Set to True for testing
        )
        return valid.email  # Return normalized email
    except EmailNotValidError as e:
        error_message = str(e)
        
        # Create masked email for logging (never log full email - PII)
        masked_email = _mask_email(email)

        # Log the error for debugging/diagnostics using lazy formatting
        logger.debug("Email validation failed for '%s': %s", masked_email, error_message)

        # Normalize error message for stable comparison
        error_lower = error_message.lower()

        # Map to user-friendly messages based on error category
        if 'dns' in error_lower or 'mx' in error_lower:
            raise ValidationError(
                "Email domain does not have valid mail servers. "
                "Please check your email address."
            )
        elif 'syntax' in error_lower or 'invalid' in error_lower:
            raise ValidationError("Please enter a valid email address.")
        else:
            # Generic message for all other cases - do not expose raw error
            raise ValidationError("Invalid email address.")
