# AgynServis

AgynServis - это веб-приложение для управления услугами и документами, разработанное на Django.

## Требования

- Python 3.10+
- Redis
- Django 5.0+
- Channels
- uWSGI
- Nginx

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd AgynServis
```

2. Создайте и активируйте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
# или
venv\Scripts\activate  # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Установите Redis:
```bash
# Для Ubuntu/Debian
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

5. Примените миграции:
```bash
python manage.py migrate
```

6. Создайте суперпользователя:
```bash
python manage.py createsuperuser
```

7. Соберите статические файлы:
```bash
python manage.py collectstatic
```

## Запуск

### Локальная разработка

```bash
python manage.py runserver
```

### Продакшн

1. Настройте uWSGI:
```bash
uwsgi --ini myapp.ini
```

2. Настройте Nginx для проксирования запросов к uWSGI.

## Структура проекта

- `AgynServis/` - основной проект Django
- `MainPage/` - приложение для главной страницы и услуг
- `users/` - приложение для управления пользователями и документами
- `templates/` - HTML шаблоны
- `static/` - статические файлы (CSS, JS, изображения)
- `media/` - загруженные пользователями файлы

## Функциональность

- Аутентификация и авторизация пользователей
- Управление профилем пользователя
- Загрузка и управление документами
- Редактирование документов в реальном времени
- Управление услугами
- Административная панель

## API Endpoints

- `/users/login/` - страница входа
- `/users/register/` - регистрация
- `/users/profile/` - профиль пользователя
- `/users/profile/edit/` - редактирование профиля
- `/users/documents/` - управление документами
- `/services/` - список услуг
- `/about/` - информация о компании
- `/contacts/` - контактная информация

## Разработка

### Создание миграций

```bash
python manage.py makemigrations
python manage.py migrate
```

### Запуск тестов

```bash
python manage.py test
```

## Лицензия

[Укажите вашу лицензию]

## Контакты

[Ваши контактные данные] 