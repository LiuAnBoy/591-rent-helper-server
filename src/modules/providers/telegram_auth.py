"""Telegram Web App authentication verification."""

import hashlib
import hmac
import json
from urllib.parse import parse_qs, parse_qsl, unquote

from loguru import logger

from src.modules.providers.models import TelegramAuthData, TelegramUser

tgauth_log = logger.bind(module="TgAuth")


def verify_init_data(init_data: str, bot_token: str) -> bool:
    """
    Verify Telegram Web App initData using HMAC-SHA-256.

    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

    Args:
        init_data: Raw initData string from Telegram Web App
        bot_token: Telegram bot token

    Returns:
        True if valid, False otherwise
    """
    try:
        # Parse with URL decoding (parse_qsl decodes values automatically)
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))

        # Extract and remove hash
        received_hash = parsed.pop("hash", "")
        if not received_hash:
            tgauth_log.warning("No hash in initData")
            return False

        # Build data check string (sorted alphabetically)
        # Values are URL-decoded by parse_qsl
        data_pairs = [f"{k}={v}" for k, v in sorted(parsed.items())]
        data_check_string = "\n".join(data_pairs)

        # Calculate secret key: HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode(), hashlib.sha256
        ).digest()

        # Calculate hash: HMAC-SHA256(secret_key, data_check_string)
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        is_valid = calculated_hash == received_hash

        if not is_valid:
            tgauth_log.warning("Invalid initData hash")

        return is_valid

    except Exception as e:
        tgauth_log.error(f"Error verifying initData: {e}")
        return False


def parse_init_data(init_data: str) -> TelegramAuthData | None:
    """
    Parse Telegram Web App initData into structured data.

    Args:
        init_data: Raw initData string from Telegram Web App

    Returns:
        TelegramAuthData if valid, None otherwise
    """
    try:
        parsed = parse_qs(init_data)

        # Parse user data (URL encoded JSON)
        user_str = parsed.get("user", [""])[0]
        if not user_str:
            tgauth_log.warning("No user in initData")
            return None

        user_data = json.loads(unquote(user_str))
        user = TelegramUser(**user_data)

        # Parse other fields
        auth_date = int(parsed.get("auth_date", ["0"])[0])
        hash_value = parsed.get("hash", [""])[0]

        return TelegramAuthData(
            user=user,
            auth_date=auth_date,
            hash=hash_value,
            query_id=parsed.get("query_id", [None])[0],
            chat_type=parsed.get("chat_type", [None])[0],
            chat_instance=parsed.get("chat_instance", [None])[0],
        )

    except Exception as e:
        tgauth_log.error(f"Error parsing initData: {e}")
        return None


def verify_and_parse_init_data(
    init_data: str, bot_token: str, max_age_seconds: int = 3600
) -> TelegramAuthData | None:
    """
    Verify and parse Telegram Web App initData.

    Args:
        init_data: Raw initData string from Telegram Web App
        bot_token: Telegram bot token
        max_age_seconds: Maximum age of auth data (default: 1 hour)

    Returns:
        TelegramAuthData if valid and not expired, None otherwise
    """
    # Verify hash
    if not verify_init_data(init_data, bot_token):
        tgauth_log.warning("verify_init_data returned False")
        return None

    # Parse data
    auth_data = parse_init_data(init_data)
    if not auth_data:
        tgauth_log.warning("parse_init_data returned None")
        return None

    # Check expiry
    if auth_data.is_expired(max_age_seconds):
        tgauth_log.warning(f"initData expired (auth_date: {auth_data.auth_date})")
        return None

    tgauth_log.debug(f"initData verified successfully for user {auth_data.user.id}")
    return auth_data
