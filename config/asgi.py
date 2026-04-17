"""
ASGI config for the standalone AI service layer.

Exposes the ASGI callable as a module-level variable named ``application``.

The service is pure HTTP (no WebSockets) so we wrap only Django's
stock ASGI handler. Use with uvicorn/daphne when async workers are
desired:

    uvicorn services.config.asgi:application --host 0.0.0.0 --port 9000
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.config.settings')

application = get_asgi_application()
