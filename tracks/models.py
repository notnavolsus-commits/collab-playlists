import os
from django.db import models
from django.contrib.auth.models import User


def upload_media_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f'{instance.artist} - {instance.title}.{ext}'
    if ext in ('jpg' ,'jpeg', 'webp', 'png'):
        return os.path.join('covers', filename)
    return os.path.join('tracks/audio', filename)

class Track(models.Model):
    title = models.CharField(max_length=200, verbose_name='Название')
    artist = models.CharField(max_length=200, verbose_name='Исполнитель')
    video_url = models.URLField(blank=True, null=True, verbose_name='Ссылка на видео')
    added_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tracks', verbose_name='Добавлено')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')
    audio_file = models.FileField(upload_to=upload_media_path, blank=True, null=True, verbose_name='Файл с аудио')
    cover_url = models.URLField(blank=True, null=True, verbose_name='Ссылка на обложку')
    cover_image = models.ImageField(upload_to=upload_media_path, blank=True, null=True, verbose_name='Файл обложки')

    def get_cover_image(self):
        if self.cover_image:
            return self.cover_image.url
        return self.cover_url

    def __str__(self):
        return f'{self.artist} - {self.title}'
    # duration =
    # file_size =