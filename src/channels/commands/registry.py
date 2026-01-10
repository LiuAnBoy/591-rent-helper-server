"""
Command Registry Module.

Central registry for all available commands.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.channels.commands.base import BaseCommand

# Import commands (will be populated after command files are created)
from src.channels.commands.start import StartCommand
from src.channels.commands.help import HelpCommand
from src.channels.commands.bind import BindCommand
from src.channels.commands.status import StatusCommand
from src.channels.commands.list import ListCommand


# Command registry: name -> command class
# Includes aliases (e.g., Chinese names)
COMMANDS: dict[str, type["BaseCommand"]] = {
    # Start
    "start": StartCommand,
    # Help + alias
    "help": HelpCommand,
    "幫助": HelpCommand,
    # Bind
    "bind": BindCommand,
    # Status
    "status": StatusCommand,
    # List + alias
    "list": ListCommand,
    "清單": ListCommand,
}


def get_command(name: str) -> Optional[type["BaseCommand"]]:
    """
    Get command class by name.

    Args:
        name: Command name (without leading /)

    Returns:
        Command class or None if not found
    """
    return COMMANDS.get(name.lower())


def parse_command(text: str) -> Optional[tuple[str, str]]:
    """
    Parse text to extract command and arguments.

    Supports:
    - /command args (standard format)
    - /command@botname args (Telegram format)
    - 中文指令 args (Chinese command without /)

    Args:
        text: Raw message text

    Returns:
        Tuple of (command_name, args) if command found, None otherwise
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Check if starts with /
    if text.startswith("/"):
        text = text[1:]  # Remove leading /

    # Split into command and args
    parts = text.split(maxsplit=1)
    command_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    # Handle @bot suffix (e.g., start@mybot)
    if "@" in command_name:
        command_name = command_name.split("@")[0]

    # Check if it's a registered command
    if command_name in COMMANDS:
        return (command_name, args)

    return None
