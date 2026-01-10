"""
Shared Commands Module.

Platform-agnostic command implementations.
"""

from src.channels.commands.base import BaseCommand, CommandResult
from src.channels.commands.registry import COMMANDS, get_command, parse_command

__all__ = [
    "BaseCommand",
    "CommandResult",
    "COMMANDS",
    "get_command",
    "parse_command",
]
