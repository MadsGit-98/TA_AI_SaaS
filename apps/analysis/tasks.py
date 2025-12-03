from celery import shared_task


@shared_task
def dummy_analysis_task():
    """
    Dummy task for the analysis app - to be replaced with real functionality in future features
    """
    return "Dummy analysis task completed successfully"