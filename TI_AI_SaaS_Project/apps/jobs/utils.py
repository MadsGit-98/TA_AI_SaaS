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
    Recursively redacts sensitive values for safe logging and truncates overly long strings.
    
    Parameters:
        data: The input to sanitize; may be a dict, list, string, or other value. Dicts and lists are processed recursively.
    
    Returns:
        The sanitized representation of `data` where values for sensitive keys are replaced with "[REDACTED]" and strings longer than 1000 characters are truncated with "..." appended.
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
    Record a standardized audit log entry for a job listing operation.
    
    Logs operation type, job identifier, and the acting user; if `user` is not provided the log will indicate an unknown actor. If `extra_data` is supplied it will be sanitized (sensitive keys redacted and long strings truncated) before being included in the log entry.
    
    Parameters:
        operation_type (str): The kind of operation performed (e.g., "create", "update", "activate", "deactivate", "delete", "duplicate").
        job_id: Identifier of the affected job.
        user (optional): The user who performed the operation; may be None.
        extra_data (optional): Additional contextual data to include; will be sanitized for sensitive fields.
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
    Record a job listing's status transition in the audit log.
    
    Logs an informational message with the job's title and ID, the status change (old -> new), and the acting user. If `job` is None, logs a warning and returns without further action. When `user` is omitted, the entry records "System" as the actor.
    
    Parameters:
        job (JobListing): The job instance whose status changed.
        old_status (str): Previous status value.
        new_status (str): New status value.
        user (User, optional): User who triggered the change; logged as their `username` if provided.
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