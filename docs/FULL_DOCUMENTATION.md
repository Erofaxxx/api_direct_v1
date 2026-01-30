# Полная документация: Мультиагентная система Яндекс Директ + ML Analytics

## Оглавление

1. [Обзор системы](#обзор-системы)
2. [Архитектура](#архитектура)
3. [Установка на Ubuntu Server](#установка-на-ubuntu-server)
4. [Настройка](#настройка)
5. [API Reference](#api-reference)
6. [Интеграция с фронтендом](#интеграция-с-фронтендом)
7. [Использование](#использование)
8. [Troubleshooting](#troubleshooting)

---

## Обзор системы

Мультиагентная система для анализа рекламных данных Яндекс Директа с использованием AI (Claude Sonnet 4.5).

### Возможности

- **Автоматический сбор данных** из Яндекс Директа
- **ML анализ** больших таблиц с текстовыми данными (города, категории)
- **Генерация PDF отчётов** с графиками и таблицами (LaTeX)
- **REST API** для интеграции с веб-интерфейсом
- **AI чат-бот** для ответов на вопросы по данным

### Компоненты

| Компонент | Описание |
|-----------|----------|
| DirectAgent | Получение данных из Яндекс Директа |
| MLAnalystAgent | Анализ данных с Claude API |
| DataAnalyzer | Обработка больших таблиц |
| PDFGenerator | Генерация PDF отчётов |
| REST API | Интерфейс для фронтенда |

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Lovable)                       │
│                    React/TypeScript Web App                      │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         REST API (FastAPI)                       │
│                    http://your-server/api/*                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ /upload  │  │ /analyze │  │  /chat   │  │ /report          │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                        ORCHESTRATOR                              │
│                   Координация агентов                            │
└─────────────────────┬───────────────────┬───────────────────────┘
                      │                   │
          ┌───────────▼───────┐ ┌─────────▼─────────┐
          │   DirectAgent     │ │   MLAnalystAgent  │
          │ (Яндекс Директ)   │ │  (Claude API)     │
          └───────────────────┘ └───────────────────┘
                      │                   │
                      ▼                   ▼
          ┌───────────────────┐ ┌───────────────────┐
          │  Yandex Direct    │ │    OpenRouter     │
          │      API          │ │  (Claude Sonnet)  │
          └───────────────────┘ └───────────────────┘
```

---

## Установка на Ubuntu Server

### Требования

- Ubuntu 20.04+ / 22.04 LTS
- Python 3.11+
- 2GB RAM минимум
- 10GB диска

### Автоматическая установка

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/your-repo/api_direct_v1.git
cd api_direct_v1

# 2. Запустите скрипт установки
cd deploy
chmod +x install.sh
sudo ./install.sh
```

### Ручная установка

```bash
# Системные зависимости
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip \
    nginx supervisor \
    texlive-latex-base texlive-latex-extra texlive-lang-cyrillic

# Создание окружения
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Настройка .env
cp .env.example .env
nano .env  # Добавьте API ключи

# Запуск API сервера
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Docker установка

```bash
# Сборка и запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f
```

---

## Настройка

### Файл .env

```env
# Яндекс Директ API
YANDEX_DIRECT_TOKEN=AgAAAA...      # OAuth токен
YANDEX_CLIENT_LOGIN=               # Для агентств
YANDEX_API_MODE=production         # production/sandbox

# OpenRouter API (Claude)
OPENROUTER_API_KEY=sk-or-v1-...    # Ключ OpenRouter
CLAUDE_MODEL=anthropic/claude-sonnet-4

# API сервер
API_HOST=0.0.0.0
API_PORT=8000

# Данные
DATA_DIR=/var/lib/yandex-direct-agent/data
LOG_LEVEL=INFO
```

### Получение API ключей

#### Яндекс Директ

1. Перейдите на https://oauth.yandex.ru/
2. Создайте приложение
3. Получите OAuth токен
4. Подайте заявку на полный доступ к API

#### OpenRouter (Claude)

1. Зарегистрируйтесь на https://openrouter.ai/
2. Создайте API ключ: https://openrouter.ai/keys
3. Пополните баланс (Claude платный)

---

## API Reference

### Базовый URL

```
http://your-server.com/api
```

### Endpoints

#### GET /api/status

Статус системы.

**Ответ:**
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00",
  "active_tasks": 2,
  "loaded_datasets": 3,
  "ml_agent_ready": true
}
```

#### POST /api/upload

Загрузка файла данных.

**Запрос:** `multipart/form-data`
- `file`: CSV, Excel или JSON файл

**Ответ:**
```json
{
  "data_id": "uuid-string",
  "filename": "sales_data.csv",
  "rows": 15000,
  "columns": 25,
  "column_info": {
    "city": {"type": "city", "unique_count": 150},
    "revenue": {"type": "numeric", "statistics": {...}}
  }
}
```

#### POST /api/analyze

Запуск анализа данных.

**Запрос:**
```json
{
  "data_id": "uuid-string",
  "analysis_type": "general",  // general, anomaly, trends, recommendations
  "options": {}
}
```

**Ответ:**
```json
{
  "task_id": "uuid-string",
  "status": "pending"
}
```

#### GET /api/task/{task_id}

Статус задачи.

**Ответ:**
```json
{
  "task_id": "uuid-string",
  "status": "completed",  // pending, running, completed, failed
  "progress": 100,
  "result": {
    "analysis": {...},
    "charts": ["path/to/chart1.png"]
  }
}
```

#### POST /api/chat

Чат с AI агентом.

**Запрос:**
```json
{
  "message": "Какие города показывают лучший ROI?",
  "data_id": "uuid-string",
  "history": []
}
```

**Ответ:**
```json
{
  "response": "На основе анализа данных, лучший ROI показывают...",
  "suggestions": ["Сгенерировать отчёт", "Показать график"],
  "charts": []
}
```

#### POST /api/report

Генерация PDF отчёта.

**Запрос:**
```json
{
  "data_id": "uuid-string",
  "title": "Месячный отчёт",
  "include_charts": true,
  "analysis_types": ["general", "recommendations"]
}
```

**Ответ:**
```json
{
  "task_id": "uuid-string",
  "status": "pending"
}
```

#### GET /api/report/{task_id}/download

Скачивание готового PDF отчёта.

**Ответ:** PDF файл

---

## Интеграция с фронтендом

### Пример на JavaScript

```javascript
const API_URL = 'http://your-server.com/api';

// Загрузка файла
async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_URL}/upload`, {
    method: 'POST',
    body: formData,
  });

  return response.json();
}

// Запуск анализа
async function analyzeData(dataId, type = 'general') {
  const response = await fetch(`${API_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      data_id: dataId,
      analysis_type: type,
    }),
  });

  return response.json();
}

// Проверка статуса задачи
async function checkTaskStatus(taskId) {
  const response = await fetch(`${API_URL}/task/${taskId}`);
  return response.json();
}

// Polling для ожидания результата
async function waitForResult(taskId, intervalMs = 2000) {
  while (true) {
    const status = await checkTaskStatus(taskId);

    if (status.status === 'completed') {
      return status.result;
    }

    if (status.status === 'failed') {
      throw new Error(status.error);
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
}

// Чат с AI
async function sendChatMessage(message, dataId, history = []) {
  const response = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      data_id: dataId,
      history,
    }),
  });

  return response.json();
}

// Генерация отчёта
async function generateReport(dataId, title) {
  const response = await fetch(`${API_URL}/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      data_id: dataId,
      title,
      include_charts: true,
    }),
  });

  const { task_id } = await response.json();
  await waitForResult(task_id);

  // Скачивание PDF
  window.open(`${API_URL}/report/${task_id}/download`);
}
```

### Пример React компонента

```jsx
import React, { useState } from 'react';

function DataAnalyzer() {
  const [dataId, setDataId] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    setLoading(true);

    const result = await uploadFile(file);
    setDataId(result.data_id);
    setLoading(false);
  };

  const handleAnalyze = async () => {
    setLoading(true);
    const { task_id } = await analyzeData(dataId);
    const result = await waitForResult(task_id);
    setAnalysis(result);
    setLoading(false);
  };

  return (
    <div>
      <input type="file" onChange={handleFileUpload} />

      {dataId && (
        <button onClick={handleAnalyze} disabled={loading}>
          {loading ? 'Анализ...' : 'Запустить анализ'}
        </button>
      )}

      {analysis && (
        <div>
          <h3>Результаты</h3>
          <pre>{JSON.stringify(analysis, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
```

---

## Использование

### Через API

```bash
# Проверка статуса
curl http://your-server/api/status

# Загрузка файла
curl -X POST http://your-server/api/upload \
  -F "file=@data.csv"

# Запуск анализа
curl -X POST http://your-server/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"data_id": "uuid", "analysis_type": "general"}'

# Чат с AI
curl -X POST http://your-server/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Анализируй данные", "data_id": "uuid"}'
```

### Через Python

```python
import asyncio
from orchestrator.main import Orchestrator

async def main():
    orch = Orchestrator()
    await orch.start()

    # Ежедневный пайплайн
    results = await orch.run_daily_pipeline()
    print(results)

    # Анализ
    analysis = await orch.run_analysis("general")
    print(analysis)

    await orch.stop()

asyncio.run(main())
```

---

## Troubleshooting

### API не отвечает

```bash
# Проверка статуса сервисов
sudo supervisorctl status

# Перезапуск
sudo supervisorctl restart yandex-direct:*

# Логи
tail -f /var/log/yandex-direct-agent/api.log
```

### Ошибки LaTeX

```bash
# Проверка установки
pdflatex --version

# Установка недостающих пакетов
sudo apt install texlive-full
```

### Ошибки Claude API

```bash
# Проверка ключа
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

### Ошибки Яндекс API

- Проверьте токен в .env
- Убедитесь, что заявка на API одобрена
- Проверьте режим (sandbox/production)

---

## Поддержка

- GitHub Issues: https://github.com/your-repo/issues
- Документация API: http://your-server/docs
