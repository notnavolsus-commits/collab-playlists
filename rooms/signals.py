from django.db.models.signals import post_save
from .models import Zone, Room
from django.dispatch import receiver

@receiver(post_save, sender=Room)
def create_standard_zones(sender, instance, created, **kwargs):
    if created:
        Zone.objects.get_or_create(room=instance, status='voting')
        Zone.objects.get_or_create(room=instance, status='playing', votable=False)