"""
Базовый клиент API Яндекс Директа.

Основные возможности:
- Автоматическое соблюдение rate limits (5 запросов/сек)
- Повторные попытки при временных ошибках
- Обработка всех типов ошибок API
- Поддержка sandbox и production режимов

Методы API v5 (JSON):
- Campaigns: get, add, update, delete, suspend, resume, archive, unarchive
- AdGroups: get, add, update, delete
- Ads: get, add, update, delete, suspend, resume, archive, moderate
- Keywords: get, add, update, delete, suspend, resume
- Bids: get, set
- Reports: получение статистики
"""

import json
import logging
from typing import Any

import requests

from .config import APIConfig, config
from .utils.errors import (
    AuthorizationError,
    RateLimitError,
    TemporaryError,
    YandexDirectAPIError,
    handle_http_error,
    raise_for_error,
)
from .utils.rate_limiter import RateLimiter, RetryHandler

logger = logging.getLogger(__name__)


class YandexDirectClient:
    """
    Клиент для работы с API Яндекс Директа v5.

    Автоматически обрабатывает:
    - Rate limiting (не более 5 запросов в секунду)
    - Повторные попытки при ошибках
    - Авторизацию через OAuth токен

    Пример использования:
        client = YandexDirectClient()
        campaigns = client.call("campaigns", "get", {
            "SelectionCriteria": {},
            "FieldNames": ["Id", "Name", "Status"]
        })
    """

    def __init__(
        self,
        token: str | None = None,
        client_login: str | None = None,
        sandbox: bool | None = None,
        api_config: APIConfig | None = None,
    ):
        """
        Инициализация клиента.

        Args:
            token: OAuth токен (если не указан, берется из переменных окружения)
            client_login: Логин клиента (для агентств)
            sandbox: Режим песочницы (если не указан, берется из переменных окружения)
            api_config: Конфигурация API (по умолчанию используется глобальная)
        """
        self._config = api_config or config
        self._token = token or self._config.token
        self._client_login = client_login or self._config.client_login

        if sandbox is not None:
            self._sandbox = sandbox
        else:
            self._sandbox = self._config.is_sandbox

        # Rate limiter и retry handler
        self._rate_limiter = RateLimiter(
            max_requests=self._config.MAX_REQUESTS_PER_SECOND
        )
        self._retry_handler = RetryHandler(
            max_retries=self._config.MAX_RETRIES,
            base_delay=self._config.RETRY_DELAY_BASE,
            delay_multiplier=self._config.RETRY_DELAY_MULTIPLIER,
        )

        # HTTP сессия для переиспользования соединений
        self._session = requests.Session()

        logger.info(f"Клиент инициализирован (sandbox={self._sandbox})")

    @property
    def base_url(self) -> str:
        """Базовый URL API."""
        if self._sandbox:
            return self._config.SANDBOX_URL
        return self._config.PRODUCTION_URL

    @property
    def reports_url(self) -> str:
        """URL для Reports API."""
        if self._sandbox:
            return self._config.REPORTS_SANDBOX_URL
        return self._config.REPORTS_PRODUCTION_URL

    def _get_headers(self, use_operator_units: bool = False) -> dict[str, str]:
        """
        Формирует заголовки запроса.

        Args:
            use_operator_units: Использовать баллы оператора (для агентств)

        Returns:
            Словарь заголовков
        """
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept-Language": "ru",
        }

        if self._client_login:
            headers["Client-Login"] = self._client_login

        if use_operator_units:
            headers["Use-Operator-Units"] = "true"

        return headers

    def _make_request(
        self,
        url: str,
        payload: dict[str, Any],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Выполняет HTTP запрос к API.

        Args:
            url: URL эндпоинта
            payload: Тело запроса
            timeout: Таймаут в секундах

        Returns:
            Ответ API в формате dict

        Raises:
            YandexDirectAPIError: При ошибках API
        """
        timeout = timeout or self._config.REQUEST_TIMEOUT

        logger.debug(f"Запрос: {url}")
        logger.debug(f"Payload: {json.dumps(payload, ensure_ascii=False)[:500]}")

        response = self._session.post(
            url,
            json=payload,
            headers=self._get_headers(),
            timeout=timeout,
        )

        # Проверка HTTP ошибок
        if response.status_code != 200:
            handle_http_error(response.status_code, response.text)

        result = response.json()

        # Логируем информацию о потраченных баллах
        units_info = response.headers.get("Units")
        if units_info:
            logger.debug(f"Units: {units_info}")

        return result

    def call(
        self,
        service: str,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Вызов метода API с автоматическим rate limiting и retry.

        Args:
            service: Название сервиса (campaigns, adgroups, ads, keywords, bids)
            method: Название метода (get, add, update, delete и др.)
            params: Параметры метода

        Returns:
            Результат вызова API

        Raises:
            AuthorizationError: При ошибках авторизации
            YandexDirectAPIError: При других ошибках API

        Пример:
            # Получение списка кампаний
            result = client.call("campaigns", "get", {
                "SelectionCriteria": {},
                "FieldNames": ["Id", "Name", "Status"]
            })
        """
        url = f"{self.base_url}{service}"
        payload = {
            "method": method,
            "params": params or {},
        }

        attempt = 0
        last_error = None

        while True:
            try:
                # Ждем своей очереди согласно rate limit
                with self._rate_limiter.acquire():
                    result = self._make_request(url, payload)

                # Проверяем на ошибки в ответе
                raise_for_error(result)

                return result

            except AuthorizationError:
                # Ошибки авторизации не повторяем
                raise

            except (RateLimitError, TemporaryError) as e:
                last_error = e

                if not self._retry_handler.wait_and_retry(attempt):
                    logger.error(f"Исчерпаны попытки после {attempt + 1} попыток")
                    raise

                attempt += 1

            except requests.RequestException as e:
                # Сетевые ошибки
                last_error = e
                logger.warning(f"Сетевая ошибка: {e}")

                if not self._retry_handler.wait_and_retry(attempt):
                    raise YandexDirectAPIError(
                        error=type("Error", (), {
                            "code": 0,
                            "message": "Network error",
                            "detail": str(e),
                        })()
                    ) from e

                attempt += 1

    def get_campaigns(
        self,
        ids: list[int] | None = None,
        states: list[str] | None = None,
        statuses: list[str] | None = None,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получение списка кампаний.

        Метод API: Campaigns.get

        Args:
            ids: Список ID кампаний (опционально)
            states: Фильтр по состояниям (ON, OFF, SUSPENDED и др.)
            statuses: Фильтр по статусам
            fields: Список запрашиваемых полей

        Returns:
            Список кампаний
        """
        selection_criteria: dict[str, Any] = {}

        if ids:
            selection_criteria["Ids"] = ids
        if states:
            selection_criteria["States"] = states
        if statuses:
            selection_criteria["Statuses"] = statuses

        fields = fields or ["Id", "Name", "Status", "State", "DailyBudget"]

        result = self.call("campaigns", "get", {
            "SelectionCriteria": selection_criteria,
            "FieldNames": fields,
        })

        return result.get("result", {}).get("Campaigns", [])

    def get_ad_groups(
        self,
        campaign_ids: list[int],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получение групп объявлений.

        Метод API: AdGroups.get

        Args:
            campaign_ids: Список ID кампаний
            fields: Список запрашиваемых полей

        Returns:
            Список групп объявлений
        """
        fields = fields or ["Id", "Name", "CampaignId", "Status"]

        result = self.call("adgroups", "get", {
            "SelectionCriteria": {"CampaignIds": campaign_ids},
            "FieldNames": fields,
        })

        return result.get("result", {}).get("AdGroups", [])

    def get_ads(
        self,
        ad_group_ids: list[int],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получение объявлений.

        Метод API: Ads.get

        Args:
            ad_group_ids: Список ID групп объявлений
            fields: Список запрашиваемых полей

        Returns:
            Список объявлений
        """
        fields = fields or ["Id", "AdGroupId", "Status", "State"]

        result = self.call("ads", "get", {
            "SelectionCriteria": {"AdGroupIds": ad_group_ids},
            "FieldNames": fields,
        })

        return result.get("result", {}).get("Ads", [])

    def get_keywords(
        self,
        ad_group_ids: list[int],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получение ключевых фраз.

        Метод API: Keywords.get

        Args:
            ad_group_ids: Список ID групп объявлений
            fields: Список запрашиваемых полей

        Returns:
            Список ключевых фраз
        """
        fields = fields or ["Id", "Keyword", "AdGroupId", "Bid", "Status"]

        result = self.call("keywords", "get", {
            "SelectionCriteria": {"AdGroupIds": ad_group_ids},
            "FieldNames": fields,
        })

        return result.get("result", {}).get("Keywords", [])

    def set_bids(
        self,
        bids: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Установка ставок для ключевых фраз.

        Метод API: Bids.set

        Args:
            bids: Список ставок в формате:
                [{"KeywordId": 123, "Bid": 1500000}, ...]
                (ставка в микрорублях, 1 руб = 1000000)

        Returns:
            Результат операции
        """
        result = self.call("bids", "set", {
            "Bids": bids,
        })

        return result.get("result", {})

    def close(self) -> None:
        """Закрывает HTTP сессию."""
        self._session.close()

    def __enter__(self) -> "YandexDirectClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
