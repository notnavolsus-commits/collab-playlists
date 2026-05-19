from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Count
from django.utils.text import slugify
from .forms import RoomForm
from .models import Room
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
    context = {
        'room': room,
        'tracks': tracks,
        'form': form,
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

# Create your views here.
