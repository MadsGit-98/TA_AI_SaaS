"""
API URL Configuration for Applications App

API endpoints for job application submission and bulk upload.
"""

from django.urls import path
from .api import (
    submit_application,
    validate_file,
    validate_contact,
    BulkUploadInitView,
    BulkUploadView,
    BulkUploadValidateView,
    BulkUploadCommitView,
    BulkUploadCancelView,
    BulkUploadStatusView,
    BulkUploadSummaryView,
    BulkUploadDecisionView,
)

app_name = 'applications_api'

urlpatterns = [
    # API endpoints
    path('', submit_application, name='submit_application'),
    path('validate-file/', validate_file, name='validate_file'),
    path('validate-contact/', validate_contact, name='validate_contact'),
    
    # Bulk upload endpoints
    path('bulk-upload/init/', BulkUploadInitView.as_view(), name='bulk-upload-init'),
    path('bulk-upload/upload/', BulkUploadView.as_view(), name='bulk-upload-upload'),
    path('bulk-upload/validate/', BulkUploadValidateView.as_view(), name='bulk-upload-validate'),
    path('bulk-upload/commit/', BulkUploadCommitView.as_view(), name='bulk-upload-commit'),
    path('bulk-upload/cancel/<uuid:batch_id>/', BulkUploadCancelView.as_view(), name='bulk-upload-cancel'),
    path('bulk-upload/status/<uuid:batch_id>/', BulkUploadStatusView.as_view(), name='bulk-upload-status'),
    path('bulk-upload/summary/<uuid:batch_id>/', BulkUploadSummaryView.as_view(), name='bulk-upload-summary'),
    path('bulk-upload/decisions/', BulkUploadDecisionView.as_view(), name='bulk-upload-decisions'),
]
