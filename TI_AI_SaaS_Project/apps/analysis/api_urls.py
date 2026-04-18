"""
URLs for AI Analysis API Endpoints

These are the API endpoints for programmatic access.
Mounted at /api/analysis/ in main urls.py
"""

from django.urls import path
from .api import (
    initiate_analysis,
    analysis_results,
    analysis_result_detail,
    get_applicant_resume,
    cancel_analysis,
    rerun_analysis,
    analysis_statistics,
)
from .webhook import analysis_webhook

app_name = 'analysis_api'

urlpatterns = [
    # API Endpoints
    path('jobs/<uuid:job_id>/analysis/initiate/', initiate_analysis, name='api-initiate-analysis'),
    path('jobs/<uuid:job_id>/analysis/results/', analysis_results, name='api-analysis-results'),
    path('results/<uuid:result_id>/', analysis_result_detail, name='api-analysis-result-detail'),
    path('applicants/<uuid:applicant_id>/resume/', get_applicant_resume, name='api-get-applicant-resume'),
    path('jobs/<uuid:job_id>/analysis/cancel/', cancel_analysis, name='api-cancel-analysis'),
    path('jobs/<uuid:job_id>/analysis/re-run/', rerun_analysis, name='api-rerun-analysis'),
    path('jobs/<uuid:job_id>/analysis/statistics/', analysis_statistics, name='api-analysis-statistics'),

    # Webhook endpoint (receives updates FROM AI service; HMAC: internal_service_hmac_required)
    path('internal/analysis/webhook/', analysis_webhook, name='analysis-webhook'),
]
