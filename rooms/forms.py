from django import forms
from django.core.exceptions import ValidationError

from .models import Room
from re import search


def custom_validate_password(password):
    if len(password) < 8:
        raise ValidationError('Длина пароля не должна быть меньше 8 символов')
    if not search(r'\d', password):
        raise ValidationError('Пароль должен содержать цифры')
    if not search(r'[A-Za-z]', password):
        raise ValidationError('Пароль должен содержать хотя бы одну букву')
    if not search(r'[!@#$%^&*(),.?":;|<>]', password):
        raise ValidationError('Пароль должен содержать хотя бы один специальный символ (!@#$%^&* и т.д.).')

class RoomForm(forms.Form):
    name = forms.CharField(max_length=30, label='Имя комнаты: ')
    is_private = forms.BooleanField(required=False, label='Приватная/Общая ')
    password = forms.CharField(max_length=128, min_length=8, required=False, widget=forms.PasswordInput, validators=[custom_validate_password], label='Пароль ')

    def clean_name(self):
        name = self.cleaned_data['name']
        name_lower = name.lower()
        duplicates = Room.objects.filter(name__iexact=name_lower)
        if duplicates.exists():
            raise ValidationError('Комната с таким именем уже существует')
        return name

    def clean(self):
        cleaned_data = super().clean()
        is_private = cleaned_data.get('is_private')
        password = cleaned_data.get('password')
        if is_private and not password:
            self.add_error('password', 'У приватной комнаты  должен быть пароль!')
        return cleaned_data