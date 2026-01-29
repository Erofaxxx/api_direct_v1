"""
Базовый класс агента для мультиагентной системы.

Архитектура системы:
┌─────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                            │
│                   (Координатор агентов)                      │
└─────────────────────┬───────────────────┬───────────────────┘
                      │                   │
          ┌───────────▼───────┐ ┌─────────▼─────────┐
          │  DirectAgent      │ │   MLAnalystAgent  │
          │  (Яндекс Директ)  │ │   (Claude API)    │
          └───────────────────┘ └───────────────────┘
                      │                   │
                      ▼                   ▼
              ┌───────────────────────────────┐
              │         SHARED DATA           │
              │    (PostgreSQL / Files)       │
              └───────────────────────────────┘
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Статусы агента."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    WAITING = "waiting"


class MessageType(Enum):
    """Типы сообщений между агентами."""
    TASK = "task"
    RESULT = "result"
    ERROR = "error"
    STATUS = "status"
    DATA = "data"


@dataclass
class AgentMessage:
    """Сообщение между агентами."""
    id: str = field(default_factory=lambda: str(uuid4()))
    type: MessageType = MessageType.TASK
    sender: str = ""
    receiver: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "sender": self.sender,
            "receiver": self.receiver,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TaskResult:
    """Результат выполнения задачи."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time: float = 0.0


class BaseAgent(ABC):
    """
    Базовый класс для всех агентов системы.

    Каждый агент:
    - Имеет уникальное имя
    - Может выполнять задачи асинхронно
    - Общается с другими агентами через сообщения
    - Логирует свои действия
    """

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        self.name = name
        self.config = config or {}
        self.status = AgentStatus.IDLE
        self._message_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._running = False

        self.logger = logging.getLogger(f"agent.{name}")
        self.logger.info(f"Агент '{name}' инициализирован")

    @abstractmethod
    async def execute_task(self, task: dict[str, Any]) -> TaskResult:
        """
        Выполнение основной задачи агента.

        Args:
            task: Параметры задачи

        Returns:
            Результат выполнения
        """
        pass

    @abstractmethod
    async def process_message(self, message: AgentMessage) -> AgentMessage | None:
        """
        Обработка входящего сообщения.

        Args:
            message: Входящее сообщение

        Returns:
            Ответное сообщение (если требуется)
        """
        pass

    async def send_message(self, receiver: str, msg_type: MessageType, payload: dict) -> AgentMessage:
        """Отправка сообщения другому агенту."""
        message = AgentMessage(
            type=msg_type,
            sender=self.name,
            receiver=receiver,
            payload=payload,
        )
        self.logger.debug(f"Отправка сообщения: {self.name} -> {receiver}")
        return message

    async def receive_message(self, message: AgentMessage) -> None:
        """Получение сообщения в очередь."""
        await self._message_queue.put(message)

    async def start(self) -> None:
        """Запуск агента."""
        self._running = True
        self.status = AgentStatus.RUNNING
        self.logger.info(f"Агент '{self.name}' запущен")

    async def stop(self) -> None:
        """Остановка агента."""
        self._running = False
        self.status = AgentStatus.IDLE
        self.logger.info(f"Агент '{self.name}' остановлен")

    async def run_loop(self) -> None:
        """Основной цикл обработки сообщений."""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                response = await self.process_message(message)
                if response:
                    # Ответ будет обработан оркестратором
                    pass
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Ошибка в цикле агента: {e}")
                self.status = AgentStatus.ERROR

    def get_status(self) -> dict[str, Any]:
        """Получение статуса агента."""
        return {
            "name": self.name,
            "status": self.status.value,
            "queue_size": self._message_queue.qsize(),
        }
