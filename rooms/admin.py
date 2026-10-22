from django.contrib import admin
from rooms.models import Room, Vote, RoomTrack, Zone

admin.site.register([Room, Vote, RoomTrack, Zone])
# Register your models here.
