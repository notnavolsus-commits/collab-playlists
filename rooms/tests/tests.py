import asyncio
import json

import pytest
import pytest_asyncio
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model

from rooms.models import Room, RoomTrack
from rooms.realtime.consumers import ConsumerInRoom
from rooms.realtime.services import ChatService, BroadcastService
from rooms.realtime.stores import BroadcastRedisStore, ChatRedisStore
from tracks.models import Track
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from django.urls.conf import re_path

User = get_user_model()

test_routes = [re_path(r'^ws/rooms/(?P<room_slug>[\w-]+)/$', ConsumerInRoom.as_asgi())]


@pytest.fixture
def user(db):
    return User.objects.create(username='New_user')


@pytest.fixture
def room(db, user):
    return Room.objects.create(name='New Room', slug='new-room', created_by=user)


async def build_consumer(room_slug: str, user: User):
    app = URLRouter(test_routes)
    communicator = WebsocketCommunicator(app, f'ws/rooms/{room_slug}/')
    communicator.scope['user'] = user
    connected, _ = await communicator.connect(timeout=10)
    return connected, communicator


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_consumer(user, room):
    connected, comm = await build_consumer(room.slug, user)
    await comm.send_to(text_data=json.dumps({'action': 'chat_message', 'message': '[] string null'}))
    res = await comm.receive_from(10)
    print(res)


@pytest_asyncio.fixture(autouse=True)
async def teardown():
    yield
    await BroadcastRedisStore.clear_state(1)
    await ChatRedisStore.delete_history(1)
