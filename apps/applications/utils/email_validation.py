"""
Email validation utilities.
"""

from django.core.exceptions import ValidationError
from email_validator import validate_email as email_validate, EmailNotValidError


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
        
        # Provide user-friendly error messages
        if 'dns' in error_message.lower() or 'mx' in error_message.lower():
            raise ValidationError(
                "Email domain does not have valid mail servers. "
                "Please check your email address."
            )
        elif 'syntax' in error_message.lower():
            raise ValidationError("Please enter a valid email address.")
        else:
            raise ValidationError(f"Invalid email address: {error_message}")
