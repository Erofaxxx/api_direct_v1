"""
Модуль для работы с Reports API Яндекс Директа.

Reports API позволяет получать статистику по:
- Кампаниям
- Группам объявлений
- Объявлениям
- Ключевым фразам
- Поисковым запросам

Особенности:
- Асинхронное формирование отчетов
- Отчеты большого объема (до 2ГБ)
- Различные форматы (TSV)

Типы отчетов:
- ACCOUNT_PERFORMANCE_REPORT - по аккаунту
- CAMPAIGN_PERFORMANCE_REPORT - по кампаниям
- ADGROUP_PERFORMANCE_REPORT - по группам
- AD_PERFORMANCE_REPORT - по объявлениям
- CRITERIA_PERFORMANCE_REPORT - по критериям показа
- SEARCH_QUERY_PERFORMANCE_REPORT - по поисковым запросам
"""

import csv
import io
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import requests

from ..config import config

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Типы отчетов Reports API."""
    ACCOUNT_PERFORMANCE = "ACCOUNT_PERFORMANCE_REPORT"
    CAMPAIGN_PERFORMANCE = "CAMPAIGN_PERFORMANCE_REPORT"
    ADGROUP_PERFORMANCE = "ADGROUP_PERFORMANCE_REPORT"
    AD_PERFORMANCE = "AD_PERFORMANCE_REPORT"
    CRITERIA_PERFORMANCE = "CRITERIA_PERFORMANCE_REPORT"
    SEARCH_QUERY_PERFORMANCE = "SEARCH_QUERY_PERFORMANCE_REPORT"
    CUSTOM = "CUSTOM_REPORT"


class DateRangeType(Enum):
    """Типы периодов для отчетов."""
    TODAY = "TODAY"
    YESTERDAY = "YESTERDAY"
    LAST_3_DAYS = "LAST_3_DAYS"
    LAST_5_DAYS = "LAST_5_DAYS"
    LAST_7_DAYS = "LAST_7_DAYS"
    LAST_14_DAYS = "LAST_14_DAYS"
    LAST_30_DAYS = "LAST_30_DAYS"
    LAST_90_DAYS = "LAST_90_DAYS"
    LAST_365_DAYS = "LAST_365_DAYS"
    THIS_WEEK_MON_TODAY = "THIS_WEEK_MON_TODAY"
    THIS_WEEK_SUN_TODAY = "THIS_WEEK_SUN_TODAY"
    LAST_WEEK = "LAST_WEEK"
    LAST_BUSINESS_WEEK = "LAST_BUSINESS_WEEK"
    LAST_WEEK_SUN_SAT = "LAST_WEEK_SUN_SAT"
    THIS_MONTH = "THIS_MONTH"
    LAST_MONTH = "LAST_MONTH"
    ALL_TIME = "ALL_TIME"
    CUSTOM_DATE = "CUSTOM_DATE"
    AUTO = "AUTO"


@dataclass
class ReportDefinition:
    """Определение отчета."""
    report_type: ReportType
    date_range_type: DateRangeType
    field_names: list[str]
    report_name: str = "API Report"
    date_from: str | None = None  # Формат YYYY-MM-DD
    date_to: str | None = None    # Формат YYYY-MM-DD
    filter_: dict[str, Any] | None = None
    include_vat: bool = True
    include_discount: bool = False


class ReportsService:
    """
    Сервис для работы с Reports API.

    Последовательность работы:
    1. Формирование запроса на создание отчета
    2. Отправка запроса (POST /reports)
    3. Ожидание готовности отчета (HTTP 201 - в процессе, 200 - готов)
    4. Получение и парсинг данных отчета

    Ограничения:
    - Не более 5 запросов в секунду
    - Интервал проверки готовности: 10-60 секунд
    - Максимальный размер отчета: 2ГБ
    """

    # Стандартные поля для разных типов отчетов
    CAMPAIGN_FIELDS = [
        "CampaignId", "CampaignName", "CampaignType",
        "Impressions", "Clicks", "Ctr", "Cost", "AvgCpc",
        "Conversions", "ConversionRate", "CostPerConversion",
    ]

    ADGROUP_FIELDS = [
        "AdGroupId", "AdGroupName", "CampaignId",
        "Impressions", "Clicks", "Ctr", "Cost", "AvgCpc",
    ]

    CRITERIA_FIELDS = [
        "CampaignId", "AdGroupId", "CriterionId", "Criterion",
        "Impressions", "Clicks", "Ctr", "Cost", "AvgCpc",
        "AvgPosition", "BounceRate", "AvgPageviews",
    ]

    def __init__(
        self,
        token: str | None = None,
        client_login: str | None = None,
        sandbox: bool | None = None,
    ):
        """
        Инициализация сервиса отчетов.

        Args:
            token: OAuth токен
            client_login: Логин клиента (для агентств)
            sandbox: Режим песочницы
        """
        self._token = token or config.token
        self._client_login = client_login or config.client_login
        self._sandbox = sandbox if sandbox is not None else config.is_sandbox
        self._session = requests.Session()

    @property
    def reports_url(self) -> str:
        """URL для Reports API."""
        if self._sandbox:
            return config.REPORTS_SANDBOX_URL
        return config.REPORTS_PRODUCTION_URL

    def _get_headers(self, processing_mode: str = "auto") -> dict[str, str]:
        """
        Формирует заголовки для запроса отчета.

        Args:
            processing_mode: Режим обработки (auto, online, offline)
        """
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept-Language": "ru",
            "processingMode": processing_mode,
            "returnMoneyInMicros": "false",
            "skipReportHeader": "true",
            "skipReportSummary": "true",
        }

        if self._client_login:
            headers["Client-Login"] = self._client_login

        return headers

    def _build_report_request(self, definition: ReportDefinition) -> dict[str, Any]:
        """Формирует тело запроса на создание отчета."""
        selection_criteria: dict[str, Any] = {}

        # Настройка периода
        if definition.date_range_type == DateRangeType.CUSTOM_DATE:
            if definition.date_from and definition.date_to:
                selection_criteria["DateFrom"] = definition.date_from
                selection_criteria["DateTo"] = definition.date_to
        else:
            selection_criteria["DateRange"] = {
                "DateRangeType": definition.date_range_type.value
            }

        # Фильтры
        if definition.filter_:
            selection_criteria["Filter"] = definition.filter_

        return {
            "params": {
                "SelectionCriteria": selection_criteria,
                "FieldNames": definition.field_names,
                "ReportName": definition.report_name,
                "ReportType": definition.report_type.value,
                "DateRangeType": definition.date_range_type.value,
                "Format": "TSV",
                "IncludeVAT": "YES" if definition.include_vat else "NO",
                "IncludeDiscount": "YES" if definition.include_discount else "NO",
            }
        }

    def request_report(
        self,
        definition: ReportDefinition,
        wait_for_result: bool = True,
        poll_interval: int = 10,
        max_wait_time: int = 600,
    ) -> list[dict[str, Any]]:
        """
        Запрашивает и получает отчет.

        Args:
            definition: Определение отчета
            wait_for_result: Ожидать готовности отчета
            poll_interval: Интервал проверки готовности (секунды)
            max_wait_time: Максимальное время ожидания (секунды)

        Returns:
            Список записей отчета в виде словарей

        Raises:
            TimeoutError: Если отчет не готов за max_wait_time
        """
        request_body = self._build_report_request(definition)

        logger.info(f"Запрос отчета: {definition.report_type.value}")

        start_time = time.time()
        retry_interval = poll_interval

        while True:
            response = self._session.post(
                self.reports_url,
                json=request_body,
                headers=self._get_headers(),
                timeout=config.REPORT_TIMEOUT,
            )

            if response.status_code == 200:
                # Отчет готов
                logger.info("Отчет получен успешно")
                return self._parse_tsv_report(response.text, definition.field_names)

            elif response.status_code == 201:
                # Отчет формируется
                if not wait_for_result:
                    logger.info("Отчет в процессе формирования")
                    return []

                # Получаем рекомендуемый интервал ожидания
                retry_in = response.headers.get("retryIn", poll_interval)
                retry_interval = int(retry_in)

                elapsed = time.time() - start_time
                if elapsed >= max_wait_time:
                    raise TimeoutError(
                        f"Отчет не готов за {max_wait_time} секунд"
                    )

                logger.debug(
                    f"Отчет формируется, ожидание {retry_interval}с "
                    f"(прошло {elapsed:.0f}с)"
                )
                time.sleep(retry_interval)

            elif response.status_code == 202:
                # Отчет поставлен в очередь
                elapsed = time.time() - start_time
                if elapsed >= max_wait_time:
                    raise TimeoutError(
                        f"Отчет в очереди более {max_wait_time} секунд"
                    )

                logger.debug(f"Отчет в очереди, ожидание {retry_interval}с")
                time.sleep(retry_interval)

            elif response.status_code == 400:
                error_data = response.json()
                raise ValueError(
                    f"Ошибка в запросе отчета: {error_data}"
                )

            elif response.status_code == 500:
                logger.warning("Ошибка сервера, повторная попытка...")
                time.sleep(retry_interval)

            else:
                raise RuntimeError(
                    f"Неожиданный статус {response.status_code}: {response.text}"
                )

    def _parse_tsv_report(
        self,
        tsv_content: str,
        field_names: list[str],
    ) -> list[dict[str, Any]]:
        """
        Парсит TSV отчет в список словарей.

        Args:
            tsv_content: Содержимое отчета в формате TSV
            field_names: Список полей

        Returns:
            Список записей
        """
        records = []
        reader = csv.DictReader(
            io.StringIO(tsv_content),
            delimiter="\t",
            fieldnames=field_names,
        )

        # Пропускаем заголовок если он есть
        first_row = next(reader, None)
        if first_row and first_row.get(field_names[0]) != field_names[0]:
            records.append(first_row)

        for row in reader:
            records.append(dict(row))

        logger.info(f"Получено {len(records)} записей")
        return records

    def get_campaign_stats(
        self,
        date_range: DateRangeType = DateRangeType.LAST_7_DAYS,
        campaign_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получение статистики по кампаниям.

        Метод API: Reports (CAMPAIGN_PERFORMANCE_REPORT)
        Частота вызова: 1 раз в сутки (или по запросу)

        Args:
            date_range: Период отчета
            campaign_ids: Фильтр по ID кампаний

        Returns:
            Статистика по кампаниям
        """
        filter_ = None
        if campaign_ids:
            filter_ = {
                "Field": "CampaignId",
                "Operator": "IN",
                "Values": [str(id_) for id_ in campaign_ids],
            }

        definition = ReportDefinition(
            report_type=ReportType.CAMPAIGN_PERFORMANCE,
            date_range_type=date_range,
            field_names=self.CAMPAIGN_FIELDS,
            report_name="Campaign Statistics",
            filter_=filter_,
        )

        return self.request_report(definition)

    def get_criteria_stats(
        self,
        date_range: DateRangeType = DateRangeType.LAST_7_DAYS,
        campaign_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получение статистики по ключевым фразам.

        Метод API: Reports (CRITERIA_PERFORMANCE_REPORT)
        Частота вызова: 1 раз в сутки (или по запросу)

        Args:
            date_range: Период отчета
            campaign_ids: Фильтр по ID кампаний

        Returns:
            Статистика по ключевым фразам
        """
        filter_ = None
        if campaign_ids:
            filter_ = {
                "Field": "CampaignId",
                "Operator": "IN",
                "Values": [str(id_) for id_ in campaign_ids],
            }

        definition = ReportDefinition(
            report_type=ReportType.CRITERIA_PERFORMANCE,
            date_range_type=date_range,
            field_names=self.CRITERIA_FIELDS,
            report_name="Criteria Statistics",
            filter_=filter_,
        )

        return self.request_report(definition)

    def close(self) -> None:
        """Закрывает HTTP сессию."""
        self._session.close()

    def __enter__(self) -> "ReportsService":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
