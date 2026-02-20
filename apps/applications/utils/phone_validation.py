"""
Phone number validation utilities using phonenumbers library.
"""

from django.core.exceptions import ValidationError
import phonenumbers


def validate_phone(phone: str, country_code: str = 'US') -> str:
    """
    Validate and normalize phone number to E.164 format.
    
    Args:
        phone: Phone number string
        country_code: ISO 3166-1 alpha-2 country code (default: 'US')
        
    Returns:
        Phone number in E.164 format (e.g., '+12025551234')
        
    Raises:
        ValidationError: If phone number is invalid
    """
    try:
        # Parse the phone number
        parsed = phonenumbers.parse(phone, country_code)
        
        # Check if it's a valid number
        if not phonenumbers.is_valid_number(parsed):
            raise ValidationError(
                "Invalid phone number. Please include country code."
            )
        
        # Return E.164 format
        return phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.E164
        )
    except phonenumbers.NumberParseException as e:
        error_message = str(e)
        
        if 'invalid' in error_message.lower():
            raise ValidationError(
                "Invalid phone number format. Please include country code."
            )
        elif 'too short' in error_message.lower():
            raise ValidationError("Phone number is too short.")
        elif 'too long' in error_message.lower():
            raise ValidationError("Phone number is too long.")
        else:
            raise ValidationError(f"Invalid phone number: {error_message}")


def format_phone_for_display(phone: str) -> str:
    """
    Format phone number for display in international format.
    
    Args:
        phone: Phone number in E.164 format
        
    Returns:
        Formatted phone number (e.g., '+1 202-555-1234')
    """
    try:
        parsed = phonenumbers.parse(phone, None)
        return phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
    except phonenumbers.NumberParseException:
        return phone
