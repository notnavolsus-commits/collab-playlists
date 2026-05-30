from django.db import models
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

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']

class RoomTrack(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='tracks')
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='added_tracks')
    position = models.IntegerField(default=0)
    is_playing = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.track} в комнате {self.room}'

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['room', 'track'], name='unique_comb_track_room')
        ]

class Vote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='votes')
    room_track = models.ForeignKey(RoomTrack, on_delete=models.CASCADE, related_name='votes')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user} голосует за {self.room_track}'

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'room_track'], name='unique_comb_user_track')
        ]

