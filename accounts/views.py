from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm, CustomAuthenticationForm


def register(request):
    """Регистрация нового пользователя"""
    if request.user.is_authenticated:
        return redirect('rooms_list')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Автоматически входим после регистрации
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}! Регистрация успешно завершена.')
            return redirect('rooms_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CustomUserCreationForm()

    return render(request, 'register.html', {'form': form})


def user_login(request):
    """Вход пользователя"""
    if request.user.is_authenticated:
        return redirect('rooms_list')

    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'С возвращением, {username}!')

                # Перенаправляем на страницу, с которой пришли, если она есть
                next_page = request.GET.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect('rooms_list')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')
    else:
        form = CustomAuthenticationForm()

    return render(request, 'login.html', {'form': form})


@login_required
def user_logout(request):
    """Выход пользователя"""
    logout(request)
    messages.info(request, 'Вы вышли из системы')
    return redirect('rooms_list')


@login_required
def profile(request):
    """Профиль пользователя"""
    return render(request, 'profile.html', {'user': request.user})
