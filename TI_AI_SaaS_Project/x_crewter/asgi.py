"""
ASGI config for x_crewter project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'x_crewter.settings')

# Import get_asgi_application first to ensure Django is initialized
from django.core.asgi import get_asgi_application

# Initialize Django
django_asgi_app = get_asgi_application()

from django.urls import path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Import consumers after Django initialization
from apps.accounts import consumers

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter([
            # WebSocket patterns for token notifications
            path('ws/token-notifications/', consumers.TokenNotificationConsumer.as_asgi()),
        ])
    ),
})