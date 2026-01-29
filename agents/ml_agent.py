"""
ML Агент для анализа данных с использованием Claude API через OpenRouter.

Задачи агента:
- Анализ статистики рекламных кампаний
- Слияние данных из Директа и CRM
- Генерация рекомендаций по ставкам
- Выявление аномалий и трендов
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import numpy as np

from .base import AgentMessage, AgentStatus, BaseAgent, MessageType, TaskResult

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """
    Клиент для работы с Claude API через OpenRouter.

    OpenRouter API позволяет использовать различные LLM модели,
    включая Claude Sonnet 4.5.
    """

    BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "anthropic/claude-sonnet-4"  # Claude Sonnet 4.5

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        site_url: str = "https://your-app.com",
        site_name: str = "Yandex Direct Analytics",
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model or self.DEFAULT_MODEL
        self.site_url = site_url
        self.site_name = site_name

        if not self.api_key:
            raise ValueError(
                "OpenRouter API key не указан. "
                "Установите переменную OPENROUTER_API_KEY"
            )

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=120.0,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        Отправка сообщения в Claude API.

        Args:
            messages: Список сообщений [{"role": "user", "content": "..."}]
            temperature: Температура генерации (0-1)
            max_tokens: Максимальное количество токенов в ответе

        Returns:
            Текст ответа модели
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = await self._client.post(
            "/chat/completions",
            headers=headers,
            json=payload,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"OpenRouter API error: {response.status_code} - {response.text}"
            )

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def analyze_data(
        self,
        data_description: str,
        data_sample: str,
        analysis_type: str = "general",
    ) -> dict[str, Any]:
        """
        Анализ данных с помощью Claude.

        Args:
            data_description: Описание данных
            data_sample: Пример данных (JSON/CSV)
            analysis_type: Тип анализа (general, anomaly, trends, recommendations)

        Returns:
            Результат анализа в формате dict
        """
        prompts = {
            "general": """Проанализируй данные рекламной кампании Яндекс Директа.
Определи:
1. Общую эффективность кампаний
2. Лучшие и худшие кампании по ROI
3. Ключевые метрики и их динамику

Данные: {data_sample}

Ответ дай в формате JSON:
{{
    "summary": "краткое резюме",
    "top_campaigns": ["список лучших"],
    "worst_campaigns": ["список худших"],
    "key_insights": ["ключевые выводы"],
    "recommendations": ["рекомендации"]
}}""",

            "anomaly": """Найди аномалии в данных рекламной кампании.
Ищи:
1. Резкие скачки CTR, CPC, расходов
2. Кампании с нетипичными показателями
3. Подозрительную активность

Данные: {data_sample}

Ответ в формате JSON:
{{
    "anomalies": [
        {{"campaign_id": "...", "type": "...", "description": "...", "severity": "high/medium/low"}}
    ],
    "recommendations": ["что делать с аномалиями"]
}}""",

            "trends": """Проанализируй тренды в данных рекламной кампании.
Определи:
1. Растущие и падающие показатели
2. Сезонность
3. Прогноз на следующий период

Данные: {data_sample}

Ответ в формате JSON:
{{
    "trends": [
        {{"metric": "...", "direction": "up/down/stable", "change_percent": 0}}
    ],
    "seasonality": "описание сезонности",
    "forecast": "прогноз"
}}""",

            "recommendations": """На основе данных рекламной кампании сгенерируй рекомендации по ставкам.

Правила:
- Если ROI > 30% и CTR > 2%, увеличить ставку на 10-20%
- Если ROI < 10%, уменьшить ставку на 15-25%
- Если CTR < 0.5%, рассмотреть паузу или переработку объявления

Данные: {data_sample}

Ответ в формате JSON:
{{
    "bid_recommendations": [
        {{
            "keyword_id": 123,
            "current_bid": 10.5,
            "new_bid": 12.0,
            "reason": "высокий ROI",
            "confidence": 0.85
        }}
    ],
    "pause_recommendations": ["keyword_ids для паузы"],
    "summary": "общее резюме"
}}"""
        }

        prompt = prompts.get(analysis_type, prompts["general"])
        prompt = prompt.format(data_sample=data_sample)

        messages = [
            {
                "role": "system",
                "content": (
                    "Ты - эксперт по анализу рекламных данных Яндекс Директа. "
                    "Твоя задача - анализировать статистику кампаний и давать "
                    "рекомендации по оптимизации. Отвечай только в формате JSON."
                )
            },
            {"role": "user", "content": prompt}
        ]

        response = await self.chat(messages, temperature=0.3)

        # Парсим JSON из ответа
        try:
            # Ищем JSON в ответе
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        return {"raw_response": response, "parse_error": True}

    async def close(self):
        """Закрытие клиента."""
        await self._client.aclose()


class MLAnalystAgent(BaseAgent):
    """
    ML Агент для анализа данных рекламных кампаний.

    Использует Claude API через OpenRouter для:
    - Интеллектуального анализа данных
    - Генерации рекомендаций
    - Выявления паттернов и аномалий
    """

    def __init__(
        self,
        name: str = "ml_analyst",
        api_key: str | None = None,
        model: str = "anthropic/claude-sonnet-4",
        data_dir: str = "data",
        config: dict[str, Any] | None = None,
    ):
        super().__init__(name, config)

        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._client = OpenRouterClient(api_key=api_key, model=model)

    async def execute_task(self, task: dict[str, Any]) -> TaskResult:
        """
        Выполнение задачи анализа.

        Поддерживаемые задачи:
        - analyze: общий анализ данных
        - find_anomalies: поиск аномалий
        - analyze_trends: анализ трендов
        - generate_recommendations: генерация рекомендаций по ставкам
        - merge_with_crm: слияние с данными CRM
        """
        task_type = task.get("type", "analyze")
        start_time = datetime.now()

        self.logger.info(f"Выполнение задачи: {task_type}")
        self.status = AgentStatus.RUNNING

        try:
            if task_type == "analyze":
                result = await self._analyze_data(task)
            elif task_type == "find_anomalies":
                result = await self._find_anomalies(task)
            elif task_type == "analyze_trends":
                result = await self._analyze_trends(task)
            elif task_type == "generate_recommendations":
                result = await self._generate_recommendations(task)
            elif task_type == "merge_with_crm":
                result = await self._merge_with_crm(task)
            else:
                raise ValueError(f"Неизвестный тип задачи: {task_type}")

            execution_time = (datetime.now() - start_time).total_seconds()
            self.status = AgentStatus.COMPLETED

            return TaskResult(
                success=True,
                data=result,
                execution_time=execution_time,
            )

        except Exception as e:
            self.logger.error(f"Ошибка при выполнении задачи: {e}")
            self.status = AgentStatus.ERROR
            return TaskResult(success=False, error=str(e))

    async def process_message(self, message: AgentMessage) -> AgentMessage | None:
        """Обработка входящего сообщения."""
        self.logger.debug(f"Получено сообщение от {message.sender}: {message.type}")

        if message.type == MessageType.TASK:
            result = await self.execute_task(message.payload)

            return await self.send_message(
                receiver=message.sender,
                msg_type=MessageType.RESULT,
                payload={
                    "task_id": message.id,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                }
            )

        elif message.type == MessageType.DATA:
            # Получены данные от DirectAgent для анализа
            if "campaign_stats" in message.payload or "criteria_stats" in message.payload:
                result = await self._generate_recommendations({
                    "data": message.payload
                })

                return await self.send_message(
                    receiver=message.sender,
                    msg_type=MessageType.DATA,
                    payload={
                        "bid_recommendations": result.get("bid_recommendations", [])
                    }
                )

        return None

    async def _analyze_data(self, task: dict) -> dict[str, Any]:
        """Общий анализ данных."""
        data = task.get("data") or await self._load_latest_data()

        # Подготавливаем данные для Claude
        data_sample = self._prepare_data_sample(data)

        analysis = await self._client.analyze_data(
            data_description="Статистика рекламных кампаний Яндекс Директа",
            data_sample=data_sample,
            analysis_type="general",
        )

        # Сохраняем результат
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.data_dir / f"analysis_{timestamp}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

        return analysis

    async def _find_anomalies(self, task: dict) -> dict[str, Any]:
        """Поиск аномалий в данных."""
        data = task.get("data") or await self._load_latest_data()
        data_sample = self._prepare_data_sample(data)

        analysis = await self._client.analyze_data(
            data_description="Данные для поиска аномалий",
            data_sample=data_sample,
            analysis_type="anomaly",
        )

        return analysis

    async def _analyze_trends(self, task: dict) -> dict[str, Any]:
        """Анализ трендов."""
        data = task.get("data") or await self._load_latest_data()
        data_sample = self._prepare_data_sample(data)

        analysis = await self._client.analyze_data(
            data_description="Данные для анализа трендов",
            data_sample=data_sample,
            analysis_type="trends",
        )

        return analysis

    async def _generate_recommendations(self, task: dict) -> dict[str, Any]:
        """Генерация рекомендаций по ставкам."""
        data = task.get("data") or await self._load_latest_data()

        # Объединяем данные Директа с данными CRM если есть
        crm_data = task.get("crm_data") or await self._load_crm_data()
        if crm_data is not None:
            data = self._merge_data(data, crm_data)

        data_sample = self._prepare_data_sample(data)

        analysis = await self._client.analyze_data(
            data_description="Данные для генерации рекомендаций по ставкам",
            data_sample=data_sample,
            analysis_type="recommendations",
        )

        # Сохраняем рекомендации
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.data_dir / f"recommendations_{timestamp}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

        self.logger.info(
            f"Сгенерировано рекомендаций: "
            f"{len(analysis.get('bid_recommendations', []))}"
        )

        return analysis

    async def _merge_with_crm(self, task: dict) -> dict[str, Any]:
        """Слияние данных Директа с CRM."""
        direct_data = task.get("direct_data") or await self._load_latest_data()
        crm_data = task.get("crm_data") or await self._load_crm_data()

        if crm_data is None:
            return {"error": "CRM данные не найдены"}

        merged = self._merge_data(direct_data, crm_data)

        # Сохраняем объединённые данные
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.data_dir / f"merged_data_{timestamp}.csv"

        if isinstance(merged, pd.DataFrame):
            merged.to_csv(filepath, index=False, encoding="utf-8")
        else:
            df = pd.DataFrame(merged)
            df.to_csv(filepath, index=False, encoding="utf-8")

        return {
            "file": str(filepath),
            "rows": len(merged) if hasattr(merged, '__len__') else 0,
        }

    async def _load_latest_data(self) -> dict[str, Any]:
        """Загрузка последних данных."""
        # Ищем последний файл экспорта
        export_files = sorted(
            self.data_dir.glob("full_export_*.json"),
            reverse=True
        )

        if export_files:
            with open(export_files[0], "r", encoding="utf-8") as f:
                return json.load(f)

        # Если нет полного экспорта, ищем статистику
        stats_files = sorted(
            self.data_dir.glob("campaign_stats_*.csv"),
            reverse=True
        )

        if stats_files:
            df = pd.read_csv(stats_files[0])
            return {"campaign_stats": df.to_dict(orient="records")}

        return {}

    async def _load_crm_data(self) -> pd.DataFrame | None:
        """Загрузка данных CRM."""
        crm_files = sorted(
            self.data_dir.glob("crm_*.csv"),
            reverse=True
        )

        if crm_files:
            return pd.read_csv(crm_files[0])

        # Возвращаем тестовые данные если CRM файлов нет
        return pd.DataFrame({
            "keyword_id": [1001, 1002, 1003, 1004, 1005],
            "conversions": [10, 5, 15, 3, 20],
            "revenue": [50000, 25000, 75000, 15000, 100000],
            "margin": [0.3, 0.25, 0.35, 0.2, 0.4],
        })

    def _merge_data(
        self,
        direct_data: dict[str, Any],
        crm_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Слияние данных Директа и CRM."""
        # Преобразуем данные Директа в DataFrame
        if "criteria_stats" in direct_data:
            direct_df = pd.DataFrame(direct_data["criteria_stats"])
        elif "campaign_stats" in direct_data:
            direct_df = pd.DataFrame(direct_data["campaign_stats"])
        else:
            direct_df = pd.DataFrame(direct_data)

        # Переименовываем колонку для слияния
        if "CriterionId" in direct_df.columns:
            direct_df = direct_df.rename(columns={"CriterionId": "keyword_id"})
        elif "CampaignId" in direct_df.columns:
            direct_df = direct_df.rename(columns={"CampaignId": "keyword_id"})

        # Слияние
        if "keyword_id" in direct_df.columns and "keyword_id" in crm_data.columns:
            merged = direct_df.merge(crm_data, on="keyword_id", how="left")
        else:
            # Если нет общего ключа, просто объединяем
            merged = pd.concat([direct_df, crm_data], axis=1)

        return merged

    def _prepare_data_sample(
        self,
        data: dict[str, Any] | pd.DataFrame,
        max_rows: int = 50,
    ) -> str:
        """Подготовка примера данных для Claude."""
        if isinstance(data, pd.DataFrame):
            sample = data.head(max_rows)
            return sample.to_json(orient="records", force_ascii=False)

        if isinstance(data, dict):
            # Ограничиваем размер данных
            result = {}
            for key, value in data.items():
                if isinstance(value, list) and len(value) > max_rows:
                    result[key] = value[:max_rows]
                else:
                    result[key] = value
            return json.dumps(result, ensure_ascii=False, indent=2)

        return str(data)[:5000]

    async def cleanup(self) -> None:
        """Очистка ресурсов."""
        await self._client.close()
        self.logger.info("Ресурсы освобождены")
