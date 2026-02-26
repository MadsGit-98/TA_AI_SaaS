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
    Produce a privacy-preserving masked representation of an email suitable for logging.
    
    If the input contains an '@', the local part is reduced to its first character followed by '***' (or '***' if the local part is empty) and combined with the domain (e.g., 'j***@example.com'). If the input does not contain an '@', returns a masked placeholder including the first 8 hex characters of the SHA-256 hash for traceability (e.g., '***@*** (hash: 1a2b3c4d)').
    
    Parameters:
        email (str): The email-like string to mask.
    
    Returns:
        str: The masked email string.
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
    Validate an email's format and deliverability and return the normalized address.
    
    Performs syntax validation and MX/deliverability checking; on success returns the validator-normalized email.
    
    Parameters:
        email (str): Email address to validate. If validation fails, a masked version of this input may be logged for diagnostics.
    
    Returns:
        str: Normalized email address.
    
    Raises:
        ValidationError: If the address fails syntax or deliverability checks; raised messages are user-facing and do not expose raw validator errors.
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
