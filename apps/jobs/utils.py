import logging
from django.utils import timezone
from .models import JobListing


logger = logging.getLogger(__name__)


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
        log_message += f" | Extra: {extra_data}"
    
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