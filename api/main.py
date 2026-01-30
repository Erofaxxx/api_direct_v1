"""
REST API для мультиагентной системы.

Endpoints:
- POST /api/analyze - анализ данных
- POST /api/upload - загрузка файла для анализа
- POST /api/report - генерация PDF отчёта
- GET /api/status - статус системы
- POST /api/chat - чат с AI агентом

Для интеграции с Lovable (фронтенд).
"""

import asyncio
import io
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# Импорты модулей системы
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.ml_agent import MLAnalystAgent, OpenRouterClient
from ml_analysis.data_analyzer import DataAnalyzer, ChartGenerator
from reports.pdf_generator import PDFReportGenerator, ReportSection

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI приложение
app = FastAPI(
    title="Yandex Direct AI Analytics API",
    description="API для анализа рекламных данных с помощью AI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS для фронтенда (Lovable)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Хранилище задач (в продакшене используйте Redis)
tasks_storage: dict[str, dict] = {}
data_storage: dict[str, pd.DataFrame] = {}

# Глобальные компоненты
data_analyzer = DataAnalyzer()
chart_generator = ChartGenerator(output_dir="reports/charts")
pdf_generator = PDFReportGenerator(output_dir="reports/output")

# ML агент (ленивая инициализация)
ml_agent: MLAnalystAgent | None = None


def get_ml_agent() -> MLAnalystAgent:
    """Получение ML агента."""
    global ml_agent
    if ml_agent is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise HTTPException(500, "OPENROUTER_API_KEY не настроен")
        ml_agent = MLAnalystAgent(api_key=api_key)
    return ml_agent


# ============== Модели запросов/ответов ==============

class AnalyzeRequest(BaseModel):
    """Запрос на анализ данных."""
    data_id: str = Field(..., description="ID загруженных данных")
    analysis_type: str = Field(
        default="general",
        description="Тип анализа: general, anomaly, trends, recommendations"
    )
    options: dict = Field(default_factory=dict, description="Дополнительные опции")


class ChatMessage(BaseModel):
    """Сообщение в чате."""
    message: str = Field(..., description="Текст сообщения пользователя")
    data_id: str | None = Field(None, description="ID данных для контекста")
    history: list[dict] = Field(default_factory=list, description="История сообщений")


class ReportRequest(BaseModel):
    """Запрос на генерацию отчёта."""
    data_id: str = Field(..., description="ID данных")
    title: str = Field(default="Аналитический отчёт", description="Заголовок отчёта")
    include_charts: bool = Field(default=True, description="Включить графики")
    analysis_types: list[str] = Field(
        default=["general", "recommendations"],
        description="Типы анализа для отчёта"
    )


class TaskStatus(BaseModel):
    """Статус задачи."""
    task_id: str
    status: str  # pending, running, completed, failed
    progress: int = 0
    result: dict | None = None
    error: str | None = None


class UploadResponse(BaseModel):
    """Ответ на загрузку файла."""
    data_id: str
    filename: str
    rows: int
    columns: int
    column_info: dict


class AnalysisResponse(BaseModel):
    """Ответ с результатами анализа."""
    task_id: str
    status: str
    result: dict | None = None


class ChatResponse(BaseModel):
    """Ответ чата."""
    response: str
    suggestions: list[str] = []
    charts: list[str] = []


# ============== Эндпоинты ==============

@app.get("/")
async def root():
    """Корневой эндпоинт."""
    return {
        "name": "Yandex Direct AI Analytics API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/api/status")
async def get_status():
    """Получение статуса системы."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "active_tasks": len([t for t in tasks_storage.values() if t["status"] == "running"]),
        "loaded_datasets": len(data_storage),
        "ml_agent_ready": ml_agent is not None,
    }


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Загрузка файла с данными для анализа.

    Поддерживаемые форматы: CSV, Excel, JSON
    """
    logger.info(f"Загрузка файла: {file.filename}")

    # Генерируем ID для данных
    data_id = str(uuid.uuid4())

    try:
        # Читаем содержимое файла
        content = await file.read()

        # Определяем формат и загружаем в DataFrame
        filename = file.filename.lower()

        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        elif filename.endswith(".json"):
            df = pd.read_json(io.BytesIO(content))
        else:
            raise HTTPException(400, "Неподдерживаемый формат файла")

        # Сохраняем в хранилище
        data_storage[data_id] = df

        # Анализируем структуру
        analysis = data_analyzer.analyze_dataframe(df)

        logger.info(f"Файл загружен: {data_id}, {len(df)} строк")

        return UploadResponse(
            data_id=data_id,
            filename=file.filename,
            rows=len(df),
            columns=len(df.columns),
            column_info=analysis["columns"],
        )

    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {e}")
        raise HTTPException(400, f"Ошибка обработки файла: {str(e)}")


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_data(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
):
    """
    Запуск анализа данных.

    Анализ выполняется асинхронно. Используйте /api/task/{task_id}
    для получения результатов.
    """
    # Проверяем наличие данных
    if request.data_id not in data_storage:
        raise HTTPException(404, "Данные не найдены")

    # Создаём задачу
    task_id = str(uuid.uuid4())
    tasks_storage[task_id] = {
        "status": "pending",
        "progress": 0,
        "result": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
    }

    # Запускаем анализ в фоне
    background_tasks.add_task(
        _run_analysis,
        task_id,
        request.data_id,
        request.analysis_type,
        request.options,
    )

    return AnalysisResponse(
        task_id=task_id,
        status="pending",
    )


async def _run_analysis(
    task_id: str,
    data_id: str,
    analysis_type: str,
    options: dict,
):
    """Фоновая задача анализа."""
    tasks_storage[task_id]["status"] = "running"
    tasks_storage[task_id]["progress"] = 10

    try:
        df = data_storage[data_id]
        agent = get_ml_agent()

        # Подготавливаем данные для Claude
        tasks_storage[task_id]["progress"] = 30
        chunks = data_analyzer.prepare_for_claude(df)

        # Запускаем анализ
        tasks_storage[task_id]["progress"] = 50
        result = await agent.execute_task({
            "type": analysis_type,
            "data": {
                "metadata": chunks[0]["content"],
                "samples": [c["content"] for c in chunks[1:]],
            }
        })

        tasks_storage[task_id]["progress"] = 80

        # Генерируем графики
        charts = []
        analysis = data_analyzer.analyze_dataframe(df)

        numeric_cols = analysis["column_types"]["numeric"]
        categorical_cols = analysis["column_types"]["categorical"]

        if numeric_cols and len(numeric_cols) > 0:
            # Гистограмма первого числового столбца
            chart_path = chart_generator.generate_histogram(
                df[numeric_cols[0]].dropna().tolist(),
                f"Распределение: {numeric_cols[0]}",
                numeric_cols[0],
                f"hist_{task_id}",
            )
            charts.append(chart_path)

        if categorical_cols and len(categorical_cols) > 0 and numeric_cols:
            # Столбчатая диаграмма по категориям
            cat_data = df.groupby(categorical_cols[0])[numeric_cols[0]].sum().head(20).to_dict()
            chart_path = chart_generator.generate_bar_chart(
                cat_data,
                f"{numeric_cols[0]} по {categorical_cols[0]}",
                categorical_cols[0],
                numeric_cols[0],
                f"bar_{task_id}",
            )
            charts.append(chart_path)

        tasks_storage[task_id]["progress"] = 100
        tasks_storage[task_id]["status"] = "completed"
        tasks_storage[task_id]["result"] = {
            "analysis": result.data,
            "charts": charts,
            "columns": analysis["columns"],
        }

    except Exception as e:
        logger.error(f"Ошибка анализа: {e}")
        tasks_storage[task_id]["status"] = "failed"
        tasks_storage[task_id]["error"] = str(e)


@app.get("/api/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Получение статуса задачи."""
    if task_id not in tasks_storage:
        raise HTTPException(404, "Задача не найдена")

    task = tasks_storage[task_id]
    return TaskStatus(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        result=task["result"],
        error=task["error"],
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatMessage):
    """
    Чат с AI агентом.

    Позволяет задавать вопросы по данным в свободной форме.
    """
    try:
        agent = get_ml_agent()

        # Формируем контекст
        context = ""
        if request.data_id and request.data_id in data_storage:
            df = data_storage[request.data_id]
            analysis = data_analyzer.analyze_dataframe(df)
            context = f"""
Контекст данных:
- Строк: {analysis['shape']['rows']}
- Столбцов: {analysis['shape']['columns']}
- Типы столбцов: {json.dumps(analysis['column_types'], ensure_ascii=False)}
- Описание столбцов: {json.dumps({k: v['type'] for k, v in analysis['columns'].items()}, ensure_ascii=False)}
"""

        # Формируем историю сообщений
        messages = [
            {
                "role": "system",
                "content": f"""Ты - AI аналитик данных рекламных кампаний Яндекс Директа.
Твоя задача - помогать пользователю анализировать данные, отвечать на вопросы
и давать рекомендации по оптимизации рекламы.

{context}

Отвечай на русском языке. Будь конкретен и полезен.
Если нужны графики или отчёты, предложи пользователю их сгенерировать."""
            }
        ]

        # Добавляем историю
        for msg in request.history[-10:]:  # Последние 10 сообщений
            messages.append(msg)

        # Добавляем текущее сообщение
        messages.append({"role": "user", "content": request.message})

        # Получаем ответ от Claude
        response = await agent._client.chat(messages, temperature=0.7)

        # Формируем предложения
        suggestions = []
        if "анализ" in request.message.lower():
            suggestions.append("Запустить полный анализ данных")
        if "отчёт" in request.message.lower() or "pdf" in request.message.lower():
            suggestions.append("Сгенерировать PDF отчёт")
        if "ставк" in request.message.lower():
            suggestions.append("Получить рекомендации по ставкам")

        return ChatResponse(
            response=response,
            suggestions=suggestions,
            charts=[],
        )

    except Exception as e:
        logger.error(f"Ошибка чата: {e}")
        raise HTTPException(500, f"Ошибка обработки запроса: {str(e)}")


@app.post("/api/report")
async def generate_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks,
):
    """
    Генерация PDF отчёта.

    Возвращает task_id для отслеживания прогресса.
    После завершения можно скачать файл через /api/report/{task_id}/download
    """
    if request.data_id not in data_storage:
        raise HTTPException(404, "Данные не найдены")

    task_id = str(uuid.uuid4())
    tasks_storage[task_id] = {
        "status": "pending",
        "progress": 0,
        "result": None,
        "error": None,
        "type": "report",
    }

    background_tasks.add_task(
        _generate_report,
        task_id,
        request.data_id,
        request.title,
        request.include_charts,
        request.analysis_types,
    )

    return {"task_id": task_id, "status": "pending"}


async def _generate_report(
    task_id: str,
    data_id: str,
    title: str,
    include_charts: bool,
    analysis_types: list[str],
):
    """Фоновая генерация отчёта."""
    tasks_storage[task_id]["status"] = "running"

    try:
        df = data_storage[data_id]
        agent = get_ml_agent()

        tasks_storage[task_id]["progress"] = 20

        # Анализируем данные
        analysis = data_analyzer.analyze_dataframe(df)
        chunks = data_analyzer.prepare_for_claude(df)

        # Получаем AI анализ
        tasks_storage[task_id]["progress"] = 40
        ai_result = await agent.execute_task({
            "type": "analyze",
            "data": {"metadata": chunks[0]["content"]},
        })

        # Генерируем графики
        charts = []
        if include_charts:
            tasks_storage[task_id]["progress"] = 60

            numeric_cols = analysis["column_types"]["numeric"]
            categorical_cols = analysis["column_types"]["categorical"]

            if numeric_cols:
                charts.append(chart_generator.generate_histogram(
                    df[numeric_cols[0]].dropna().tolist(),
                    f"Распределение: {numeric_cols[0]}",
                    numeric_cols[0],
                    f"report_hist_{task_id}",
                ))

            if categorical_cols and numeric_cols:
                cat_data = df.groupby(categorical_cols[0])[numeric_cols[0]].sum().head(15).to_dict()
                charts.append(chart_generator.generate_bar_chart(
                    cat_data,
                    f"Суммарный {numeric_cols[0]} по {categorical_cols[0]}",
                    categorical_cols[0],
                    numeric_cols[0],
                    f"report_bar_{task_id}",
                ))

        # Генерируем PDF
        tasks_storage[task_id]["progress"] = 80
        pdf_path = pdf_generator.generate_from_analysis(
            analysis_result=ai_result.data,
            charts=charts,
            title=title,
        )

        tasks_storage[task_id]["progress"] = 100
        tasks_storage[task_id]["status"] = "completed"
        tasks_storage[task_id]["result"] = {"pdf_path": pdf_path}

    except Exception as e:
        logger.error(f"Ошибка генерации отчёта: {e}")
        tasks_storage[task_id]["status"] = "failed"
        tasks_storage[task_id]["error"] = str(e)


@app.get("/api/report/{task_id}/download")
async def download_report(task_id: str):
    """Скачивание сгенерированного PDF отчёта."""
    if task_id not in tasks_storage:
        raise HTTPException(404, "Задача не найдена")

    task = tasks_storage[task_id]

    if task["status"] != "completed":
        raise HTTPException(400, f"Отчёт ещё не готов. Статус: {task['status']}")

    pdf_path = task["result"]["pdf_path"]

    if not Path(pdf_path).exists():
        raise HTTPException(404, "Файл отчёта не найден")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"report_{task_id}.pdf",
    )


@app.get("/api/data/{data_id}/preview")
async def preview_data(data_id: str, rows: int = 100):
    """Предпросмотр загруженных данных."""
    if data_id not in data_storage:
        raise HTTPException(404, "Данные не найдены")

    df = data_storage[data_id]

    return {
        "columns": list(df.columns),
        "data": df.head(rows).to_dict(orient="records"),
        "total_rows": len(df),
    }


@app.delete("/api/data/{data_id}")
async def delete_data(data_id: str):
    """Удаление загруженных данных."""
    if data_id not in data_storage:
        raise HTTPException(404, "Данные не найдены")

    del data_storage[data_id]
    return {"status": "deleted", "data_id": data_id}


# ============== Запуск сервера ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
