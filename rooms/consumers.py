import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Room, RoomTrack, Vote
from django.contrib.auth.models import User

class ConsumerInRoom(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_slug = self.scope['url_route']['kwargs']['room_slug']
        self.room_group_name = f'room_{self.room_slug}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data['action'] == 'vote':
            room_track_id = data['room_track_id']
            if self.scope['user'].is_authenticated:
                user_id = self.scope['user'].id
            else:
                return
            toggle_dict = await self.toggle_vote(user_id, room_track_id)
            await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'send_vote_update',
                **toggle_dict
            }
        )

    @database_sync_to_async
    def toggle_vote(self, user_id, room_track_id):
        try:
            room_track = RoomTrack.objects.get(id=room_track_id)
        except RoomTrack.DoesNotExist:
            return
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return
        vote = Vote.objects.filter(user=user, room_track=room_track)
        if vote.exists():
            vote.delete()
            action = 'unvoted'
        else:
            Vote.objects.create(user=user, room_track=room_track)
            action = 'voted'
        new_votes_count = Vote.objects.filter(room_track=room_track).count()
        return {
            'new_votes_count': new_votes_count,
            'action': action,
            'room_track_id': room_track_id
        }

    async def send_vote_update(self, event):
        await self.send(text_data=json.dumps({
            'room_track_id': event['room_track_id'],
            'new_votes_count': event['new_votes_count'],
            'action': event['action'],
        }))