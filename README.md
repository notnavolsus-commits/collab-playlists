# 🎵 Collab Playlist

Совместный музыкальный плеер с синхронизацией воспроизведения, чатом и голосованием за треки.

## 📋 Требования

- Python 3.10+
- Redis 7+
- SQLite

## 🚀 Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/yourusername/collab_playlist.git
cd collab_playlist
```

### 2. Создание виртуального окружения
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB_CHAT=1
REDIS_DB_BROADCAST=2
```

### 5. Миграции
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Сбор статических файлов
```bash
python manage.py collectstatic
```
### 7. Создание суперпользователя
```bash
python manage.py createsuperuser
```
### 8. Запуск Redis (необходим для WebSockets)
```bash
# Windows (через WSL или скачав Redis)
redis-server

# Linux/Mac
sudo service redis start
```
### 9. Запуск сервера
```bash
# Для разработки с Daphne (WebSocket поддержка)
daphne -b 0.0.0.0 -p 8000 collab_playlist.asgi:application

# Или через runserver (без продакшен-рекомендаций)
python manage.py runserver
```

## Структура проекта
```text
collab_playlist/
├── accounts/              # Приложение для аутентификации
│   ├── models.py         # Profile модель для аватаров
│   ├── views.py          # Регистрация, логин, профиль
│   └── forms.py          # Формы регистрации
├── collab_playlist/      # Основная конфигурация
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py          # ASGI конфигурация для WebSockets
├── media/               # Загруженные файлы (треки, аватары)
│   ├── avatars/
│   ├── covers/
│   └── tracks/
├── rooms/                # Основное приложение
│   ├── models.py        # Room, RoomTrack, Vote, ChatMessage
│   ├── consumers.py     # WebSocket обработчики
│   ├── routing.py
│   ├── forms.py
│   ├── views.py
│   └── static/rooms/    # Статические файлы
├── tracks/
│   ├── models.py
│   └── views.py
├── templates/           # Шаблоны
└── manage.py
```

# 🎮 Использование
## Создание комнаты
Зарегистрируйтесь или войдите

Нажмите ***"Создать комнату"***

Задайте название и (опционально) пароль

## Добавление треков
В комнате прокрутите вниз до формы ***"Добавить трек"***

Заполните название, исполнителя

Загрузите MP3 файл и (опционально) обложку

## Управление эфиром (только для создателя)
▶️ Запустить эфир — нажмите ***"Запустить эфир"*** у трека

⏸️ Пауза — приостановить воспроизведение

▶️ Возобновить — продолжить с того же места

⏹️ Остановить — полностью остановить трансляцию

## Голосование
Нажмите ***"Голосовать"*** у трека

Треки с большим количеством голосов поднимаются вверх

## Чат
Пишите сообщения в поле внизу страницы

Сообщения сохраняются в историю