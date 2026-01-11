"""Telegram webhook routes."""

import os
from typing import Optional

from asyncpg import Pool
from fastapi import APIRouter, Request
from loguru import logger
from telegram import Update

from config.settings import get_settings
from src.channels.telegram import TelegramBot, TelegramHandler
from src.connections.postgres import get_postgres

webhook_log = logger.bind(module="Webhook")

router = APIRouter(prefix="/webhook/telegram", tags=["Telegram"])

# Telegram bot and handler instances
_bot: Optional[TelegramBot] = None
_handler: Optional[TelegramHandler] = None


async def init_bot() -> Optional[TelegramBot]:
    """Initialize Telegram bot and handler."""
    global _bot, _handler
    settings = get_settings()

    if not settings.telegram.bot_token:
        webhook_log.warning("Telegram bot token not configured")
        return None

    # Initialize bot
    _bot = TelegramBot.init(settings.telegram.bot_token)

    if not _bot.is_configured:
        webhook_log.warning("Telegram bot failed to initialize")
        return None

    # Get database pool for handler
    postgres = await get_postgres()

    # Initialize handler with database pool
    _handler = TelegramHandler(bot=_bot, pool=postgres.pool)

    # Log bot info
    if _bot.bot:
        bot_info = await _bot.bot.get_me()
        webhook_log.info(f"Telegram bot initialized: @{bot_info.username}")

    return _bot


def get_bot() -> Optional[TelegramBot]:
    """Get bot instance."""
    return _bot


def get_handler() -> Optional[TelegramHandler]:
    """Get handler instance."""
    return _handler


@router.post("")
async def telegram_webhook(request: Request) -> dict:
    """Handle Telegram webhook updates."""
    if not _bot or not _bot.is_configured:
        webhook_log.warning("Telegram bot not initialized")
        return {"status": False, "error": "Bot not configured"}

    if not _handler:
        webhook_log.warning("Telegram handler not initialized")
        return {"status": False, "error": "Handler not configured"}

    try:
        data = await request.json()
        update = Update.de_json(data, _bot.bot)

        # Route to handler
        await _handler.handle_update(update)

        return {"status": True}

    except Exception as e:
        webhook_log.error(f"Webhook error: {e}")
        return {"status": False, "error": str(e)}


@router.post("/setup")
async def setup_telegram_webhook() -> dict:
    """Setup Telegram webhook URL."""
    if not _bot or not _bot.bot:
        return {"status": False, "error": "Bot not configured"}

    settings = get_settings()
    webhook_url = settings.telegram.webhook_url

    if not webhook_url:
        return {"status": False, "error": "TELEGRAM_WEBHOOK_URL not configured"}

    full_url = f"{webhook_url}/webhook/telegram"

    try:
        await _bot.bot.set_webhook(url=full_url)
        webhook_log.info(f"Webhook set to: {full_url}")
        return {"status": True, "webhook_url": full_url}
    except Exception as e:
        webhook_log.error(f"Failed to set webhook: {e}")
        return {"status": False, "error": str(e)}


async def auto_setup_webhook() -> bool:
    """
    Auto setup webhook on startup.
    
    Returns:
        True if setup successful, False otherwise
    """
    if not _bot or not _bot.bot:
        webhook_log.warning("Cannot auto-setup webhook: bot not configured")
        return False

    settings = get_settings()
    webhook_url = settings.telegram.webhook_url

    if not webhook_url:
        webhook_log.warning("Cannot auto-setup webhook: TELEGRAM_WEBHOOK_URL not configured")
        return False

    full_url = f"{webhook_url}/webhook/telegram"

    try:
        await _bot.bot.set_webhook(url=full_url)
        webhook_log.info(f"Webhook auto-setup complete: {full_url}")
        return True
    except Exception as e:
        webhook_log.error(f"Failed to auto-setup webhook: {e}")
        return False


@router.delete("")
async def delete_telegram_webhook() -> dict:
    """Delete Telegram webhook (switch to polling mode)."""
    if not _bot or not _bot.bot:
        return {"status": False, "error": "Bot not configured"}

    try:
        await _bot.bot.delete_webhook()
        webhook_log.info("Webhook deleted")
        return {"status": True, "message": "Webhook deleted"}
    except Exception as e:
        webhook_log.error(f"Failed to delete webhook: {e}")
        return {"status": False, "error": str(e)}


@router.get("/info")
async def get_telegram_webhook_info() -> dict:
    """Get current Telegram webhook info."""
    if not _bot or not _bot.bot:
        return {"status": False, "error": "Bot not configured"}

    try:
        info = await _bot.bot.get_webhook_info()
        return {
            "status": True,
            "webhook": {
                "url": info.url,
                "has_custom_certificate": info.has_custom_certificate,
                "pending_update_count": info.pending_update_count,
                "last_error_date": info.last_error_date,
                "last_error_message": info.last_error_message,
            },
        }
    except Exception as e:
        webhook_log.error(f"Failed to get webhook info: {e}")
        return {"status": False, "error": str(e)}
