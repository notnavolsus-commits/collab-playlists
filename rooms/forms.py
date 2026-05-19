from django import forms
from django.core.exceptions import ValidationError

from .models import Room

class RoomForm(forms.Form):
    name = forms.CharField(max_length=200)

    def clean_name(self):
        name = self.cleaned_data['name']
        name_lower = name.lower()
        duplicates = Room.objects.filter(name__iexact=name_lower)
        if duplicates.exists():
            raise ValidationError('Комната с таким именем уже существует')
        return name


