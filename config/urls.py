"""
AI Service URL Configuration

Lightweight URL routing for the AI service API.
"""

from django.urls import path, include

urlpatterns = [
    path('api/v1/', include('services.api.urls')),
    path('health', include('services.api.urls')),
    path('ready', include('services.api.urls')),
]
