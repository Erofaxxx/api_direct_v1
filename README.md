# Yandex Direct API Client

Python-клиент для работы с API Яндекс Директа v5.

## Возможности

- Получение данных о кампаниях, группах объявлений, ключевых фразах
- Выгрузка статистики через Reports API
- Управление ставками
- Автоматическое соблюдение rate limits (5 req/sec)
- Повторные попытки при временных ошибках
- Экспорт данных для ML анализа

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

1. Скопируйте файл `.env.example` в `.env`:
```bash
cp .env.example .env
```

2. Заполните переменные окружения:
```
YANDEX_DIRECT_TOKEN=ваш_oauth_токен
YANDEX_CLIENT_LOGIN=логин_клиента  # опционально, для агентств
YANDEX_API_MODE=sandbox  # или production
```

## Использование

### Ежедневная выгрузка данных

```python
from yandex_direct_api.app import YandexDirectApp

with YandexDirectApp() as app:
    results = app.run_daily_export()
    print(f"Кампаний: {len(results['campaigns'])}")
```

### Получение статистики

```python
from yandex_direct_api.client import YandexDirectClient

client = YandexDirectClient()
campaigns = client.get_campaigns()
```

### Запуск по расписанию

```bash
python -m examples.scheduled_runner
```

Или через cron:
```
0 3 * * * /path/to/python -m examples.daily_export
```

## Структура проекта

```
yandex_direct_api/
├── __init__.py
├── config.py          # Конфигурация API
├── client.py          # Основной клиент API
├── app.py             # Главное приложение
├── services/
│   └── reports.py     # Reports API
├── models/
│   └── __init__.py
└── utils/
    ├── errors.py      # Обработка ошибок
    └── rate_limiter.py # Rate limiting

examples/
├── daily_export.py    # Ежедневная выгрузка
├── scheduled_runner.py # Запуск по расписанию
└── ml_integration.py  # Интеграция с ML

docs/
└── API_APPLICATION.md # Документация для заявки
```

## Документация для заявки на API

Файл `docs/API_APPLICATION.md` содержит полное описание приложения для подачи заявки на доступ к API Яндекс Директа:

- Используемые методы API
- Схема вызовов
- Частота обращений
- Обработка ошибок
- Учет ограничений API

## Лицензия

MIT
