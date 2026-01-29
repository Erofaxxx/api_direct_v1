# Мультиагентная система Яндекс Директ + ML

Мультиагентная система для автоматизации работы с Яндекс Директом и ML-анализа рекламных данных.

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                            │
│                   (Координатор агентов)                      │
└─────────────────────┬───────────────────┬───────────────────┘
                      │                   │
          ┌───────────▼───────┐ ┌─────────▼─────────┐
          │  DirectAgent      │ │   MLAnalystAgent  │
          │  (Яндекс Директ)  │ │   (Claude API)    │
          └───────────────────┘ └───────────────────┘
                      │                   │
                      ▼                   ▼
              ┌───────────────────────────────────────┐
              │            SHARED DATA                 │
              │         (Files / Database)             │
              └───────────────────────────────────────┘
```

## Агенты

### DirectAgent
- Получение данных из API Яндекс Директа
- Выгрузка статистики по кампаниям и ключевым фразам
- Обновление ставок по рекомендациям ML агента

### MLAnalystAgent
- Анализ данных с помощью Claude Sonnet 4.5 (через OpenRouter)
- Генерация рекомендаций по ставкам
- Выявление аномалий и трендов
- Слияние данных с CRM

## Быстрый старт

### 1. Клонирование и установка

```bash
git clone <repo-url>
cd api_direct_v1

# Создание виртуального окружения
python3.11 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Конфигурация

```bash
cp .env.example .env
nano .env
```

Заполните:
```env
# Яндекс Директ
YANDEX_DIRECT_TOKEN=ваш_токен

# OpenRouter (Claude API)
OPENROUTER_API_KEY=ваш_ключ_openrouter
```

### 3. Запуск

```bash
# Запуск ежедневного пайплайна
python -m orchestrator.main

# Запуск планировщика (работает в фоне)
python -m deploy.scheduler
```

## Деплой на Ubuntu Server

### Вариант 1: Скрипт установки

```bash
cd deploy
chmod +x install.sh
sudo ./install.sh
```

### Вариант 2: Docker

```bash
# Сборка и запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f agent-orchestrator
```

### Вариант 3: Systemd

```bash
# Копирование сервиса
sudo cp deploy/yandex-direct-agent.service /etc/systemd/system/

# Запуск
sudo systemctl daemon-reload
sudo systemctl enable yandex-direct-agent
sudo systemctl start yandex-direct-agent
```

## Расписание задач

| Время | Задача | Описание |
|-------|--------|----------|
| 03:00 | daily_pipeline | Полная выгрузка + анализ |
| 10:00 (пн-пт) | recommendations | Генерация рекомендаций |
| 12:00 | anomaly_check | Проверка аномалий |

## Структура проекта

```
api_direct_v1/
├── agents/                    # Агенты системы
│   ├── base.py               # Базовый класс агента
│   ├── direct_agent.py       # Агент Яндекс Директа
│   └── ml_agent.py           # ML агент (Claude API)
│
├── orchestrator/              # Оркестратор
│   └── main.py               # Координация агентов
│
├── yandex_direct_api/         # API клиент Яндекс Директа
│   ├── client.py             # HTTP клиент
│   ├── config.py             # Конфигурация
│   ├── services/
│   │   └── reports.py        # Reports API
│   └── utils/
│       ├── errors.py         # Обработка ошибок
│       └── rate_limiter.py   # Rate limiting
│
├── deploy/                    # Деплой
│   ├── install.sh            # Скрипт установки
│   ├── scheduler.py          # Планировщик
│   └── *.service             # Systemd сервисы
│
├── docs/                      # Документация
│   ├── API_APPLICATION.md    # Для заявки на API
│   └── YANDEX_APPLICATION_ANSWERS.txt
│
├── docker-compose.yml         # Docker конфигурация
├── Dockerfile
└── requirements.txt
```

## API Endpoints

### Яндекс Директ (используемые методы)

| Метод | Описание | Частота |
|-------|----------|---------|
| Campaigns.get | Список кампаний | 1 раз/сутки |
| AdGroups.get | Группы объявлений | 1 раз/сутки |
| Keywords.get | Ключевые фразы | 1 раз/сутки |
| Bids.set | Установка ставок | По запросу |
| Reports API | Статистика | 1 раз/сутки |

### Claude API (через OpenRouter)

- Модель: `anthropic/claude-sonnet-4`
- Endpoint: `https://openrouter.ai/api/v1/chat/completions`

## Примеры использования

### Запуск анализа

```python
import asyncio
from orchestrator.main import Orchestrator

async def main():
    orch = Orchestrator()
    await orch.start()

    # Полный пайплайн
    results = await orch.run_daily_pipeline()

    # Только анализ
    analysis = await orch.run_analysis("general")

    # Оптимизация ставок
    bids = await orch.run_bid_optimization(auto_apply=False)

    await orch.stop()

asyncio.run(main())
```

### Работа с агентами напрямую

```python
from agents import DirectAgent, MLAnalystAgent

# Яндекс Директ
direct = DirectAgent(token="your_token")
result = await direct.execute_task({"type": "full_export"})

# ML анализ
ml = MLAnalystAgent(api_key="your_openrouter_key")
analysis = await ml.execute_task({"type": "analyze"})
```

## Получение API ключей

### Яндекс Директ
1. Зарегистрируйте приложение: https://oauth.yandex.ru/
2. Получите токен через OAuth
3. Подайте заявку на полный доступ к API

### OpenRouter (Claude API)
1. Зарегистрируйтесь: https://openrouter.ai/
2. Создайте API ключ: https://openrouter.ai/keys
3. Пополните баланс для использования Claude

## Документация для заявки на API Яндекса

Файл `docs/YANDEX_APPLICATION_ANSWERS.txt` содержит подробные ответы для заявки:
- Названия методов API
- Схема вызовов
- Частота обращений
- Обработка ошибок
- Учёт ограничений

## Лицензия

MIT
