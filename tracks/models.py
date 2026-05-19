from django.db import models
from django.contrib.auth.models import User


class Track(models.Model):
    title = models.CharField(max_length=200)
    artist = models.CharField(max_length=200)
    video_url = models.URLField(blank=True, null=True)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tracks')
    created_at = models.DateTimeField(auto_now_add=True)
    audio_file = models.FileField(upload_to='tracks/audio', blank=True, null=True)
    # duration =
    # file_size =