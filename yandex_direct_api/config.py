"""
Конфигурация для работы с API Яндекс Директа.

API Endpoints:
- Production: https://api.direct.yandex.com/json/v5/
- Sandbox: https://api-sandbox.direct.yandex.com/json/v5/

Ограничения API (учитываются в программе):
- Максимум 5 запросов в секунду
- Лимит на количество объектов в одном запросе (10000)
- Лимит на размер ответа (отчеты до 2ГБ)
- Баллы за операции (ежедневный лимит)
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class APIConfig:
    """Конфигурация API Яндекс Директа."""

    # Базовые URL
    PRODUCTION_URL: str = "https://api.direct.yandex.com/json/v5/"
    SANDBOX_URL: str = "https://api-sandbox.direct.yandex.com/json/v5/"

    # URL для отчетов
    REPORTS_PRODUCTION_URL: str = "https://api.direct.yandex.com/json/v5/reports"
    REPORTS_SANDBOX_URL: str = "https://api-sandbox.direct.yandex.com/json/v5/reports"

    # Ограничения API
    MAX_REQUESTS_PER_SECOND: int = 5
    REQUEST_INTERVAL: float = 0.2  # 200ms между запросами (1/5 секунды)
    MAX_OBJECTS_PER_REQUEST: int = 10000
    MAX_IDS_PER_REQUEST: int = 10000

    # Настройки повторных попыток
    MAX_RETRIES: int = 3
    RETRY_DELAY_BASE: float = 1.0  # Базовая задержка в секундах
    RETRY_DELAY_MULTIPLIER: float = 2.0  # Множитель для экспоненциальной задержки

    # Таймауты
    REQUEST_TIMEOUT: int = 300  # 5 минут для обычных запросов
    REPORT_TIMEOUT: int = 600  # 10 минут для отчетов
    REPORT_POLL_INTERVAL: int = 10  # Интервал проверки готовности отчета

    @property
    def token(self) -> str:
        """OAuth токен."""
        return os.getenv("YANDEX_DIRECT_TOKEN", "")

    @property
    def client_login(self) -> str | None:
        """Логин клиента (для агентств)."""
        login = os.getenv("YANDEX_CLIENT_LOGIN", "")
        return login if login else None

    @property
    def is_sandbox(self) -> bool:
        """Режим песочницы."""
        return os.getenv("YANDEX_API_MODE", "sandbox").lower() == "sandbox"

    @property
    def base_url(self) -> str:
        """Базовый URL API в зависимости от режима."""
        return self.SANDBOX_URL if self.is_sandbox else self.PRODUCTION_URL

    @property
    def reports_url(self) -> str:
        """URL для Reports API."""
        return self.REPORTS_SANDBOX_URL if self.is_sandbox else self.REPORTS_PRODUCTION_URL


# Глобальная конфигурация
config = APIConfig()
