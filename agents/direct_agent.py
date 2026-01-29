"""
Агент для работы с API Яндекс Директа.

Задачи агента:
- Получение данных о кампаниях, группах, ключевых фразах
- Выгрузка статистики через Reports API
- Обновление ставок по рекомендациям ML агента
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .base import AgentMessage, AgentStatus, BaseAgent, MessageType, TaskResult

# Импорт существующих модулей
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from yandex_direct_api.client import YandexDirectClient
from yandex_direct_api.services.reports import DateRangeType, ReportsService
from yandex_direct_api.utils.errors import AuthorizationError, YandexDirectAPIError

logger = logging.getLogger(__name__)


class DirectAgent(BaseAgent):
    """
    Агент для работы с Яндекс Директом.

    Возможности:
    - fetch_campaigns: получение списка кампаний
    - fetch_statistics: выгрузка статистики
    - update_bids: обновление ставок
    - full_export: полная ежедневная выгрузка
    """

    def __init__(
        self,
        name: str = "direct_agent",
        token: str | None = None,
        client_login: str | None = None,
        data_dir: str = "data",
        config: dict[str, Any] | None = None,
    ):
        super().__init__(name, config)

        self.token = token
        self.client_login = client_login
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._client: YandexDirectClient | None = None
        self._reports: ReportsService | None = None

    def _get_client(self) -> YandexDirectClient:
        """Получение или создание клиента API."""
        if self._client is None:
            self._client = YandexDirectClient(
                token=self.token,
                client_login=self.client_login,
            )
        return self._client

    def _get_reports(self) -> ReportsService:
        """Получение или создание сервиса отчётов."""
        if self._reports is None:
            self._reports = ReportsService(
                token=self.token,
                client_login=self.client_login,
            )
        return self._reports

    async def execute_task(self, task: dict[str, Any]) -> TaskResult:
        """
        Выполнение задачи.

        Поддерживаемые задачи:
        - fetch_campaigns: получить список кампаний
        - fetch_statistics: получить статистику
        - update_bids: обновить ставки
        - full_export: полная выгрузка данных
        """
        task_type = task.get("type", "full_export")
        start_time = datetime.now()

        self.logger.info(f"Выполнение задачи: {task_type}")
        self.status = AgentStatus.RUNNING

        try:
            if task_type == "fetch_campaigns":
                result = await self._fetch_campaigns(task)
            elif task_type == "fetch_statistics":
                result = await self._fetch_statistics(task)
            elif task_type == "update_bids":
                result = await self._update_bids(task)
            elif task_type == "full_export":
                result = await self._full_export(task)
            else:
                raise ValueError(f"Неизвестный тип задачи: {task_type}")

            execution_time = (datetime.now() - start_time).total_seconds()
            self.status = AgentStatus.COMPLETED

            return TaskResult(
                success=True,
                data=result,
                execution_time=execution_time,
            )

        except AuthorizationError as e:
            self.logger.error(f"Ошибка авторизации: {e}")
            self.status = AgentStatus.ERROR
            return TaskResult(success=False, error=str(e))

        except YandexDirectAPIError as e:
            self.logger.error(f"Ошибка API: {e}")
            self.status = AgentStatus.ERROR
            return TaskResult(success=False, error=str(e))

        except Exception as e:
            self.logger.error(f"Неожиданная ошибка: {e}")
            self.status = AgentStatus.ERROR
            return TaskResult(success=False, error=str(e))

    async def process_message(self, message: AgentMessage) -> AgentMessage | None:
        """Обработка входящего сообщения."""
        self.logger.debug(f"Получено сообщение от {message.sender}: {message.type}")

        if message.type == MessageType.TASK:
            # Выполняем задачу
            result = await self.execute_task(message.payload)

            # Отправляем результат
            return await self.send_message(
                receiver=message.sender,
                msg_type=MessageType.RESULT,
                payload={
                    "task_id": message.id,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                    "execution_time": result.execution_time,
                }
            )

        elif message.type == MessageType.DATA:
            # Обработка данных от другого агента (например, рекомендации от ML)
            if "bid_recommendations" in message.payload:
                result = await self._update_bids({
                    "recommendations": message.payload["bid_recommendations"]
                })
                return await self.send_message(
                    receiver=message.sender,
                    msg_type=MessageType.RESULT,
                    payload={"bids_updated": result}
                )

        return None

    async def _fetch_campaigns(self, task: dict) -> dict[str, Any]:
        """Получение списка кампаний."""
        client = self._get_client()

        # Выполняем в отдельном потоке (т.к. requests синхронный)
        loop = asyncio.get_event_loop()
        campaigns = await loop.run_in_executor(
            None,
            lambda: client.get_campaigns(
                fields=task.get("fields", [
                    "Id", "Name", "Status", "State", "Type", "DailyBudget"
                ])
            )
        )

        self.logger.info(f"Получено кампаний: {len(campaigns)}")

        # Сохраняем данные
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.data_dir / f"campaigns_{timestamp}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(campaigns, f, ensure_ascii=False, indent=2)

        return {
            "campaigns": campaigns,
            "count": len(campaigns),
            "file": str(filepath),
        }

    async def _fetch_statistics(self, task: dict) -> dict[str, Any]:
        """Получение статистики."""
        reports = self._get_reports()

        date_range = task.get("date_range", "LAST_7_DAYS")
        date_range_type = DateRangeType[date_range]

        loop = asyncio.get_event_loop()

        # Статистика по кампаниям
        campaign_stats = await loop.run_in_executor(
            None,
            lambda: reports.get_campaign_stats(date_range=date_range_type)
        )

        # Статистика по ключевым фразам
        criteria_stats = await loop.run_in_executor(
            None,
            lambda: reports.get_criteria_stats(date_range=date_range_type)
        )

        self.logger.info(
            f"Получено статистики: кампании={len(campaign_stats)}, "
            f"фразы={len(criteria_stats)}"
        )

        # Сохраняем в CSV для ML анализа
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if campaign_stats:
            df = pd.DataFrame(campaign_stats)
            filepath = self.data_dir / f"campaign_stats_{timestamp}.csv"
            df.to_csv(filepath, index=False, encoding="utf-8")

        if criteria_stats:
            df = pd.DataFrame(criteria_stats)
            filepath = self.data_dir / f"criteria_stats_{timestamp}.csv"
            df.to_csv(filepath, index=False, encoding="utf-8")

        return {
            "campaign_stats": campaign_stats,
            "criteria_stats": criteria_stats,
            "campaign_count": len(campaign_stats),
            "criteria_count": len(criteria_stats),
        }

    async def _update_bids(self, task: dict) -> dict[str, Any]:
        """Обновление ставок по рекомендациям."""
        recommendations = task.get("recommendations", [])

        if not recommendations:
            return {"updated": 0, "message": "Нет рекомендаций для обновления"}

        client = self._get_client()

        # Конвертируем в формат API
        bids = [
            {
                "KeywordId": r["keyword_id"],
                "Bid": int(r["new_bid"] * 1_000_000),  # В микрорублях
            }
            for r in recommendations
        ]

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: client.set_bids(bids)
        )

        self.logger.info(f"Обновлено ставок: {len(bids)}")

        return {
            "updated": len(bids),
            "result": result,
        }

    async def _full_export(self, task: dict) -> dict[str, Any]:
        """Полная выгрузка данных."""
        self.logger.info("Начало полной выгрузки данных")

        # 1. Получаем кампании
        campaigns_result = await self._fetch_campaigns(task)

        # 2. Получаем статистику
        stats_result = await self._fetch_statistics(task)

        # 3. Объединяем результаты
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        full_data = {
            "timestamp": timestamp,
            "campaigns": campaigns_result["campaigns"],
            "campaign_stats": stats_result["campaign_stats"],
            "criteria_stats": stats_result["criteria_stats"],
        }

        # Сохраняем полный экспорт
        filepath = self.data_dir / f"full_export_{timestamp}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Полная выгрузка завершена: {filepath}")

        return {
            "file": str(filepath),
            "campaigns_count": campaigns_result["count"],
            "campaign_stats_count": stats_result["campaign_count"],
            "criteria_stats_count": stats_result["criteria_count"],
        }

    async def cleanup(self) -> None:
        """Очистка ресурсов."""
        if self._client:
            self._client.close()
        if self._reports:
            self._reports.close()
        self.logger.info("Ресурсы освобождены")
