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
    path('application/success/<uuid:application_id>/', views.application_success_view, name='application_success'),
    
    # API endpoints (public, unauthenticated)
    path('api/applications/', submit_application, name='submit_application'),
    path('api/applications/validate-file/', validate_file, name='validate_file'),
    path('api/applications/validate-contact/', validate_contact, name='validate_contact'),
    path('api/applications/<uuid:application_id>/', get_application_status, name='application_status'),
]
