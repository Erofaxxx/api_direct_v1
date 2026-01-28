"""
Yandex Direct API Client.

Клиент для работы с API Яндекс Директа v5.

Основные компоненты:
- YandexDirectClient: базовый клиент API
- YandexDirectApp: приложение для автоматизации
- ReportsService: работа с Reports API
"""

from .client import YandexDirectClient
from .app import YandexDirectApp
from .config import config, APIConfig

__version__ = "1.0.0"
__all__ = [
    "YandexDirectClient",
    "YandexDirectApp",
    "config",
    "APIConfig",
]
