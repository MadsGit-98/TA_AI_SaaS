from celery import shared_task


@shared_task
def dummy_applications_task():
    """
    Dummy task for the applications app - to be replaced with real functionality in future features
    """
    return "Dummy applications task completed successfully"