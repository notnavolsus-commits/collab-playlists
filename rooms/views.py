import os
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Count
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import RoomForm
from .models import Room, RoomTrack
from tracks.forms import TrackForm
from random import randint
from time import time

def rooms_list(request):
    rooms = Room.objects.filter(is_active=True)
    return render(request, 'rooms_list.html', {'rooms': rooms})

def room_detail(request, room_slug):
    room = get_object_or_404(Room, slug=room_slug)
    tracks = room.tracks.annotate(
        vote_count = Count('votes')
    )
    form = TrackForm()
    tracks_count = tracks.count()
    if tracks_count % 10 == 1 and tracks_count % 100 != 11:
        count_word = 'трек'
    elif 2 <= tracks_count % 10 <= 4 and (tracks_count % 100 < 10 or tracks_count % 100 >= 20):
        count_word = 'трека'
    else:
        count_word = 'треков'
    context = {
        'room': room,
        'tracks': tracks,
        'form': form,
        'tracks_count': str(tracks_count) + ' ' + count_word,
    }
    return render(request, 'room_detail.html', context)

@login_required
def create_room(request):
    if request.method == 'GET':
        form = RoomForm()
        return render(request, 'create_room.html', {'form': form})
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            slug = slugify(name)
            duplicates = Room.objects.filter(slug=slug)
            tries = 10
            while duplicates.exists() and tries > 0:
                slug += '-' + str(randint(0, 1000000))
                duplicates = Room.objects.filter(slug=slug)
                tries -= 1
                if not tries:
                    slug += str(time()).replace('.', '-')
                    break
            room = Room.objects.create(name=name, created_by=request.user, slug=slug)
            return redirect('room_detail', room_slug=slug)
        return render(request, 'create_room.html', {'form': form})

def is_staff_or_creator(model):
    def decorator(view):
        def wrapper(request, **kwargs):
            if model == 'room':
                room = Room.objects.get(slug=kwargs['room_slug'])
            elif model == 'track':
                room_track = RoomTrack.objects.get(id=kwargs['track_id'])
                room = room_track.room
                kwargs.update({'track': room_track})
            else:
                raise ValueError('Другие модели не предусмотрены для декорирования is_staff_or_created_by')
            if request.user.is_staff or room.created_by == request.user:
                kwargs.update({'room': room})
                return view(request, **kwargs)
            else:
                raise PermissionDenied
        return wrapper
    return decorator


@require_POST
@login_required
@is_staff_or_creator('track')
def delete_track(request, **kwargs):
    room = kwargs.get('room')
    room_track = kwargs.get('track')
    track = room_track.track
    room_track.delete()
    if RoomTrack.objects.filter(track=track).count() == 0:
        if track.audio_file and os.path.exists(track.audio_file.path):
            os.remove(track.audio_file.path)
        track.delete()
    return JsonResponse({'track_id': track.id, 'success': True})


@is_staff_or_creator('room')
def delete_room(request):
    pass




