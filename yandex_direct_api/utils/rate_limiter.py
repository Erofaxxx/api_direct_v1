"""
Rate Limiter для соблюдения ограничений API Яндекс Директа.

Ограничения:
- Не более 5 запросов в секунду
- Ежедневный лимит на операции (баллы)

Стратегия:
1. Token Bucket алгоритм для контроля частоты запросов
2. Экспоненциальная задержка при ошибках лимита
3. Автоматическое ожидание между запросами
"""

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

logger = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """
    Rate limiter с использованием Token Bucket алгоритма.

    Гарантирует не более max_requests запросов в секунду.
    """

    max_requests: int = 5  # Максимум запросов в секунду
    window_size: float = 1.0  # Размер окна в секундах

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _request_times: list[float] = field(default_factory=list)

    def _cleanup_old_requests(self, current_time: float) -> None:
        """Удаляет записи о запросах старше окна."""
        cutoff = current_time - self.window_size
        self._request_times = [t for t in self._request_times if t > cutoff]

    def wait_if_needed(self) -> float:
        """
        Ожидает, если достигнут лимит запросов.

        Returns:
            Время ожидания в секундах (0 если ожидание не требовалось)
        """
        with self._lock:
            current_time = time.time()
            self._cleanup_old_requests(current_time)

            if len(self._request_times) >= self.max_requests:
                # Нужно подождать до освобождения слота
                oldest_request = min(self._request_times)
                wait_time = oldest_request + self.window_size - current_time

                if wait_time > 0:
                    logger.debug(f"Rate limit: ожидание {wait_time:.3f}с")
                    time.sleep(wait_time)
                    current_time = time.time()
                    self._cleanup_old_requests(current_time)

                    return wait_time

            # Регистрируем новый запрос
            self._request_times.append(time.time())
            return 0.0

    @contextmanager
    def acquire(self) -> Generator[None, None, None]:
        """
        Контекстный менеджер для выполнения запроса с учетом лимитов.

        Usage:
            with rate_limiter.acquire():
                response = make_request()
        """
        self.wait_if_needed()
        yield


class RetryHandler:
    """
    Обработчик повторных попыток с экспоненциальной задержкой.

    Используется при временных ошибках и ошибках лимитов.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        delay_multiplier: float = 2.0,
        max_delay: float = 60.0,
    ):
        """
        Args:
            max_retries: Максимальное количество повторных попыток
            base_delay: Базовая задержка в секундах
            delay_multiplier: Множитель для экспоненциальной задержки
            max_delay: Максимальная задержка в секундах
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.delay_multiplier = delay_multiplier
        self.max_delay = max_delay

    def get_delay(self, attempt: int) -> float:
        """
        Вычисляет задержку для указанной попытки.

        Args:
            attempt: Номер попытки (начиная с 0)

        Returns:
            Задержка в секундах
        """
        delay = self.base_delay * (self.delay_multiplier ** attempt)
        return min(delay, self.max_delay)

    def should_retry(self, attempt: int) -> bool:
        """
        Проверяет, нужно ли делать повторную попытку.

        Args:
            attempt: Номер текущей попытки

        Returns:
            True если можно повторить, False если лимит исчерпан
        """
        return attempt < self.max_retries

    def wait_and_retry(self, attempt: int) -> bool:
        """
        Ожидает перед повторной попыткой.

        Args:
            attempt: Номер текущей попытки

        Returns:
            True если выполнено ожидание, False если лимит исчерпан
        """
        if not self.should_retry(attempt):
            return False

        delay = self.get_delay(attempt)
        logger.info(f"Повторная попытка {attempt + 1}/{self.max_retries} через {delay:.1f}с")
        time.sleep(delay)
        return True


# Глобальный rate limiter
rate_limiter = RateLimiter()
retry_handler = RetryHandler()
