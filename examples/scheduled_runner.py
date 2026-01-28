#!/usr/bin/env python3
"""
Пример: Запуск выгрузки по расписанию.

Этот скрипт запускает ежедневную выгрузку данных
в указанное время (по умолчанию в 03:00).

Использование:
    python -m examples.scheduled_runner

Также можно запустить через cron:
    0 3 * * * /path/to/python -m examples.daily_export
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import schedule
import time
import logging
from datetime import datetime

from yandex_direct_api.app import YandexDirectApp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_export():
    """Выполняет выгрузку данных."""
    logger.info("Запуск запланированной выгрузки")

    try:
        with YandexDirectApp(output_dir="data/exports") as app:
            results = app.run_daily_export()

            logger.info(
                f"Выгрузка завершена: "
                f"{len(results['campaigns'])} кампаний, "
                f"{len(results['statistics'])} записей статистики"
            )

    except Exception as e:
        logger.error(f"Ошибка при выгрузке: {e}")


def main():
    """Запуск по расписанию."""
    # Запуск каждый день в 03:00
    schedule.every().day.at("03:00").do(run_export)

    logger.info("Планировщик запущен. Выгрузка запланирована на 03:00 ежедневно.")
    logger.info("Для остановки нажмите Ctrl+C")

    # Также можно запустить сразу при старте
    # run_export()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
