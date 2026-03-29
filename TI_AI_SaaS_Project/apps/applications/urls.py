"""
URL Configuration for Applications App

Public endpoints for job application submission.
"""

from django.urls import path
from . import views

app_name = 'applications'

urlpatterns = [
    # Template views
    path('apply/<uuid:application_link>/', views.application_form_view, name='application_form'),
    path('application/success/<uuid:application_id>/<uuid:access_token>/', views.application_success_view, name='application_success'),
    
    # Bulk upload views
    path('bulk-upload/<uuid:job_listing_id>/', views.bulk_upload_view, name='bulk_upload'),
    path('bulk-upload/summary/<uuid:batch_id>/', views.bulk_upload_summary_view, name='bulk_upload_summary'),
]
