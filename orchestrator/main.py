"""
Оркестратор мультиагентной системы.

Координирует работу агентов:
1. DirectAgent - получение данных из Яндекс Директа
2. MLAnalystAgent - анализ данных и генерация рекомендаций

Сценарии работы:
- daily_pipeline: ежедневная выгрузка + анализ + рекомендации
- on_demand_analysis: анализ по запросу
- bid_optimization: оптимизация ставок
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.base import AgentMessage, AgentStatus, MessageType
from agents.direct_agent import DirectAgent
from agents.ml_agent import MLAnalystAgent

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/orchestrator.log"),
    ]
)
logger = logging.getLogger("orchestrator")


class Orchestrator:
    """
    Оркестратор мультиагентной системы.

    Управляет жизненным циклом агентов и координирует их работу.
    """

    def __init__(
        self,
        yandex_token: str | None = None,
        yandex_client_login: str | None = None,
        openrouter_api_key: str | None = None,
        claude_model: str = "anthropic/claude-sonnet-4",
        data_dir: str = "data",
    ):
        """
        Инициализация оркестратора.

        Args:
            yandex_token: Токен Яндекс Директа
            yandex_client_login: Логин клиента (для агентств)
            openrouter_api_key: API ключ OpenRouter
            claude_model: Модель Claude для ML агента
            data_dir: Директория для данных
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Создаём директорию для логов
        Path("logs").mkdir(exist_ok=True)

        # Инициализация агентов
        self.direct_agent = DirectAgent(
            name="direct_agent",
            token=yandex_token or os.getenv("YANDEX_DIRECT_TOKEN"),
            client_login=yandex_client_login or os.getenv("YANDEX_CLIENT_LOGIN"),
            data_dir=str(self.data_dir),
        )

        self.ml_agent = MLAnalystAgent(
            name="ml_analyst",
            api_key=openrouter_api_key or os.getenv("OPENROUTER_API_KEY"),
            model=claude_model,
            data_dir=str(self.data_dir),
        )

        self._agents = {
            "direct_agent": self.direct_agent,
            "ml_analyst": self.ml_agent,
        }

        self._running = False
        logger.info("Оркестратор инициализирован")

    async def start(self) -> None:
        """Запуск всех агентов."""
        logger.info("Запуск агентов...")
        self._running = True

        for name, agent in self._agents.items():
            await agent.start()
            logger.info(f"Агент '{name}' запущен")

    async def stop(self) -> None:
        """Остановка всех агентов."""
        logger.info("Остановка агентов...")
        self._running = False

        for name, agent in self._agents.items():
            await agent.stop()
            if hasattr(agent, 'cleanup'):
                await agent.cleanup()
            logger.info(f"Агент '{name}' остановлен")

    async def run_daily_pipeline(self) -> dict[str, Any]:
        """
        Ежедневный пайплайн обработки данных.

        Последовательность:
        1. DirectAgent: полная выгрузка данных из Яндекс Директа
        2. MLAnalystAgent: анализ данных и генерация рекомендаций
        3. (Опционально) DirectAgent: применение рекомендаций по ставкам

        Returns:
            Результаты выполнения пайплайна
        """
        logger.info("=" * 60)
        logger.info("ЗАПУСК ЕЖЕДНЕВНОГО ПАЙПЛАЙНА")
        logger.info("=" * 60)

        results = {
            "timestamp": datetime.now().isoformat(),
            "stages": {},
            "success": True,
        }

        try:
            # Этап 1: Выгрузка данных из Яндекс Директа
            logger.info("\n>>> Этап 1: Выгрузка данных из Яндекс Директа")
            direct_result = await self.direct_agent.execute_task({
                "type": "full_export"
            })

            results["stages"]["data_export"] = {
                "success": direct_result.success,
                "data": direct_result.data,
                "execution_time": direct_result.execution_time,
            }

            if not direct_result.success:
                logger.error(f"Ошибка выгрузки: {direct_result.error}")
                results["success"] = False
                return results

            logger.info(
                f"Выгружено: {direct_result.data.get('campaigns_count', 0)} кампаний, "
                f"{direct_result.data.get('criteria_stats_count', 0)} записей статистики"
            )

            # Этап 2: ML анализ данных
            logger.info("\n>>> Этап 2: ML анализ данных")
            ml_result = await self.ml_agent.execute_task({
                "type": "analyze",
                "data": {
                    "campaign_stats": direct_result.data.get("campaign_stats", []),
                    "criteria_stats": direct_result.data.get("criteria_stats", []),
                }
            })

            results["stages"]["ml_analysis"] = {
                "success": ml_result.success,
                "data": ml_result.data,
                "execution_time": ml_result.execution_time,
            }

            if not ml_result.success:
                logger.error(f"Ошибка анализа: {ml_result.error}")

            # Этап 3: Генерация рекомендаций
            logger.info("\n>>> Этап 3: Генерация рекомендаций по ставкам")
            rec_result = await self.ml_agent.execute_task({
                "type": "generate_recommendations",
                "data": {
                    "criteria_stats": direct_result.data.get("criteria_stats", []),
                }
            })

            results["stages"]["recommendations"] = {
                "success": rec_result.success,
                "data": rec_result.data,
                "execution_time": rec_result.execution_time,
            }

            recommendations = rec_result.data.get("bid_recommendations", [])
            logger.info(f"Сгенерировано рекомендаций: {len(recommendations)}")

            # Сохраняем результаты пайплайна
            self._save_pipeline_results(results)

            logger.info("\n" + "=" * 60)
            logger.info("ПАЙПЛАЙН ЗАВЕРШЁН УСПЕШНО")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Критическая ошибка в пайплайне: {e}")
            results["success"] = False
            results["error"] = str(e)

        return results

    async def run_bid_optimization(
        self,
        auto_apply: bool = False,
    ) -> dict[str, Any]:
        """
        Пайплайн оптимизации ставок.

        Args:
            auto_apply: Автоматически применять рекомендации

        Returns:
            Результаты оптимизации
        """
        logger.info("Запуск оптимизации ставок")

        results = {
            "timestamp": datetime.now().isoformat(),
            "stages": {},
        }

        # 1. Получаем свежую статистику
        stats_result = await self.direct_agent.execute_task({
            "type": "fetch_statistics",
            "date_range": "LAST_7_DAYS",
        })

        results["stages"]["fetch_stats"] = stats_result.data

        # 2. Генерируем рекомендации
        rec_result = await self.ml_agent.execute_task({
            "type": "generate_recommendations",
            "data": {
                "criteria_stats": stats_result.data.get("criteria_stats", []),
            }
        })

        results["stages"]["recommendations"] = rec_result.data
        recommendations = rec_result.data.get("bid_recommendations", [])

        # 3. Применяем рекомендации (если включено)
        if auto_apply and recommendations:
            logger.info(f"Применение {len(recommendations)} рекомендаций...")

            apply_result = await self.direct_agent.execute_task({
                "type": "update_bids",
                "recommendations": recommendations,
            })

            results["stages"]["apply_bids"] = apply_result.data
            logger.info(f"Обновлено ставок: {apply_result.data.get('updated', 0)}")
        else:
            logger.info(
                f"Сгенерировано {len(recommendations)} рекомендаций "
                "(автоприменение отключено)"
            )

        return results

    async def run_analysis(
        self,
        analysis_type: str = "general",
    ) -> dict[str, Any]:
        """
        Запуск анализа данных.

        Args:
            analysis_type: Тип анализа (general, anomaly, trends)

        Returns:
            Результаты анализа
        """
        logger.info(f"Запуск анализа: {analysis_type}")

        task_map = {
            "general": "analyze",
            "anomaly": "find_anomalies",
            "trends": "analyze_trends",
        }

        result = await self.ml_agent.execute_task({
            "type": task_map.get(analysis_type, "analyze")
        })

        return result.data

    def _save_pipeline_results(self, results: dict[str, Any]) -> None:
        """Сохранение результатов пайплайна."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.data_dir / f"pipeline_results_{timestamp}.json"

        import json
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Результаты сохранены: {filepath}")

    def get_status(self) -> dict[str, Any]:
        """Получение статуса всех агентов."""
        return {
            name: agent.get_status()
            for name, agent in self._agents.items()
        }


async def main():
    """Главная функция запуска."""
    orchestrator = Orchestrator()

    try:
        await orchestrator.start()

        # Запуск ежедневного пайплайна
        results = await orchestrator.run_daily_pipeline()

        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТЫ ПАЙПЛАЙНА")
        print("=" * 60)
        print(f"Успех: {results['success']}")

        for stage_name, stage_data in results.get("stages", {}).items():
            print(f"\n{stage_name}:")
            if isinstance(stage_data, dict):
                for key, value in stage_data.items():
                    if key != "data":
                        print(f"  {key}: {value}")

    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())
