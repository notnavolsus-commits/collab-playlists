from django.db.models import Count
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from rooms.models import RoomTrack, Room
from .forms import TrackForm
from .models import Track


@login_required
def add_track(request, room_slug):
    room = get_object_or_404(Room, slug=room_slug)
    if request.method == 'POST':
        form = TrackForm(request.POST, request.FILES)
        if form.is_valid():
            title = form.cleaned_data['title']
            artist = form.cleaned_data['artist']
            audio_file = form.cleaned_data['audio_file']
            cover_image = form.cleaned_data['cover_image']
            cover_url = form.cleaned_data['cover_url']
            track = Track.objects.create(
                title=title,
                artist=artist,
                audio_file=audio_file,
                added_by=request.user,
                cover_image=cover_image,
                cover_url=cover_url,
            )
            room_track = RoomTrack.objects.create(
                room=room,
                track=track,
                added_by=request.user,
            )

            return redirect('room_detail', room_slug=room.slug)

        tracks = room.tracks.annotate(
            vote_count=Count('votes')
        )
        return render(request, 'room_detail.html', {'form': form, 'room': room, 'tracks': tracks})

    else:
        form = TrackForm()
        tracks = room.tracks.annotate(
            vote_count=Count('votes')
        )
        return render(request, 'room_detail.html', {'form': form, 'room': room, 'tracks': tracks})
