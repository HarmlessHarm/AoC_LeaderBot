"""Telegram bot command handlers."""

import asyncio
import functools
import logging
from datetime import datetime

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from aoc_bot.aoc_api import AoCAPIClient, AoCAPIError
from aoc_bot.database import DatabaseManager
from aoc_bot.message_formatter import MessageFormatter
from aoc_bot.polling_manager import PollingManager

logger = logging.getLogger(__name__)


def admin_only(func):
    """Decorator to restrict command to chat administrators.

    Args:
        func: Async command handler function.

    Returns:
        Wrapped function that checks admin status.
    """

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await is_user_admin(update, context):
            await update.message.reply_text(
                "❌ This command is only available to chat administrators."
            )
            return

        return await func(update, context)

    return wrapper


async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is a chat administrator.

    Args:
        update: Telegram update.
        context: Command context.

    Returns:
        True if user is admin, False otherwise.
    """
    # Private chats: user is always admin
    if update.effective_chat.type == "private":
        return True

    # Groups/supergroups: check admin list
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        user_id = update.effective_user.id
        return any(admin.user.id == user_id for admin in admins)
    except TelegramError:
        logger.error("Failed to check admin status")
        return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command.

    Args:
        update: Telegram update.
        context: Command context.
    """
    welcome = """🤖 Advent of Code Leaderboard Bot

I monitor your private AoC leaderboards and notify you of updates!

Admin Commands:
/set_leaderboard <id> <cookie> [year] - Set leaderboard
/remove_leaderboard - Stop monitoring

Everyone Can Use:
/rankings - Show current rankings
/status - Show monitoring status
/help - Show detailed help

For more information, use /help"""

    await update.message.reply_text(welcome)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command.

    Args:
        update: Telegram update.
        context: Command context.
    """
    help_text = r"""How to use the bot:

1️⃣ Set a leaderboard (admin only):
   /set_leaderboard <leaderboard_id> <session_cookie> [year]

   Example:
   /set_leaderboard 123456 abc123def456 2024

   Where:
   - leaderboard_id is your AoC private leaderboard ID
   - session_cookie is your AoC session cookie (get it from browser DevTools)
   - year is optional (defaults to current year)

   Note: Each chat can only have one leaderboard. Setting a new one replaces the old one.

2️⃣ View current rankings (everyone):
   /rankings - Show rankings for your chat's leaderboard

3️⃣ Check status (everyone):
   /status - Show monitoring status and next poll time

4️⃣ Remove the leaderboard (admin only):
   /remove_leaderboard - Stop monitoring this chat's leaderboard

Quick Setup:
1. Go to your private leaderboard on adventofcode.com
2. Note the leaderboard ID from the URL (example.com/view/12345)
3. Open DevTools (F12)
4. Go to Application → Cookies → adventofcode.com
5. Find the "session" cookie and copy its value
6. Send this command to the bot:
   /set_leaderboard <leaderboard_id> <session_cookie>

   Example: /set_leaderboard 12345 abc123def456xyz789..."""

    await update.message.reply_text(help_text)


@admin_only
async def set_leaderboard_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /set_leaderboard command.

    Args:
        update: Telegram update.
        context: Command context.
    """
    # Get components from context
    db: DatabaseManager = context.bot_data.get("database")
    polling_mgr: PollingManager = context.bot_data.get("polling_manager")

    if not db or not polling_mgr:
        await update.message.reply_text("❌ Bot not fully initialized. Try again later.")
        return

    # Parse arguments
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /set_leaderboard <leaderboard_id> <session_cookie> [year]\n\n"
            "Example: /set_leaderboard 123456 abc123def456 2024"
        )
        return

    leaderboard_id = context.args[0]
    session_cookie = context.args[1]
    year = int(context.args[2]) if len(context.args) > 2 else datetime.now().year
    chat_id = str(update.effective_chat.id)

    # Validate inputs
    if not leaderboard_id.isdigit():
        await update.message.reply_text("❌ Leaderboard ID must be numeric.")
        return

    # Automatically add session= prefix if not present
    if not session_cookie.startswith("session="):
        session_cookie = f"session={session_cookie}"

    if year < 2015 or year > datetime.now().year:
        await update.message.reply_text(
            f"❌ Year must be between 2015 and {datetime.now().year}"
        )
        return

    # Check if already exists (we'll update it if it does)
    try:
        existing = await db.get_config_for_chat(chat_id)
        if existing:
            await update.message.reply_text(
                f"ℹ️ Replacing previous leaderboard configuration..."
            )
    except Exception as e:
        logger.error(f"Failed to check config existence: {e}")
        await update.message.reply_text("❌ Database error. Try again later.")
        return

    # Test AoC API connection
    await update.message.reply_text("⏳ Testing connection to Advent of Code...")

    try:
        test_client = AoCAPIClient(session_cookie, year, leaderboard_id)
        # Run in thread to avoid blocking
        await asyncio.to_thread(test_client.fetch_leaderboard)
    except AoCAPIError as e:
        logger.warning(f"Failed to connect to AoC: {e}")
        await update.message.reply_text(
            f"❌ Failed to connect to AoC:\n{e}\n\n"
            "Please check:\n"
            "1. Your session cookie is correct\n"
            "2. Your leaderboard ID is correct\n"
            "3. You have access to the private leaderboard"
        )
        return
    except Exception as e:
        logger.error(f"Unexpected error testing AoC connection: {e}")
        await update.message.reply_text("❌ Connection test failed. Try again later.")
        return

    # Add to database
    try:
        await db.add_config(chat_id, leaderboard_id, session_cookie, year)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}")
        return
    except Exception as e:
        logger.error(f"Failed to add config: {e}")
        await update.message.reply_text("❌ Database error. Try again later.")
        return

    # Start monitoring
    try:
        await polling_mgr.add_leaderboard(chat_id, leaderboard_id, year)
    except Exception as e:
        logger.error(f"Failed to start monitoring: {e}")
        # Remove from database if monitoring start failed
        await db.remove_config(chat_id, leaderboard_id, year)
        await update.message.reply_text(
            "❌ Failed to start monitoring. Please try again."
        )
        return

    await update.message.reply_text(
        f"✅ Leaderboard {leaderboard_id} ({year}) configured!\n\n"
        "🎉 Monitoring started. You'll receive updates when the leaderboard changes.\n\n"
        "Use /status to see monitoring details."
    )

    # Fetch and post current rankings
    try:
        leaderboard_client = AoCAPIClient(session_cookie, year, leaderboard_id)
        leaderboard_data = await asyncio.to_thread(
            leaderboard_client.fetch_leaderboard
        )
        ranking_messages = MessageFormatter.format_leaderboard(leaderboard_data, year)
        for message in ranking_messages:
            await update.message.reply_text(message)
    except Exception as e:
        logger.warning(f"Failed to fetch initial rankings: {e}")
        # Don't fail the entire command if we can't fetch rankings
        pass


@admin_only
async def remove_leaderboard_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /remove_leaderboard command.

    Args:
        update: Telegram update.
        context: Command context.
    """
    # Get components from context
    db: DatabaseManager = context.bot_data.get("database")
    polling_mgr: PollingManager = context.bot_data.get("polling_manager")

    if not db or not polling_mgr:
        await update.message.reply_text("❌ Bot not fully initialized. Try again later.")
        return

    chat_id = str(update.effective_chat.id)

    # Check if config exists
    try:
        config = await db.get_config_for_chat(chat_id)
        if not config:
            await update.message.reply_text(
                "❌ No leaderboard configured for this chat."
            )
            return
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        await update.message.reply_text("❌ Database error. Try again later.")
        return

    # Stop monitoring
    try:
        await polling_mgr.remove_leaderboard(
            chat_id, config.leaderboard_id, config.year
        )
    except Exception as e:
        logger.error(f"Failed to stop monitoring: {e}")
        await update.message.reply_text("❌ Failed to stop monitoring. Try again later.")
        return

    # Remove from database
    try:
        await db.remove_config(chat_id)
    except Exception as e:
        logger.error(f"Failed to remove config: {e}")
        await update.message.reply_text("❌ Database error. Try again later.")
        return

    await update.message.reply_text(
        "✅ Leaderboard removed.\nMonitoring stopped."
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command.

    Args:
        update: Telegram update.
        context: Command context.
    """
    # Get components from context
    db: DatabaseManager = context.bot_data.get("database")
    polling_mgr: PollingManager = context.bot_data.get("polling_manager")

    if not db or not polling_mgr:
        await update.message.reply_text("❌ Bot not fully initialized. Try again later.")
        return

    chat_id = str(update.effective_chat.id)

    try:
        configs = await db.get_configs_for_chat(chat_id)
    except Exception as e:
        logger.error(f"Failed to get configs: {e}")
        await update.message.reply_text("❌ Database error. Try again later.")
        return

    if not configs:
        await update.message.reply_text(
            "No leaderboards configured.\n"
            "Use /add_leaderboard to add one!"
        )
        return

    lines = ["📊 **Bot Status**\n"]

    for config in configs:
        task_key = (chat_id, config.leaderboard_id, config.year)
        task_status = polling_mgr.get_task_status(task_key)

        lines.append(
            f"**Leaderboard {config.leaderboard_id}** ({config.year})\n"
            f"Status: "
        )

        if task_status:
            lines[-1] += task_status.status.upper()

            if task_status.last_poll:
                lines.append(
                    f"Last poll: {task_status.last_poll.strftime('%Y-%m-%d %H:%M:%S')}"
                )

            if task_status.next_poll:
                lines.append(
                    f"Next poll: {task_status.next_poll.strftime('%Y-%m-%d %H:%M:%S')}"
                )

            if task_status.error_message:
                lines.append(f"⚠️ Error: {task_status.error_message}")

            if task_status.error_count > 0:
                lines.append(f"Error count: {task_status.error_count}")
        else:
            lines[-1] += "UNKNOWN"

        lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def rankings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /rankings command (no parameters needed).

    Args:
        update: Telegram update.
        context: Command context.
    """
    # Get database from context
    db: DatabaseManager = context.bot_data.get("database")

    if not db:
        await update.message.reply_text("❌ Bot not fully initialized. Try again later.")
        return

    chat_id = str(update.effective_chat.id)

    # Check if config exists for this chat
    try:
        config = await db.get_config_for_chat(chat_id)
        if not config:
            await update.message.reply_text(
                "❌ No leaderboard configured for this chat.\n"
                "Use /add_leaderboard to add one."
            )
            return
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        await update.message.reply_text("❌ Database error. Try again later.")
        return

    # Fetch and display rankings
    try:
        await update.message.reply_text("⏳ Fetching leaderboard rankings...")
        leaderboard_client = AoCAPIClient(
            config.session_cookie, config.year, config.leaderboard_id
        )
        leaderboard_data = await asyncio.to_thread(
            leaderboard_client.fetch_leaderboard
        )
        ranking_messages = MessageFormatter.format_leaderboard(
            leaderboard_data, config.year
        )
        for message in ranking_messages:
            await update.message.reply_text(message)
    except AoCAPIError as e:
        logger.warning(f"Failed to fetch rankings: {e}")
        await update.message.reply_text(f"❌ Failed to fetch rankings:\n{e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching rankings: {e}")
        await update.message.reply_text("❌ Failed to fetch rankings. Try again later.")


async def register_handlers(
    application, db_manager: DatabaseManager, polling_manager: PollingManager
) -> None:
    """Register all command handlers and set up autocomplete.

    Args:
        application: Telegram Application.
        db_manager: Database manager instance.
        polling_manager: Polling manager instance.
    """
    # Store shared objects in bot_data
    application.bot_data["database"] = db_manager
    application.bot_data["polling_manager"] = polling_manager

    # Register command handlers
    from telegram import BotCommand
    from telegram.ext import CommandHandler

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("set_leaderboard", set_leaderboard_command))
    application.add_handler(
        CommandHandler("remove_leaderboard", remove_leaderboard_command)
    )
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("rankings", rankings_command))

    # Set up command autocomplete
    commands = [
        BotCommand("start", "Welcome message"),
        BotCommand("help", "Show detailed help"),
        BotCommand("set_leaderboard", "Set leaderboard (admin only)"),
        BotCommand("remove_leaderboard", "Stop monitoring (admin only)"),
        BotCommand("rankings", "Show current rankings"),
        BotCommand("status", "Show monitoring status"),
    ]

    try:
        await application.bot.set_my_commands(commands)
        logger.info("Command autocomplete registered")
    except Exception as e:
        logger.warning(f"Failed to set command autocomplete: {e}")

    logger.info("Command handlers registered")
