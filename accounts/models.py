from django.db import models
from django.contrib.auth.models import User
from PIL import Image
import os
from django.conf import settings

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def __str__(self):
        return f'{self.user.username}\'s profile'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.avatar and self.avatar.path and os.path.exists(self.avatar.path):
            try:
                img = Image.open(self.avatar.path)
                if img.height > 200 or img.width > 200:
                    output_size = (200, 200)
                    img.thumbnail(output_size)
                    img.save(self.avatar.path)
            except Exception as e:
                print(f'Ошибка обработки аватара: {e}')

    def get_avatar_url(self):
        if self.avatar and self.avatar.url:
            return self.avatar.url
        return settings.DEFAULT_AVATAR_URL

    def get_avatar_url_relative(self):
        if self.avatar and self.avatar.url:
            return '/media' + self.avatar.url.split('media')[1]
        return '/media' + settings.DEFAULT_AVATAR_URL.split('media')[1]
