"""
List Command Module.

Handles the /list command - shows user's subscriptions.
"""

from typing import Optional

from loguru import logger

from src.channels.commands.base import BaseCommand, CommandResult
from src.modules.bindings import BindingRepository
from src.modules.subscriptions import SubscriptionRepository


class ListCommand(BaseCommand):
    """List command - shows user's subscriptions."""

    name = "list"
    description = "List subscriptions"
    usage = "/list"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: Optional[dict] = None,
    ) -> CommandResult:
        """
        Execute /list command.

        Args:
            user_id: Platform user ID
            args: Command arguments (unused)
            context: Must contain 'service' key

        Returns:
            List of user's subscriptions
        """
        if not self._pool:
            logger.error("Database pool not available for list command")
            return CommandResult.fail("System error, please try again later")

        service = context.get("service", "unknown") if context else "unknown"

        # Check binding first
        binding_repo = BindingRepository(self._pool)
        binding = await binding_repo.get_binding_by_service_id(
            service=service,
            service_id=user_id,
        )

        if not binding:
            return CommandResult.fail(
                "Not bound to any account. Use /bind <code> first."
            )

        # Get subscriptions
        sub_repo = SubscriptionRepository(self._pool)
        subscriptions = await sub_repo.get_by_user(binding.user_id)

        if not subscriptions:
            return CommandResult.ok(
                message="No subscriptions found.",
                title="list_empty",
                subscriptions=[],
                count=0,
            )

        # Format subscription data
        sub_list = []
        for sub in subscriptions:
            sub_data = {
                "id": sub.get("id"),
                "name": sub.get("name", f"Subscription {sub['id']}"),
                "enabled": sub.get("enabled", False),
                "region": sub.get("region"),
                "price_min": sub.get("price_min"),
                "price_max": sub.get("price_max"),
                "kind": sub.get("kind"),
            }
            sub_list.append(sub_data)

        return CommandResult.ok(
            message=f"Found {len(sub_list)} subscription(s).",
            title="list_subscriptions",
            subscriptions=sub_list,
            count=len(sub_list),
        )
