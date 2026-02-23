"""
API URL Configuration for Applications App

API endpoints for job application submission.
"""

from django.urls import path
from .api import (
    submit_application,
    validate_file,
    validate_contact,
    get_application_status,
)

app_name = 'applications_api'

urlpatterns = [
    # API endpoints
    path('', submit_application, name='submit_application'),
    path('validate-file/', validate_file, name='validate_file'),
    path('validate-contact/', validate_contact, name='validate_contact'),
    path('<uuid:application_id>/', get_application_status, name='application_status'),
]
