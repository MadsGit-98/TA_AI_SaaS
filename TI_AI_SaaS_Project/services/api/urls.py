"""
AI Service API URL Configuration

Defines all API endpoints for the AI service layer.
"""

from django.urls import path
from services.api.views import (
    InitiateAnalysisView,
    RerunAnalysisView,
    AnalysisStatusView,
    CancelAnalysisView,
    HealthView,
    ReadyView,
)

app_name = 'api'

urlpatterns = [
    path('analysis/initiate/', InitiateAnalysisView.as_view(), name='initiate'),
    path('analysis/<str:job_id>/rerun/', RerunAnalysisView.as_view(), name='rerun'),
    path('analysis/<str:job_id>/status/', AnalysisStatusView.as_view(), name='status'),
    path('analysis/<str:job_id>/cancel/', CancelAnalysisView.as_view(), name='cancel'),

    path('health/', HealthView.as_view(), name='health'),
    path('ready/', ReadyView.as_view(), name='ready'),
]
