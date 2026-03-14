"""
URLs for AI Analysis API Endpoints

These are the API endpoints for programmatic access.
Mounted at /api/analysis/ in main urls.py
"""

from django.urls import path
from .api import (
    initiate_analysis,
    analysis_status,
    analysis_results,
    analysis_result_detail,
    cancel_analysis,
    rerun_analysis,
    analysis_statistics,
)

app_name = 'analysis_api'

urlpatterns = [
    # API Endpoints
    path('jobs/<uuid:job_id>/analysis/initiate/', initiate_analysis, name='api-initiate-analysis'),
    path('jobs/<uuid:job_id>/analysis/status/', analysis_status, name='api-analysis-status'),
    path('jobs/<uuid:job_id>/analysis/results/', analysis_results, name='api-analysis-results'),
    path('results/<uuid:result_id>/', analysis_result_detail, name='api-analysis-result-detail'),
    path('jobs/<uuid:job_id>/analysis/cancel/', cancel_analysis, name='api-cancel-analysis'),
    path('jobs/<uuid:job_id>/analysis/re-run/', rerun_analysis, name='api-rerun-analysis'),
    path('jobs/<uuid:job_id>/analysis/statistics/', analysis_statistics, name='api-analysis-statistics'),
]
