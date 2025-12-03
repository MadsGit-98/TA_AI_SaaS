from celery import shared_task


@shared_task
def dummy_analysis_task():
    """
    Placeholder Celery task for the analysis app that performs no work.
    
    Returns:
        str: The static success message "Dummy analysis task completed successfully".
    """
    return "Dummy analysis task completed successfully"