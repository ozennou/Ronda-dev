from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/matchmaking/(?P<player_id>\d+)$', consumers.MatchMakerConsumer.as_asgi()),
    re_path(r'ws/game/(?P<room_name>[-\w.!]+)/(?P<player_num>[12])$', consumers.GameConsumer.as_asgi()),
    re_path(r'ws/bot_game/(?P<room_name>[-\w.!]+)/(?P<player_num>[2])$', consumers.GameConsumer.as_asgi()),
]