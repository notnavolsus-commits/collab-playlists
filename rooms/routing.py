from django.urls import re_path
from rooms.realtime.consumers import ConsumerInRoom

websocket_urlpatterns = [re_path(r'^ws/rooms/(?P<room_slug>[\w-]+)/$', ConsumerInRoom.as_asgi())]