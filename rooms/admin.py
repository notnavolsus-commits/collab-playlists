from django.contrib import admin
from rooms.models import Room, Vote, RoomTrack

admin.site.register([Room, Vote, RoomTrack])
# Register your models here.
