import logging
from django.utils import timezone
from .models import JobListing


logger = logging.getLogger(__name__)

# Define sensitive keys that should be redacted from logs
SENSITIVE_KEYS = {
    "password", "token", "secret", "ssn", "api_key", "access_token",
    "refresh_token", "auth_token", "session_id", "credit_card",
    "cvv", "pin", "key", "private_key", "public_key", "oauth_token",
    "authorization", "bearer", "credentials", "cert", "certificate"
}


def sanitize_extra_data(data):
    """
    Sanitize sensitive data in logs by replacing values for sensitive keys with '[REDACTED]'.

    Args:
        data: Input data which can be dict, list, or other types

    Returns:
        Safe redacted representation of the input data
    """
    if isinstance(data, dict):
        sanitized_dict = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_KEYS:
                sanitized_dict[key] = "[REDACTED]"
            elif isinstance(value, (dict, list)):
                sanitized_dict[key] = sanitize_extra_data(value)
            else:
                sanitized_dict[key] = value
        return sanitized_dict
    elif isinstance(data, list):
        return [sanitize_extra_data(item) for item in data]
    else:
        # For non-dict inputs, return as is or truncate if too long
        if isinstance(data, str) and len(data) > 1000:
            return data[:1000] + "..."
        return data


def log_job_operation(operation_type, job_id, user=None, extra_data=None):
    """
    Log job listing operations for auditing purposes.

    Args:
        operation_type (str): Type of operation (create, update, activate, deactivate, delete, duplicate)
        job_id (UUID): ID of the job being operated on
        user (User, optional): User performing the operation
        extra_data (dict, optional): Additional data about the operation
    """
    user_info = f"User: {user.username if user else 'Unknown'}"
    job_info = f"Job ID: {job_id}"
    operation_info = f"Operation: {operation_type}"

    log_message = f"[JOB OPERATION] {operation_info} | {job_info} | {user_info}"

    if extra_data:
        sanitized_extra_data = sanitize_extra_data(extra_data)
        log_message += f" | Extra: {sanitized_extra_data}"

    logger.info(log_message)


def log_job_status_change(job, old_status, new_status, user=None):
    """
    Log job status changes specifically.

    Args:
        job (JobListing): The job instance
        old_status (str): Previous status
        new_status (str): New status
        user (User, optional): User who triggered the change
    """
    if job is None:
        logger.warning("[JOB STATUS CHANGE] Called with None job object")
        return

    user_info = f"User: {user.username if user else 'System'}"
    job_info = f"Job: {job.title} (ID: {job.id})"
    status_info = f"Status: {old_status} -> {new_status}"

    log_message = f"[JOB STATUS CHANGE] {status_info} | {job_info} | {user_info}"
    logger.info(log_message)


def log_failed_job_operation(operation_type, job_id, error_message, user=None):
    """
    Log failed job operations.
    
    Args:
        operation_type (str): Type of operation that failed
        job_id (UUID): ID of the job involved
        error_message (str): Error message
        user (User, optional): User who attempted the operation
    """
    user_info = f"User: {user.username if user else 'Unknown'}"
    job_info = f"Job ID: {job_id}"
    operation_info = f"Operation: {operation_type}"
    error_info = f"Error: {error_message}"
    
    log_message = f"[FAILED JOB OPERATION] {operation_info} | {job_info} | {user_info} | {error_info}"
    logger.warning(log_message)