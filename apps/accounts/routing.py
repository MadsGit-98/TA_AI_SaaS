from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/token-notifications/', consumers.TokenNotificationConsumer.as_asgi()),
]