# Интернет-магазин электроники на Flask (NanoWave)

Полнофункциональное веб-приложение интернет-магазина электроники на Python/Flask с SQLite, авторизацией, корзиной, заказами, административной панелью и логированием.

## Возможности

- Каталог товаров с поиском и фильтрацией по категориям
- Карточка товара с добавлением в корзину
- Регистрация, вход и выход пользователей
- Профиль пользователя с историей заказов
- Корзина: добавление, изменение количества, удаление
- Оформление заказа с созданием записей в `orders` и `order_items`
- Административная панель:
  - просмотр/добавление/редактирование/удаление товаров
  - просмотр пользователей
  - просмотр заказов
- Логирование ключевых действий в `logs/app.log`

## Технологии

- Python 3
- Flask
- sqlite3
- Flask-Login
- Flask-WTF
- Jinja2
- Bootstrap 5
- logging
- Werkzeug Security

## Структура проекта

```
project/
├── app/
│   ├── forms/
│   │   ├── __init__.py
│   │   ├── login_form.py
│   │   ├── register_form.py
│   │   └── product_form.py
│   ├── templates/
│   │   ├── admin/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── catalog.html
│   │   ├── product.html
│   │   ├── cart.html
│   │   ├── login.html
│   │   ├── register.html
│   │   └── profile.html
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   ├── images/
│   │   └── uploads/
│   ├── __init__.py
│   ├── config.py
│   └── routes.py
├── database/
│   └── shop.db
├── logs/
│   └── app.log
├── run.py
├── requirements.txt
└── README.md
```

## Быстрый старт

1. Создать и активировать виртуальное окружение:
   - Windows PowerShell:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Установить зависимости:
   ```powershell
   pip install -r requirements.txt
   ```

3. Запустить приложение:
   ```powershell
   python run.py
   ```

4. Открыть в браузере:
   - [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Тестовый администратор

Создается автоматически при первом запуске:

- Email: `admin@example.com`
- Пароль: `admin123`

## Безопасность

- Пароли хешируются через `werkzeug.security.generate_password_hash`
- Защищенные маршруты через `Flask-Login`
- Проверка роли администратора для доступа к админ-панели
- Формы на `Flask-WTF` с CSRF-защитой

## Логирование

Логируются:

- регистрация пользователей
- вход/выход пользователей
- оформление заказов
- действия администратора с товарами
- системные события запуска

Файл логов: `logs/app.log`
