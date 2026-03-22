"""
WebSocket Routing for AI Analysis Application

This module defines the WebSocket URL patterns for the analysis app.
"""

from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/analysis-notifications/', consumers.AnalysisNotificationConsumer.as_asgi()),
]
