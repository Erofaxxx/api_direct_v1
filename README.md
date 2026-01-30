# Мультиагентная система Яндекс Директ + ML Analytics

Полноценная мультиагентная система для анализа рекламных данных с AI (Claude Sonnet 4.5).

## Возможности

- **AI анализ данных** — Claude Sonnet 4.5 через OpenRouter
- **Большие таблицы** — работа с таблицами любого размера (chunking)
- **Текстовые данные** — классификация городов, категорий и других текстовых полей
- **PDF отчёты** — профессиональные отчёты с графиками (LaTeX)
- **REST API** — интеграция с любым фронтендом
- **AI чат** — вопросы по данным в свободной форме

## Быстрый старт

### Установка на Ubuntu

```bash
git clone https://github.com/your-repo/api_direct_v1.git
cd api_direct_v1/deploy
chmod +x install.sh
sudo ./install.sh
```

### Docker

```bash
docker-compose up -d
```

### Локальный запуск

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Отредактируйте .env

# Запуск API
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/status` | Статус системы |
| POST | `/api/upload` | Загрузка файла |
| POST | `/api/analyze` | Запуск анализа |
| GET | `/api/task/{id}` | Статус задачи |
| POST | `/api/chat` | Чат с AI |
| POST | `/api/report` | Генерация PDF |
| GET | `/api/report/{id}/download` | Скачать PDF |

**Swagger документация:** http://your-server/docs

## Интеграция с фронтендом (Lovable)

Промпт для создания интерфейса: [`docs/LOVABLE_PROMPT.md`](docs/LOVABLE_PROMPT.md)

```javascript
// Пример использования API
const response = await fetch('http://your-server/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: 'Какие города показывают лучший ROI?',
    data_id: 'uuid-загруженных-данных'
  })
});
const { response: aiAnswer } = await response.json();
```

## Архитектура

```
┌─────────────────────────────────────────────────┐
│              REST API (FastAPI)                  │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│                 ORCHESTRATOR                     │
└─────────────────────┬───────────────────────────┘
          ┌───────────┴───────────┐
          ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  DirectAgent    │     │  MLAnalystAgent │
│ (Яндекс Директ) │     │  (Claude API)   │
└─────────────────┘     └─────────────────┘
```

## Структура проекта

```
api_direct_v1/
├── api/                    # REST API (FastAPI)
│   └── main.py
├── agents/                 # Агенты
│   ├── direct_agent.py     # Яндекс Директ
│   └── ml_agent.py         # Claude AI
├── ml_analysis/            # Анализ данных
│   └── data_analyzer.py    # Большие таблицы, классификация
├── reports/                # Генерация отчётов
│   └── pdf_generator.py    # LaTeX → PDF
├── orchestrator/           # Координатор
├── deploy/                 # Деплой
│   └── install.sh          # Установка Ubuntu
├── docs/                   # Документация
│   ├── FULL_DOCUMENTATION.md
│   ├── LOVABLE_PROMPT.md
│   └── YANDEX_APPLICATION_ANSWERS.txt
└── docker-compose.yml
```

## Настройка

```env
# .env
YANDEX_DIRECT_TOKEN=your_token
OPENROUTER_API_KEY=your_key
CLAUDE_MODEL=anthropic/claude-sonnet-4
```

## Документация

- [Полная документация](docs/FULL_DOCUMENTATION.md)
- [Промпт для Lovable](docs/LOVABLE_PROMPT.md)
- [Заявка на API Яндекса](docs/YANDEX_APPLICATION_ANSWERS.txt)
- [Swagger API](http://your-server/docs)

## Лицензия

MIT
