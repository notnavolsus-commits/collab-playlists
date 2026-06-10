from django import forms
from PIL import Image

from rooms.models import RoomTrack
from .models import Track

class TrackForm(forms.Form):
    OPERATION_CHOICES = [
        ('new', 'Загрузить новый трек'),
        ('existing', 'Выбрать из библиотеки'),
    ]

    operation_type = forms.ChoiceField(
        choices=OPERATION_CHOICES,
        widget=forms.RadioSelect,
        initial='new',
        label='Как предпочитаете добавить трек?'
    )

    existing_track = forms.ModelChoiceField(
        queryset=Track.objects.none(),
        required=False,
        label='Трек из библиотеки',
        empty_label='-----Выберите трек-----',
        widget=forms.Select(attrs={'style': 'trackform-track-select'})
    )

    title = forms.CharField(label='Название', max_length=200, required=False)
    artist = forms.CharField(label='Исполнитель', max_length=200, required=False)
    audio_file = forms.FileField(required=False)
    cover_url = forms.URLField(label='Ссылка на обложку', required=False)
    cover_image = forms.ImageField(label='Файл обложки', required=False)

    def __init__(self, *args, **kwargs):
        room = kwargs.pop('room', None)
        self._room = room
        super().__init__(*args, **kwargs)

        if room:
            existing_track_ids = RoomTrack.objects.filter(room=room).values_list('track_id', flat=True)
            self.fields['existing_track'].queryset = Track.objects.exclude(id__in=existing_track_ids).order_by('id', 'title')
            available_count = self.fields['existing_track'].queryset.count()
            if available_count == 0:
                self.fields['existing_track'].widget.attrs['disabled'] = 'disabled'
                self.fields['existing_track'].help_text = "Нет доступных треков для добавления в эту комнату"
            else:
                self.fields['existing_track'].help_text = f'Доступно треков: {available_count}'
        else:
            self.fields['existing_track'].queryset = Track.objects.all().order_by('artist', 'title')

    def clean_audio_file(self):
        audio_file = self.cleaned_data['audio_file']
        if not audio_file:
            return audio_file
        if not audio_file.name.endswith('.mp3'):
            raise forms.ValidationError("Файл должен иметь расширение mp3")
        max_size = 15 * 1024 * 1024
        if audio_file.size > max_size:
            raise forms.ValidationError(f"Файл должен быть не больше: {max_size / (1024 * 1024)} MB")
        return audio_file

    @staticmethod
    def validate_cover_image(cover_image):
        allowed_extensions = ['jpg', 'jpeg', 'png', 'webp']
        ext = cover_image.name.split('.')[-1].lower()
        if ext not in allowed_extensions:
            raise forms.ValidationError(
                f'Неподдерживаемый формат. Изображение должно быть в одном из следующих форматов: {', '.join(allowed_extensions)}')
        max_size = 2 * 1024 * 1024
        if cover_image.size > max_size:
            raise forms.ValidationError(f"Файл должен быть не больше: {max_size / (1024 * 1024)} MB")
        # Проверка содержимого
        try:
            image = Image.open(cover_image)
            image.verify()

            # Переоткрываем для дополнительных проверок
            cover_image.seek(0)
            image = Image.open(cover_image)

            max_dimension = 4000
            if image.width > max_dimension or image.height > max_dimension:
                raise forms.ValidationError(f'Изображение слишком большое. Максимальный размер: {max_dimension}')

            aspect_ratio = image.width / image.height
            if aspect_ratio > 2 or aspect_ratio < 0.5:
                raise forms.ValidationError('Изображение слишком вытянутое')
        except Exception as e:
            raise forms.ValidationError(f'Невалидное изображение: {str(e)}')

    def clean(self):
        cleaned_data = super().clean()
        operation_type = cleaned_data.get('operation_type')
        if operation_type == 'existing':
            existing_track = cleaned_data.get('existing_track')
            if not existing_track:
                raise forms.ValidationError('Пожалуйста выберите трек из существующих')
        else:
            title = cleaned_data.get('title')
            artist = cleaned_data.get('artist')
            audio_file = cleaned_data.get('audio_file')
            errors = []
            if not title:
                errors.append('название')
            if not artist:
                errors.append('исполнителя')
            if errors:
                raise forms.ValidationError(f'Для нового трека необходимо добавить {", ".join(errors)}')
            cover_image, cover_url = cleaned_data.get('cover_image'), cleaned_data.get('cover_url')
            if not cover_image and not cover_url:
                raise forms.ValidationError("Нужно указать URL или вставить файл")
            if cover_image:
                self.validate_cover_image(cover_image)
        return cleaned_data


