"""
List Command Module.

Handles the /list command - shows user's subscriptions.
"""

from loguru import logger

from src.channels.commands.base import BaseCommand, CommandResult

cmd_log = logger.bind(module="BotCommand")
from src.modules.providers import UserProviderRepository  # noqa: E402
from src.modules.subscriptions import SubscriptionRepository  # noqa: E402


class ListCommand(BaseCommand):
    """List command - shows user's subscriptions."""

    name = "list"
    description = "List subscriptions"
    usage = "/list"

    async def execute(
        self,
        user_id: str,
        args: str,
        context: dict | None = None,
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
            cmd_log.error("Database pool not available for list command")
            return CommandResult.fail("System error, please try again later")

        service = context.get("service", "unknown") if context else "unknown"

        # Check provider binding first
        provider_repo = UserProviderRepository(self._pool)
        provider = await provider_repo.find_by_provider(
            provider=service,
            provider_id=user_id,
        )

        if not provider:
            return CommandResult.fail("尚未綁定帳號。請點擊「開啟管理頁面」按鈕登入。")

        # Get subscriptions
        sub_repo = SubscriptionRepository(self._pool)
        subscriptions = await sub_repo.get_by_user(provider.user_id)

        if not subscriptions:
            return CommandResult.ok(
                message="目前沒有訂閱。",
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
            message=f"找到 {len(sub_list)} 個訂閱。",
            title="list_subscriptions",
            subscriptions=sub_list,
            count=len(sub_list),
        )
