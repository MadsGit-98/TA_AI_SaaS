"""
AI Service URL Configuration

Lightweight URL routing for the AI service API.

Exposes:
- /api/v1/...    all analysis + health endpoints (API-key protected)
- /health        liveness/readiness (no auth, used by orchestrators)
- /ready         dependency readiness (no auth, used by orchestrators)
"""

from django.urls import path, include

from services.api.views import HealthView, ReadyView

urlpatterns = [
    path('api/v1/', include('services.api.urls')),
    path('health', HealthView.as_view(), name='health_root'),
    path('ready', ReadyView.as_view(), name='ready_root'),
]
