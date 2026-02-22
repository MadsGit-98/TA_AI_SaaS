"""
URL Configuration for Applications App

Public endpoints for job application submission.
"""

from django.urls import path
from . import views
from .api import (
    submit_application,
    validate_file,
    validate_contact,
    get_application_status,
)

app_name = 'applications'

urlpatterns = [
    # Template views
    path('apply/<uuid:job_id>/', views.application_form_view, name='application_form'),
    path('application/success/<uuid:application_id>/<uuid:access_token>/', views.application_success_view, name='application_success'),

    # API endpoints
    path('', submit_application, name='submit_application'),
    path('validate-file/', validate_file, name='validate_file'),
    path('validate-contact/', validate_contact, name='validate_contact'),
    path('<uuid:application_id>/', get_application_status, name='application_status'),
]
