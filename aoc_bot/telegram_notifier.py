"""Telegram bot notifications."""

import asyncio
import logging
from typing import List

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends messages to Telegram chats."""

    def __init__(self, bot_token: str):
        """Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token from @BotFather.
        """
        self.bot = Bot(token=bot_token)

    async def send_message(self, chat_id: str, message: str) -> None:
        """Send a single message to a specific chat.

        Args:
            chat_id: Telegram chat ID where to send the message.
            message: Message text to send.

        Raises:
            TelegramError: If message sending fails.
        """
        try:
            logger.debug(f"Sending message to chat {chat_id}")
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="HTML",
            )
            logger.debug("Message sent successfully")
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
            raise

    async def send_messages(self, chat_id: str, messages: List[str]) -> None:
        """Send multiple messages with rate limiting.

        Args:
            chat_id: Telegram chat ID where to send messages.
            messages: List of message texts to send.
        """
        for i, message in enumerate(messages):
            try:
                await self.send_message(chat_id, message)
                # Add delay between messages to respect Telegram rate limits
                if i < len(messages) - 1:
                    await asyncio.sleep(0.5)
            except TelegramError as e:
                logger.error(
                    f"Failed to send message {i + 1}/{len(messages)} to {chat_id}: {e}"
                )
                # Continue sending remaining messages
