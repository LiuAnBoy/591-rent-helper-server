"""
Status Command Module.

Handles the /status command - shows binding status.
"""

from typing import Optional

from loguru import logger

from src.channels.commands.base import BaseCommand, CommandResult
from src.modules.bindings import BindingRepository


class StatusCommand(BaseCommand):
    """Status command - shows current binding status."""

    name = "status"
    description = "Check binding status"
    usage = "/status"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: Optional[dict] = None,
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
            logger.error("Database pool not available for status command")
            return CommandResult.fail("System error, please try again later")

        service = context.get("service", "unknown") if context else "unknown"

        repo = BindingRepository(self._pool)
        binding = await repo.get_binding_by_service_id(
            service=service,
            service_id=user_id,
        )

        if not binding:
            return CommandResult.ok(
                message="Not bound to any account yet.",
                title="status_unbound",
                is_bound=False,
            )

        return CommandResult.ok(
            message="Account is bound and active.",
            title="status_bound",
            is_bound=True,
            service=service,
            service_id=user_id,
            enabled=binding.enabled,
            created_at=binding.created_at.isoformat() if binding.created_at else None,
        )
