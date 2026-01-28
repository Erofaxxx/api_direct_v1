"""
Обработка ошибок API Яндекс Директа.

Типы ошибок API:
1. Ошибки авторизации (код 52, 53, 54)
2. Ошибки лимитов (код 506, 9000)
3. Ошибки данных (коды 8xxx)
4. Временные ошибки (5xx HTTP, код 1000, 1001, 1002)

Стратегия обработки:
- Временные ошибки: повтор с экспоненциальной задержкой
- Ошибки лимитов: ожидание сброса лимита
- Ошибки авторизации: прекращение работы, уведомление
- Ошибки данных: логирование, пропуск операции
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Категории ошибок API."""
    AUTHORIZATION = "authorization"  # Ошибки авторизации - не повторять
    RATE_LIMIT = "rate_limit"        # Превышение лимита - ждать и повторить
    TEMPORARY = "temporary"           # Временные ошибки - повторить с задержкой
    DATA_ERROR = "data_error"        # Ошибки в данных - не повторять, логировать
    UNKNOWN = "unknown"              # Неизвестные ошибки


@dataclass
class APIError:
    """Структура ошибки API."""
    code: int
    message: str
    detail: str = ""
    category: ErrorCategory = ErrorCategory.UNKNOWN
    retryable: bool = False
    retry_after: int | None = None  # Время ожидания в секундах


# Маппинг кодов ошибок на категории
ERROR_CODES = {
    # Ошибки авторизации
    52: ErrorCategory.AUTHORIZATION,   # Недействительный токен
    53: ErrorCategory.AUTHORIZATION,   # Недостаточно прав
    54: ErrorCategory.AUTHORIZATION,   # Пользователь заблокирован

    # Ошибки лимитов
    506: ErrorCategory.RATE_LIMIT,     # Превышен лимит запросов
    9000: ErrorCategory.RATE_LIMIT,    # Превышен лимит операций

    # Временные ошибки
    1000: ErrorCategory.TEMPORARY,     # Внутренняя ошибка сервера
    1001: ErrorCategory.TEMPORARY,     # Сервер перегружен
    1002: ErrorCategory.TEMPORARY,     # Таймаут операции

    # Ошибки данных
    8000: ErrorCategory.DATA_ERROR,    # Объект не найден
    8800: ErrorCategory.DATA_ERROR,    # Недопустимое значение параметра
}


class YandexDirectAPIError(Exception):
    """Базовое исключение для ошибок API Яндекс Директа."""

    def __init__(self, error: APIError):
        self.error = error
        super().__init__(f"[{error.code}] {error.message}: {error.detail}")


class AuthorizationError(YandexDirectAPIError):
    """Ошибка авторизации."""
    pass


class RateLimitError(YandexDirectAPIError):
    """Превышение лимита запросов."""
    pass


class TemporaryError(YandexDirectAPIError):
    """Временная ошибка, можно повторить."""
    pass


class DataError(YandexDirectAPIError):
    """Ошибка в данных запроса."""
    pass


def parse_api_error(response_data: dict[str, Any]) -> APIError | None:
    """
    Парсинг ошибки из ответа API.

    Args:
        response_data: Ответ API в формате dict

    Returns:
        APIError если есть ошибка, None если ошибок нет
    """
    error_data = response_data.get("error")
    if not error_data:
        return None

    code = error_data.get("error_code", 0)
    message = error_data.get("error_string", "Unknown error")
    detail = error_data.get("error_detail", "")

    category = ERROR_CODES.get(code, ErrorCategory.UNKNOWN)

    # Определяем возможность повтора
    retryable = category in (ErrorCategory.RATE_LIMIT, ErrorCategory.TEMPORARY)

    # Для ошибок лимитов извлекаем время ожидания
    retry_after = None
    if category == ErrorCategory.RATE_LIMIT:
        retry_after = 60  # По умолчанию ждем минуту

    return APIError(
        code=code,
        message=message,
        detail=detail,
        category=category,
        retryable=retryable,
        retry_after=retry_after,
    )


def raise_for_error(response_data: dict[str, Any]) -> None:
    """
    Проверка ответа API на наличие ошибок.

    Args:
        response_data: Ответ API

    Raises:
        AuthorizationError: При ошибках авторизации
        RateLimitError: При превышении лимитов
        TemporaryError: При временных ошибках
        DataError: При ошибках в данных
        YandexDirectAPIError: При неизвестных ошибках
    """
    error = parse_api_error(response_data)
    if not error:
        return

    logger.error(f"API Error: [{error.code}] {error.message} - {error.detail}")

    exception_map = {
        ErrorCategory.AUTHORIZATION: AuthorizationError,
        ErrorCategory.RATE_LIMIT: RateLimitError,
        ErrorCategory.TEMPORARY: TemporaryError,
        ErrorCategory.DATA_ERROR: DataError,
    }

    exception_class = exception_map.get(error.category, YandexDirectAPIError)
    raise exception_class(error)


def handle_http_error(status_code: int, response_text: str) -> None:
    """
    Обработка HTTP ошибок.

    Args:
        status_code: HTTP статус код
        response_text: Текст ответа

    Raises:
        TemporaryError: При 5xx ошибках
        YandexDirectAPIError: При других ошибках
    """
    if 500 <= status_code < 600:
        error = APIError(
            code=status_code,
            message=f"HTTP {status_code}",
            detail=response_text[:200],
            category=ErrorCategory.TEMPORARY,
            retryable=True,
        )
        raise TemporaryError(error)

    error = APIError(
        code=status_code,
        message=f"HTTP Error {status_code}",
        detail=response_text[:200],
        category=ErrorCategory.UNKNOWN,
        retryable=False,
    )
    raise YandexDirectAPIError(error)
