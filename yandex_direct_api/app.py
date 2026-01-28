"""
Главное приложение для интеграции с API Яндекс Директа.

Функционал:
1. Ежедневная выгрузка статистики из Яндекс Директа
2. Получение данных о кампаниях, группах, объявлениях
3. Управление ставками на основе анализа данных
4. Экспорт данных для слияния с CRM и ML анализа

Схема работы:
1. Запуск по расписанию (1 раз в сутки) или по запросу менеджера
2. Получение списка активных кампаний
3. Выгрузка статистики по кампаниям и ключевым фразам
4. Сохранение данных для дальнейшего анализа
5. (Опционально) Корректировка ставок на основе ML рекомендаций
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .client import YandexDirectClient
from .services.reports import DateRangeType, ReportsService
from .utils.errors import AuthorizationError, YandexDirectAPIError

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class YandexDirectApp:
    """
    Приложение для работы с Яндекс Директом.

    Реализует полный цикл:
    - Получение данных из API
    - Экспорт для ML анализа
    - Применение рекомендаций (корректировка ставок)

    Используемые методы API:
    - Campaigns.get - получение списка кампаний
    - AdGroups.get - получение групп объявлений
    - Keywords.get - получение ключевых фраз
    - Bids.set - установка ставок
    - Reports API - получение статистики

    Частота вызовов:
    - Полная выгрузка: 1 раз в сутки
    - Обновление ставок: по запросу (не чаще 1 раза в час)
    """

    def __init__(
        self,
        token: str | None = None,
        client_login: str | None = None,
        output_dir: str = "data",
    ):
        """
        Инициализация приложения.

        Args:
            token: OAuth токен Яндекс Директа
            client_login: Логин клиента (для агентских аккаунтов)
            output_dir: Директория для сохранения данных
        """
        self.client = YandexDirectClient(token=token, client_login=client_login)
        self.reports = ReportsService(token=token, client_login=client_login)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Приложение Яндекс Директ инициализировано")

    def run_daily_export(self) -> dict[str, Any]:
        """
        Выполняет ежедневную выгрузку данных.

        Последовательность вызовов API:
        1. Campaigns.get - получение списка кампаний (1 запрос)
        2. Reports API (CAMPAIGN_PERFORMANCE_REPORT) - статистика по кампаниям
        3. AdGroups.get - получение групп для каждой кампании (N запросов)
        4. Keywords.get - получение ключевых фраз (N запросов)
        5. Reports API (CRITERIA_PERFORMANCE_REPORT) - статистика по фразам

        Интервал между запросами: 200мс (соблюдение лимита 5 req/sec)

        Returns:
            Словарь с результатами выгрузки
        """
        logger.info("=" * 50)
        logger.info("Начало ежедневной выгрузки данных")
        logger.info("=" * 50)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = {
            "timestamp": timestamp,
            "campaigns": [],
            "statistics": [],
            "keywords_stats": [],
            "errors": [],
        }

        try:
            # 1. Получение списка кампаний
            logger.info("Шаг 1: Получение списка кампаний (Campaigns.get)")
            campaigns = self.client.get_campaigns(
                fields=[
                    "Id", "Name", "Status", "State", "Type",
                    "DailyBudget", "StartDate", "EndDate",
                ]
            )
            results["campaigns"] = campaigns
            logger.info(f"Получено кампаний: {len(campaigns)}")

            # 2. Получение статистики по кампаниям
            logger.info("Шаг 2: Получение статистики по кампаниям (Reports API)")
            campaign_stats = self.reports.get_campaign_stats(
                date_range=DateRangeType.LAST_7_DAYS
            )
            results["statistics"] = campaign_stats
            logger.info(f"Получено записей статистики: {len(campaign_stats)}")

            # 3. Получение ключевых фраз и их статистики
            active_campaign_ids = [
                c["Id"] for c in campaigns
                if c.get("State") in ("ON", "SUSPENDED")
            ]

            if active_campaign_ids:
                logger.info("Шаг 3: Получение групп объявлений (AdGroups.get)")
                ad_groups = self.client.get_ad_groups(
                    campaign_ids=active_campaign_ids
                )
                logger.info(f"Получено групп объявлений: {len(ad_groups)}")

                if ad_groups:
                    ad_group_ids = [g["Id"] for g in ad_groups]

                    logger.info("Шаг 4: Получение ключевых фраз (Keywords.get)")
                    keywords = self.client.get_keywords(ad_group_ids=ad_group_ids)
                    logger.info(f"Получено ключевых фраз: {len(keywords)}")

                logger.info("Шаг 5: Получение статистики по фразам (Reports API)")
                keywords_stats = self.reports.get_criteria_stats(
                    date_range=DateRangeType.LAST_7_DAYS,
                    campaign_ids=active_campaign_ids,
                )
                results["keywords_stats"] = keywords_stats
                logger.info(f"Получено записей статистики: {len(keywords_stats)}")

            # 4. Сохранение данных
            self._save_results(results, timestamp)

            logger.info("=" * 50)
            logger.info("Выгрузка завершена успешно")
            logger.info("=" * 50)

        except AuthorizationError as e:
            logger.error(f"Ошибка авторизации: {e}")
            results["errors"].append({"type": "auth", "message": str(e)})
            raise

        except YandexDirectAPIError as e:
            logger.error(f"Ошибка API: {e}")
            results["errors"].append({"type": "api", "message": str(e)})

        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            results["errors"].append({"type": "unknown", "message": str(e)})

        return results

    def _save_results(self, results: dict[str, Any], timestamp: str) -> None:
        """
        Сохраняет результаты выгрузки.

        Args:
            results: Данные для сохранения
            timestamp: Временная метка
        """
        # JSON для архива
        json_path = self.output_dir / f"export_{timestamp}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"Данные сохранены: {json_path}")

        # CSV для анализа
        if results.get("statistics"):
            stats_df = pd.DataFrame(results["statistics"])
            csv_path = self.output_dir / f"campaign_stats_{timestamp}.csv"
            stats_df.to_csv(csv_path, index=False, encoding="utf-8")
            logger.info(f"Статистика кампаний: {csv_path}")

        if results.get("keywords_stats"):
            kw_df = pd.DataFrame(results["keywords_stats"])
            csv_path = self.output_dir / f"keywords_stats_{timestamp}.csv"
            kw_df.to_csv(csv_path, index=False, encoding="utf-8")
            logger.info(f"Статистика фраз: {csv_path}")

    def apply_bid_recommendations(
        self,
        recommendations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Применяет рекомендации по ставкам от ML модели.

        Метод API: Bids.set
        Частота вызова: по запросу менеджера (не чаще 1 раза в час)

        Args:
            recommendations: Список рекомендаций в формате:
                [{"keyword_id": 123, "new_bid": 15.5}, ...]
                где new_bid - новая ставка в рублях

        Returns:
            Результат применения ставок
        """
        logger.info(f"Применение {len(recommendations)} рекомендаций по ставкам")

        # Конвертируем рубли в копейки (API принимает целые числа)
        bids = [
            {
                "KeywordId": r["keyword_id"],
                "Bid": int(r["new_bid"] * 1_000_000),  # В микрорублях
            }
            for r in recommendations
        ]

        # Разбиваем на батчи (не более 10000 за запрос)
        batch_size = 10000
        results = {"success": 0, "errors": []}

        for i in range(0, len(bids), batch_size):
            batch = bids[i:i + batch_size]
            try:
                result = self.client.set_bids(batch)
                results["success"] += len(batch)
                logger.info(f"Обновлено ставок: {len(batch)}")
            except YandexDirectAPIError as e:
                logger.error(f"Ошибка при установке ставок: {e}")
                results["errors"].append(str(e))

        return results

    def close(self) -> None:
        """Закрывает все соединения."""
        self.client.close()
        self.reports.close()
        logger.info("Соединения закрыты")

    def __enter__(self) -> "YandexDirectApp":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def main():
    """Точка входа для запуска выгрузки."""
    with YandexDirectApp() as app:
        results = app.run_daily_export()
        print(f"Выгружено кампаний: {len(results['campaigns'])}")
        print(f"Записей статистики: {len(results['statistics'])}")


if __name__ == "__main__":
    main()
