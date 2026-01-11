"""
Bind Command Module (DEPRECATED).

Handles the /bind command - links platform account to user account.
This command is deprecated in favor of Telegram Web App login flow.
"""

from typing import Optional

from loguru import logger

from src.channels.commands.base import BaseCommand, CommandResult
from src.modules.bindings import BindingRepository


class BindCommand(BaseCommand):
    """Bind command - links platform account to user account."""

    name = "bind"
    description = "Bind account"
    usage = "/bind <code>"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: Optional[dict] = None,
    ) -> CommandResult:
        """
        Execute /bind command.

        Args:
            user_id: Platform user ID (e.g., Telegram chat_id)
            args: Bind code
            context: Must contain 'service' key (e.g., 'telegram', 'line')

        Returns:
            Binding result
        """
        if not self._pool:
            logger.error("Database pool not available for bind command")
            return CommandResult.fail("System error, please try again later")

        service = context.get("service", "unknown") if context else "unknown"
        code = args.strip().upper()

        # Validate code
        if not code:
            return CommandResult.fail(
                "Please provide a bind code. Usage: /bind <code>"
            )

        if len(code) != 10:
            return CommandResult.fail(
                "Invalid bind code format. Code should be 10 alphanumeric characters."
            )

        # Verify and bind
        repo = BindingRepository(self._pool)
        bound_user_id = await repo.verify_bind_code(
            service=service,
            code=code,
            service_id=user_id,
        )

        if bound_user_id:
            logger.info(f"Binding successful: {service} user {user_id} -> account {bound_user_id}")
            return CommandResult.ok(
                message="Binding successful! You will now receive rental notifications.",
                title="bind_success",
                bound_user_id=bound_user_id,
            )
        else:
            return CommandResult.fail(
                "Binding failed. The code may be invalid, expired, or this account is already bound."
            )
