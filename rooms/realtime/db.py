from channels.db import database_sync_to_async
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from re import fullmatch
from datetime import datetime

from django.db import IntegrityError

from rooms.models import RoomTrack


@database_sync_to_async
def room_creator_validation(room, user) -> bool:
    if room.created_by == user:
        return True
    else:
        return False


@database_sync_to_async
def get_room_by_slug(room_slug: str):
    if fullmatch(r'^\s*$', room_slug):
        raise ValueError("Error in db method get_room_by_slug: slug can't be blank or consist of just spaces")
    Room = apps.get_model('rooms', 'Room')
    return Room.objects.get(slug=room_slug)


@database_sync_to_async
def get_user_by_username(username: str):
    if fullmatch(r'^\s*$', username):
        raise ValueError("Error in db method get_user_by_username: username can't be blank or consist of just spaces ")
    from django.contrib.auth.models import User
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return None


@database_sync_to_async
def get_user_avatar(user) -> str:
    if user.is_authenticated and hasattr(user, 'profile'):
        return user.profile.get_avatar_url()
    return settings.DEFAULT_AVATAR_URL_REL


@database_sync_to_async
def toggle_vote(user_id: int, room_track_id: int) -> dict | None:
    User = get_user_model()
    RoomTrack = apps.get_model('rooms', 'RoomTrack')
    try:
        room_track = RoomTrack.objects.get(id=room_track_id)
    except RoomTrack.DoesNotExist:
        return None
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None
    return room_track.create_or_toggle_vote(user)


@database_sync_to_async
def save_message_to_db(room, message: str, user=None, timestamp=None):
    if not isinstance(message, str) and fullmatch(r'^\s*$', message):
        raise ValueError("Error in db method save_message_to_db: message can't be non string, blank or consist of just spaces")
    ChatMessage = apps.get_model('rooms', 'ChatMessage')
    ChatMessage.objects.get_or_create(room=room, user=user, message=message[:500], created_at=datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S'))


@database_sync_to_async
def get_chat_history_from_db(room_id: int, limit: int) -> list[dict[str, str]]:
    if limit < 1:
        raise ValueError('Error in db method get_chat_history_from_db: limit of messages must be more than 1')
    ChatMessage = apps.get_model('rooms', 'ChatMessage')
    qs = ChatMessage.objects.filter(room=room_id).order_by('-created_at')[:limit]
    return [
        {
            'username': msg.username,
            'message': msg.message,
            'timestamp': msg.formatted_timestamp,
            'avatar_url': msg.avatar_url,
        }
        for msg in reversed(qs)
    ]

@database_sync_to_async
def validate_room_track_in_room(room_id: int, room_track_id: int) -> bool:
    RoomTrack = apps.get_model('rooms', 'RoomTrack')
    return RoomTrack.objects.filter(room__id=room_id, id=room_track_id).exists()

@database_sync_to_async
def move_room_track_to_zone(room_track_id: int, zone_id: int, room_id: int):
    RoomTrack = apps.get_model('rooms', 'RoomTrack')
    Zone = apps.get_model('rooms', 'Zone')
    room_track = RoomTrack.objects.get(id=room_track_id, room_id=room_id)
    zone = Zone.objects.get(id=zone_id, room_id=room_id)
    if not room_track_id:
        raise IntegrityError('Not found such RoomTrack instance')
    if not zone:
        raise IntegrityError('Not found such Zone instance')
    room_track.zone = zone
    room_track.full_clean()
    room_track.save(update_fields=zone)
    return room_track

@database_sync_to_async
def move_room_track_to_playing_zone(room_track_id: int, room_id: int):
    Zone = apps.get_model('rooms', 'Zone')
    zone = Zone.objects.get(status='playing', room_id=room_id)
    return move_room_track_to_zone(room_track_id, zone.id, room_id)

@database_sync_to_async
def move_room_track_to_voting_zone(room_track_id: int, room_id: int):
    Zone = apps.get_model('rooms', 'Zone')
    zone = Zone.objects.get(status='voting', room_id=room_id)
    return move_room_track_to_zone(room_track_id, zone.id, room_id)


__all__ = [
    'room_creator_validation',
    'get_room_by_slug',
    'get_user_by_username',
    'get_user_avatar',
    'toggle_vote',
    'save_message_to_db',
    'get_chat_history_from_db',
    'validate_room_track_in_room',
    'move_room_track_to_playing_zone',
    'move_room_track_to_voting_zone'
]