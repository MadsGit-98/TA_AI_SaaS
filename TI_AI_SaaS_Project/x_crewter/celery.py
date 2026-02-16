import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'x_crewter.settings')

app = Celery('x_crewter')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Add periodic task to check job statuses every minute
app.conf.beat_schedule = {
    # Existing task
    'monitor-and-refresh-tokens': {
        'task': 'apps.accounts.tasks.monitor_and_refresh_tokens',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    # New task for job status checks
    'check-job-statuses': {
        'task': 'apps.jobs.tasks.check_job_statuses',
        'schedule': 60.0,  # Every 60 seconds
    },
}