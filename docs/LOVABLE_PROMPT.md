# Промпт для Lovable: Создание интерфейса AI Analytics

Скопируйте этот промпт в Lovable для создания веб-интерфейса к вашему API.

---

## ПРОМПТ ДЛЯ LOVABLE

```
Создай современное веб-приложение для анализа рекламных данных с AI.

## Описание проекта

Приложение для анализа данных Яндекс Директа с использованием AI (Claude).
Пользователи загружают CSV/Excel файлы, получают AI анализ и PDF отчёты.

## API Backend

Backend уже готов и работает по адресу: {YOUR_API_URL}

API Endpoints:
- GET /api/status - статус системы
- POST /api/upload - загрузка файла (multipart/form-data)
- POST /api/analyze - запуск анализа
- GET /api/task/{task_id} - статус задачи
- POST /api/chat - чат с AI
- POST /api/report - генерация PDF
- GET /api/report/{task_id}/download - скачивание PDF
- GET /api/data/{data_id}/preview - предпросмотр данных

## Требования к интерфейсу

### 1. Главная страница (Dashboard)
- Красивый hero section с описанием сервиса
- Статистика: количество загруженных файлов, анализов, отчётов
- Быстрые действия: "Загрузить данные", "Начать анализ"
- Последние загруженные файлы

### 2. Страница загрузки данных
- Drag & drop зона для файлов
- Поддержка CSV, Excel, JSON
- Отображение прогресса загрузки
- После загрузки показать:
  - Количество строк и столбцов
  - Типы столбцов (числовые, категории, города)
  - Превью первых 10 строк таблицы
- Кнопка "Запустить анализ"

### 3. Страница анализа
- Выбор типа анализа:
  - Общий анализ
  - Поиск аномалий
  - Анализ трендов
  - Рекомендации по ставкам
- Прогресс-бар выполнения (polling /api/task/{id})
- Результаты анализа:
  - Ключевые выводы (карточки)
  - Графики (если есть)
  - Таблицы с данными
- Кнопка "Сгенерировать отчёт"

### 4. AI Чат
- Интерфейс чата как в ChatGPT
- Возможность задавать вопросы по загруженным данным
- Предложения быстрых вопросов (suggestions)
- История сообщений
- Индикатор набора ответа

### 5. Страница отчётов
- Список сгенерированных отчётов
- Статус генерации (в процессе / готов)
- Кнопка скачивания PDF
- Предпросмотр содержимого

### 6. Настройки
- Конфигурация API URL
- Тема (светлая/тёмная)

## Технические требования

### Стек
- React + TypeScript
- Tailwind CSS
- shadcn/ui компоненты
- React Query для API запросов
- Zustand или Context для состояния

### API интеграция

Создай сервис для работы с API:

```typescript
// services/api.ts
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export const api = {
  // Статус
  async getStatus() {
    const res = await fetch(`${API_URL}/status`);
    return res.json();
  },

  // Загрузка файла
  async uploadFile(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_URL}/upload`, {
      method: 'POST',
      body: formData,
    });
    return res.json();
  },

  // Анализ
  async analyze(dataId: string, type: string) {
    const res = await fetch(`${API_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data_id: dataId, analysis_type: type }),
    });
    return res.json();
  },

  // Статус задачи
  async getTaskStatus(taskId: string) {
    const res = await fetch(`${API_URL}/task/${taskId}`);
    return res.json();
  },

  // Чат
  async chat(message: string, dataId?: string, history: any[] = []) {
    const res = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, data_id: dataId, history }),
    });
    return res.json();
  },

  // Генерация отчёта
  async generateReport(dataId: string, title: string) {
    const res = await fetch(`${API_URL}/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        data_id: dataId,
        title,
        include_charts: true,
      }),
    });
    return res.json();
  },

  // URL для скачивания отчёта
  getReportDownloadUrl(taskId: string) {
    return `${API_URL}/report/${taskId}/download`;
  },
};
```

### Polling для задач

```typescript
// hooks/useTaskPolling.ts
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

export function useTaskPolling(taskId: string | null) {
  return useQuery({
    queryKey: ['task', taskId],
    queryFn: () => api.getTaskStatus(taskId!),
    enabled: !!taskId,
    refetchInterval: (data) => {
      if (data?.status === 'completed' || data?.status === 'failed') {
        return false;
      }
      return 2000; // Poll every 2 seconds
    },
  });
}
```

## Дизайн

- Минималистичный современный дизайн
- Основные цвета: синий (#2563eb) и белый
- Акцентный цвет: зелёный для успеха (#22c55e)
- Тёмная тема с тёмно-серым фоном (#1f2937)
- Анимации при загрузке и переходах
- Адаптивный дизайн (mobile-first)

## Структура страниц

```
/                 - Dashboard
/upload           - Загрузка файлов
/analyze/:dataId  - Страница анализа
/chat             - AI чат
/reports          - Список отчётов
/settings         - Настройки
```

## Дополнительно

- Добавь toast уведомления для успешных/ошибочных операций
- Добавь skeleton loading состояния
- Добавь empty states для пустых списков
- Сохраняй историю чата в localStorage
- Добавь возможность экспорта результатов в CSV
```

---

## Как использовать

1. Откройте https://lovable.dev/
2. Создайте новый проект
3. Вставьте промпт выше
4. Замените `{YOUR_API_URL}` на адрес вашего API сервера
5. Lovable сгенерирует код
6. Настройте переменную окружения `VITE_API_URL`

---

## Переменные окружения для Lovable проекта

Создайте файл `.env` в сгенерированном проекте:

```env
VITE_API_URL=http://your-server.com/api
```

---

## Примеры компонентов

### FileUpload компонент

```tsx
import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileSpreadsheet } from 'lucide-react';
import { api } from '@/services/api';

export function FileUpload({ onUploadComplete }) {
  const [uploading, setUploading] = useState(false);

  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;

    setUploading(true);
    try {
      const result = await api.uploadFile(file);
      onUploadComplete(result);
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setUploading(false);
    }
  }, [onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/json': ['.json'],
    },
    maxFiles: 1,
  });

  return (
    <div
      {...getRootProps()}
      className={`
        border-2 border-dashed rounded-xl p-12 text-center cursor-pointer
        transition-colors duration-200
        ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
        ${uploading ? 'opacity-50 pointer-events-none' : ''}
      `}
    >
      <input {...getInputProps()} />
      <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
      {isDragActive ? (
        <p className="text-blue-600 font-medium">Отпустите файл здесь</p>
      ) : (
        <>
          <p className="text-gray-600 mb-2">
            Перетащите файл сюда или кликните для выбора
          </p>
          <p className="text-sm text-gray-400">
            Поддерживаются CSV, Excel, JSON
          </p>
        </>
      )}
    </div>
  );
}
```

### ChatInterface компонент

```tsx
import { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';
import { api } from '@/services/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export function ChatInterface({ dataId }: { dataId?: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await api.chat(
        input,
        dataId,
        messages.map(m => ({ role: m.role, content: m.content }))
      );

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.response,
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Chat error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[600px] bg-white rounded-xl shadow-lg">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl px-4 py-2">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100" />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t p-4">
        <div className="flex space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Задайте вопрос по данным..."
            className="flex-1 px-4 py-2 border rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-full hover:bg-blue-700 disabled:opacity-50"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## После генерации

1. Скачайте проект из Lovable
2. Установите зависимости: `npm install`
3. Создайте `.env` с URL вашего API
4. Запустите: `npm run dev`
5. Деплой на Vercel/Netlify
