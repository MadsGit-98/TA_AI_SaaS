"""
WebSocket routing configuration for applications app

Defines URL routing for bulk upload consumers.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/bulk-upload/(?P<batch_id>[A-Za-z0-9_-]+)/$', consumers.BulkUploadConsumer.as_asgi()),
]
