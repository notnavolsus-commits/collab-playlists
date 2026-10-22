from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, IntegrityError
from django.db.models import Count
from django.db.models.functions import Lower
from django.contrib.auth.models import User

from tracks.models import Track
from django.contrib.auth.hashers import make_password, check_password

class Room(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Имя комнаты')
    slug = models.SlugField(max_length=100, unique=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_private = models.BooleanField(default=False)
    password = models.CharField(max_length=128, blank=True, null=True)

    def set_password(self) -> None:
        if self.is_private and not self.password:
            raise ValidationError('Private room must have password')
        if self.password and not self.is_private:
            self.password = None
        if self.password and not self.password.startswith('pbkdf2_'): #TODO: password starts with pbkdf2_ won't be hashed
            self.password = make_password(self.password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(name='name_is_not_just_spaces', condition=~models.Q(name__regex=r'^\s*$')),
            models.UniqueConstraint(Lower('name'), name='unique_name')
        ]

class Zone(models.Model):
    STATUS = [('standard', [('playing', 'Playing'), ('voting', 'Voting')]), ]

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='zones')
    status = models.CharField(max_length=20, choices=STATUS, default='voting')
    votable = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.status} zone of {self.room} room"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['room', 'status'], name='unique_zone_in_room')
        ]

class RoomTrack(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='tracks')
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='added_tracks')
    created_at = models.DateTimeField(auto_now_add=True)
    played_at = models.DateTimeField(null=True, blank=True)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='tracks', blank=True, null=True)

    def __str__(self):
        return f'{self.track} in room {self.room}'

    def create_or_toggle_vote(self, user: User) -> dict[str, str | int | list[int]]:
        if not self.zone.votable:
            raise IntegrityError('You can not vote for track from not votable zone')
        vote = Vote.objects.filter(user=user, room_track=self)
        if vote.exists():
            vote.delete()
        else:
            Vote.objects.create(user=user, room_track=self)
        action = 'vote_update'
        new_votes_count = Vote.objects.filter(room_track=self).count()
        room = self.room
        room_tracks = RoomTrack.objects.filter(room=room, zone=self.zone).annotate(vote_count=Count('votes')).order_by('-vote_count',
                                                                                                       'created_at')
        new_order = list(room_tracks.values_list('id', flat=True))
        return {
            'zone': self.zone.status,
            'new_votes_count': new_votes_count,
            'action': action,
            'room_track_id': self.id,
            'new_order': new_order,
        }

    def clean(self):
        super().clean()
        if self.zone.room.id != self.room.id:
            raise ValidationError('RoomTrack zone can\'t be in other room, than RoomTrack')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['room', 'track'], name='unique_comb_track_room')
        ]

class Vote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='votes')
    room_track = models.ForeignKey(RoomTrack, on_delete=models.CASCADE, related_name='votes')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} voting for {self.room_track}'

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'room_track'], name='unique_comb_user_track')
        ]

class ChatMessage(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='chat_messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name='chat_messages')
    message = models.CharField(max_length=500)
    created_at = models.DateTimeField()

    @property
    def avatar_url(self) -> str:
        if hasattr(self.user, 'profile'):
            return self.user.profile.get_avatar_url() or settings.DEFAULT_AVATAR_URL_REL
        return settings.DEFAULT_AVATAR_URL_REL

    @property
    def formatted_timestamp(self) -> str:
        return self.created_at.strftime('%Y-%m-%d %H:%M:%S')

    @property
    def username(self) -> str:
        if self.user and self.user.username:
            return self.user.username
        return 'Anonymous'

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(name='message_is_not_empty', condition=~models.Q(message__regex=r'^\s*$')),
        ]

