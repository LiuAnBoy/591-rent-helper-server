"""
Status Command Module.

Handles the /status command - shows binding status.
"""

from loguru import logger

from src.channels.commands.base import BaseCommand, CommandResult

cmd_log = logger.bind(module="BotCommand")
from src.modules.providers import UserProviderRepository  # noqa: E402


class StatusCommand(BaseCommand):
    """Status command - shows current binding status."""

    name = "status"
    description = "Check binding status"
    usage = "/status"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: dict | None = None,
    ) -> CommandResult:
        """
        Execute /status command.

        Args:
            user_id: Platform user ID
            args: Command arguments (unused)
            context: Must contain 'service' key

        Returns:
            Binding status information
        """
        if not self._pool:
            cmd_log.error("Database pool not available for status command")
            return CommandResult.fail("System error, please try again later")

        service = context.get("service", "unknown") if context else "unknown"

        repo = UserProviderRepository(self._pool)
        provider = await repo.find_by_provider(
            provider=service,
            provider_id=user_id,
        )

        if not provider:
            return CommandResult.ok(
                message="尚未綁定帳號。請點擊「開啟管理頁面」按鈕登入。",
                title="status_unbound",
                is_bound=False,
            )

        return CommandResult.ok(
            message="帳號已綁定。",
            title="status_bound",
            is_bound=True,
            service=service,
            service_id=user_id,
            enabled=provider.notify_enabled,
            created_at=provider.created_at.isoformat() if provider.created_at else None,
        )
