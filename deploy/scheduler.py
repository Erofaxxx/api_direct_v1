#!/usr/bin/env python3
"""
Планировщик задач для мультиагентной системы.

Запускает задачи по расписанию:
- 03:00 - ежедневная выгрузка данных
- 10:00 - генерация рекомендаций (по будням)
- По запросу - оптимизация ставок

Использование:
    python -m deploy.scheduler
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

import schedule
import time

from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/scheduler.log"),
    ]
)
logger = logging.getLogger("scheduler")

# Глобальная переменная для остановки
running = True


def signal_handler(signum, frame):
    """Обработчик сигналов для корректной остановки."""
    global running
    logger.info(f"Получен сигнал {signum}, останавливаемся...")
    running = False


def run_daily_pipeline():
    """Запуск ежедневного пайплайна."""
    logger.info("Запуск ежедневного пайплайна по расписанию")

    try:
        from orchestrator.main import Orchestrator

        async def _run():
            orchestrator = Orchestrator()
            try:
                await orchestrator.start()
                results = await orchestrator.run_daily_pipeline()
                logger.info(f"Пайплайн завершён: success={results['success']}")
                return results
            finally:
                await orchestrator.stop()

        asyncio.run(_run())

    except Exception as e:
        logger.error(f"Ошибка в ежедневном пайплайне: {e}")


def run_recommendations():
    """Генерация рекомендаций."""
    logger.info("Запуск генерации рекомендаций")

    try:
        from orchestrator.main import Orchestrator

        async def _run():
            orchestrator = Orchestrator()
            try:
                await orchestrator.start()
                results = await orchestrator.run_analysis("general")
                logger.info("Рекомендации сгенерированы")
                return results
            finally:
                await orchestrator.stop()

        asyncio.run(_run())

    except Exception as e:
        logger.error(f"Ошибка при генерации рекомендаций: {e}")


def run_bid_optimization():
    """Оптимизация ставок (без автоприменения)."""
    logger.info("Запуск оптимизации ставок")

    try:
        from orchestrator.main import Orchestrator

        async def _run():
            orchestrator = Orchestrator()
            try:
                await orchestrator.start()
                results = await orchestrator.run_bid_optimization(auto_apply=False)
                logger.info("Оптимизация завершена")
                return results
            finally:
                await orchestrator.stop()

        asyncio.run(_run())

    except Exception as e:
        logger.error(f"Ошибка при оптимизации ставок: {e}")


def main():
    """Основной цикл планировщика."""
    global running

    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 60)
    logger.info("ПЛАНИРОВЩИК ЗАДАЧ ЗАПУЩЕН")
    logger.info("=" * 60)

    # Настройка расписания
    # Ежедневная выгрузка в 03:00
    schedule.every().day.at("03:00").do(run_daily_pipeline)
    logger.info("Задача: ежедневная выгрузка в 03:00")

    # Генерация рекомендаций в 10:00 по будням
    schedule.every().monday.at("10:00").do(run_recommendations)
    schedule.every().tuesday.at("10:00").do(run_recommendations)
    schedule.every().wednesday.at("10:00").do(run_recommendations)
    schedule.every().thursday.at("10:00").do(run_recommendations)
    schedule.every().friday.at("10:00").do(run_recommendations)
    logger.info("Задача: рекомендации в 10:00 (пн-пт)")

    # Проверка аномалий в 12:00
    schedule.every().day.at("12:00").do(
        lambda: asyncio.run(run_analysis_task("anomaly"))
    )
    logger.info("Задача: проверка аномалий в 12:00")

    logger.info("")
    logger.info("Ожидание задач... (Ctrl+C для остановки)")

    while running:
        try:
            schedule.run_pending()
            time.sleep(60)  # Проверка каждую минуту
        except Exception as e:
            logger.error(f"Ошибка в цикле планировщика: {e}")
            time.sleep(60)

    logger.info("Планировщик остановлен")


async def run_analysis_task(analysis_type: str):
    """Запуск задачи анализа."""
    from orchestrator.main import Orchestrator

    orchestrator = Orchestrator()
    try:
        await orchestrator.start()
        results = await orchestrator.run_analysis(analysis_type)
        logger.info(f"Анализ {analysis_type} завершён")
        return results
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    main()
