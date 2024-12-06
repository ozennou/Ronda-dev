import os
import django
from django.conf import settings
import logging

django.setup()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'game2.settings')

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

from app.routing import websocket_urlpatterns



application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})