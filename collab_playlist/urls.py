"""
URL configuration for collab_playlist project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from rooms.views import *
from tracks.views import add_track
from django.conf import settings
from django.conf.urls.static import static
from accounts import views as users_views

urlpatterns = [
    path('', rooms_list, name='rooms_list'),
    path('admin/', admin.site.urls),
    path('rooms/<slug:room_slug>/', room_detail, name='room_detail'),
    path('rooms/<slug:room_slug>/add_track/', add_track, name='add_track'),
    path('register/', users_views.register, name='register'),
    path('login/', users_views.user_login, name='login'),
    path('logout/', users_views.user_logout, name='logout'),
    path('profile/', users_views.profile, name='profile'),
    path('create_room/', create_room, name='create_room'),
    path('rooms/<slug:room_slug>/delete_track/<int:track_id>/', delete_track, name='delete_track'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)