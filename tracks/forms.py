from django import forms
from PIL import Image

class TrackForm(forms.Form):
    title = forms.CharField(label='Название', max_length=200)
    artist = forms.CharField(label='Исполнитель', max_length=200)
    audio_file = forms.FileField(required=False)
    cover_url = forms.URLField(label='Ссылка на обложку', required=False)
    cover_image = forms.ImageField(label='Файл обложки', required=False)

    def clean_audio_file(self):
        audio_file = self.cleaned_data['audio_file']
        if not audio_file:
            return audio_file
        if not audio_file.name.endswith('.mp3'):
            raise forms.ValidationError("Файл должен иметь расширение mp3")
        max_size = 10 * 1024 * 1024
        if audio_file.size > max_size:
            raise forms.ValidationError(f"Файл должен быть не больше: {max_size / (1024 * 1024)} MB")
        return audio_file

    def clean(self):
        cover_image, cover_url = self.cleaned_data['cover_image'], self.cleaned_data['cover_url']
        if not cover_image and not cover_url:
            raise forms.ValidationError("Нужно указать URL или вставить файл")
        if cover_image:
            allowed_extensions = ['jpg', 'jpeg', 'png', 'webp']
            ext = cover_image.name.split('.')[-1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError(f'Неподдерживаемый формат. Изображение должно быть в одном из следующих форматов: {', '.join(allowed_extensions)}')
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


