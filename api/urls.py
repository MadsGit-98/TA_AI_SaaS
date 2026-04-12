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
from services.api.webhook import DjangoWebhookView

app_name = 'api'

urlpatterns = [
    # Analysis endpoints
    path('analysis/initiate/', InitiateAnalysisView.as_view(), name='initiate'),
    path('analysis/<str:job_id>/rerun/', RerunAnalysisView.as_view(), name='rerun'),
    path('analysis/<str:job_id>/status/', AnalysisStatusView.as_view(), name='status'),
    path('analysis/<str:job_id>/cancel/', CancelAnalysisView.as_view(), name='cancel'),

    # Health check endpoints
    path('health/', HealthView.as_view(), name='health'),
    path('ready/', ReadyView.as_view(), name='ready'),

    # Webhook endpoint (receives updates FROM AI service, sends TO Django)
    # Note: This is called by the AI service to push updates to Django
    path('internal/analysis/webhook/', DjangoWebhookView.as_view(), name='webhook'),
]
