"""
Email validation utilities.
"""

import logging
from django.core.exceptions import ValidationError
from email_validator import validate_email as email_validate, EmailNotValidError

logger = logging.getLogger(__name__)


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

        # Log the original error for debugging/diagnostics
        logger.debug(f"Email validation failed for '{email}': {error_message}")

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
