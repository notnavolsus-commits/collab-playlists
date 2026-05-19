from django import forms


class TrackForm(forms.Form):
    title = forms.CharField(label='Title', max_length=200)
    artist = forms.CharField(label='Artist', max_length=200)
    audio_file = forms.FileField(required=False)

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
