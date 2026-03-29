"""
WebSocket routing configuration

Defines URL routing for WebSocket consumers.
"""

from django.urls import re_path
from apps.applications.consumers import BulkUploadConsumer

websocket_urlpatterns = [
    re_path(r'^ws/bulk-upload/(?P<batch_id>[A-Za-z0-9_-]+)/$', BulkUploadConsumer.as_asgi()),
]
