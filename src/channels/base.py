"""
Base Channel Module.

Defines base interfaces for notification channels.
"""

from abc import ABC, abstractmethod
from typing import Any

from asyncpg import Pool

from src.channels.commands.base import CommandResult


class BaseFormatter(ABC):
    """
    Base class for message formatters.

    Each platform implements its own formatter to convert
    CommandResult into platform-specific message format.
    """

    @abstractmethod
    def format_command_result(self, result: CommandResult) -> str:
        """
        Format a command result into a message string.

        Args:
            result: CommandResult from command execution

        Returns:
            Formatted message string for the platform
        """
        pass

    @abstractmethod
    def format_object(self, obj: Any) -> str:
        """
        Format a rental object for notification.

        Args:
            obj: RentalObject to format

        Returns:
            Formatted object message
        """
        pass


class BaseChannel(ABC):
    """
    Base class for notification channels.

    Each platform (Telegram, LINE, Discord, etc.) implements
    this interface for handling messages and sending notifications.
    """

    # Channel identifier
    service_name: str = ""

    def __init__(self, pool: Pool | None = None):
        """
        Initialize channel.

        Args:
            pool: Database connection pool
        """
        self._pool = pool
        self._formatter: BaseFormatter | None = None

    @property
    @abstractmethod
    def formatter(self) -> BaseFormatter:
        """Get the formatter for this channel."""
        pass

    @abstractmethod
    async def send_message(self, user_id: str, message: str) -> bool:
        """
        Send a message to a user.

        Args:
            user_id: Platform-specific user ID
            message: Message to send

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    async def handle_message(self, user_id: str, text: str) -> str | None:
        """
        Handle an incoming message from a user.

        Args:
            user_id: Platform-specific user ID
            text: Message text

        Returns:
            Response message or None
        """
        pass
