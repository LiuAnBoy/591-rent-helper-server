"""
Base Command Module.

Defines the base command interface and result structure.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from asyncpg import Pool


@dataclass
class CommandResult:
    """
    Structured result from command execution.

    Attributes:
        success: Whether the command executed successfully
        message: Main message to display
        title: Optional title for the message
        data: Additional structured data for formatting
        error: Error message if command failed
    """
    success: bool = True
    message: str = ""
    title: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @classmethod
    def ok(cls, message: str, title: Optional[str] = None, **data) -> "CommandResult":
        """Create a successful result."""
        return cls(success=True, message=message, title=title, data=data)

    @classmethod
    def fail(cls, error: str) -> "CommandResult":
        """Create a failed result."""
        return cls(success=False, error=error)


class BaseCommand(ABC):
    """
    Base class for all commands.

    Commands are platform-agnostic and return structured results.
    Each platform's formatter handles the actual message formatting.
    """

    # Command metadata
    name: str = ""
    description: str = ""
    usage: str = ""

    def __init__(self, pool: Optional[Pool] = None):
        """
        Initialize command.

        Args:
            pool: Database connection pool
        """
        self._pool = pool

    @abstractmethod
    async def execute(
        self,
        user_id: str,
        args: str,
        context: Optional[dict] = None,
    ) -> CommandResult:
        """
        Execute the command.

        Args:
            user_id: Platform-specific user identifier (chat_id, line_id, etc.)
            args: Command arguments
            context: Optional platform-specific context

        Returns:
            CommandResult with structured response data
        """
        pass
