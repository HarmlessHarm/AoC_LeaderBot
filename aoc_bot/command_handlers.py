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
    welcome = """🤖 **Advent of Code Leaderboard Bot**

I monitor your private AoC leaderboards and notify you of updates!

**Admin Commands:**
/add_leaderboard <id> <cookie> [year] - Add a leaderboard to monitor
/remove_leaderboard <id> [year] - Stop monitoring a leaderboard

**Everyone Can Use:**
/list_leaderboards - Show configured leaderboards
/status - Show monitoring status
/help - Show detailed help

For more information, use /help"""

    await update.message.reply_text(welcome, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command.

    Args:
        update: Telegram update.
        context: Command context.
    """
    help_text = """**How to use the bot:**

1️⃣ **Add a leaderboard** (admin only):
   `/add_leaderboard <leaderboard_id> <session_cookie> [year]`

   Example:
   `/add_leaderboard 123456 session=abc123def456 2024`

   Where:
   - `leaderboard_id` is your AoC private leaderboard ID
   - `session_cookie` is your AoC session cookie (get it from browser DevTools)
   - `year` is optional (defaults to current year)

2️⃣ **View leaderboards** (everyone):
   `/list_leaderboards` - Show all configured leaderboards

3️⃣ **Check status** (everyone):
   `/status` - Show monitoring status and next poll time

4️⃣ **Remove a leaderboard** (admin only):
   `/remove_leaderboard <leaderboard_id> [year]`

**Getting your session cookie:**
1. Log into adventofcode.com in your browser
2. Open DevTools (F12)
3. Go to Application → Cookies → adventofcode.com
4. Copy the value of the "session" cookie

**More help:**
Use /start for a quick overview"""

    await update.message.reply_text(help_text, parse_mode="Markdown")


@admin_only
async def add_leaderboard_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /add_leaderboard command.

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
            "Usage: /add_leaderboard <leaderboard_id> <session_cookie> [year]\n\n"
            "Example: /add_leaderboard 123456 session=abc123 2024"
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

    if not session_cookie.startswith("session="):
        await update.message.reply_text("❌ Session cookie should start with 'session='")
        return

    if year < 2015 or year > datetime.now().year:
        await update.message.reply_text(
            f"❌ Year must be between 2015 and {datetime.now().year}"
        )
        return

    # Check if already exists
    try:
        if await db.config_exists(chat_id, leaderboard_id, year):
            await update.message.reply_text(
                f"❌ Leaderboard {leaderboard_id} ({year}) is already configured."
            )
            return
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

    # Parse arguments
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /remove_leaderboard <leaderboard_id> [year]\n\n"
            "Example: /remove_leaderboard 123456 2024"
        )
        return

    leaderboard_id = context.args[0]
    year = int(context.args[1]) if len(context.args) > 1 else datetime.now().year
    chat_id = str(update.effective_chat.id)

    # Validate inputs
    if not leaderboard_id.isdigit():
        await update.message.reply_text("❌ Leaderboard ID must be numeric.")
        return

    # Check if config exists
    try:
        config = await db.get_config(chat_id, leaderboard_id, year)
        if not config:
            await update.message.reply_text(
                f"❌ Leaderboard {leaderboard_id} ({year}) not found."
            )
            return
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        await update.message.reply_text("❌ Database error. Try again later.")
        return

    # Stop monitoring
    try:
        await polling_mgr.remove_leaderboard(chat_id, leaderboard_id, year)
    except Exception as e:
        logger.error(f"Failed to stop monitoring: {e}")
        await update.message.reply_text("❌ Failed to stop monitoring. Try again later.")
        return

    # Remove from database
    try:
        await db.remove_config(chat_id, leaderboard_id, year)
    except Exception as e:
        logger.error(f"Failed to remove config: {e}")
        await update.message.reply_text("❌ Database error. Try again later.")
        return

    await update.message.reply_text(
        f"✅ Leaderboard {leaderboard_id} ({year}) removed.\n"
        "Monitoring stopped."
    )


async def list_leaderboards_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /list_leaderboards command.

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

    try:
        configs = await db.get_configs_for_chat(chat_id)
    except Exception as e:
        logger.error(f"Failed to get configs: {e}")
        await update.message.reply_text("❌ Database error. Try again later.")
        return

    if not configs:
        await update.message.reply_text(
            "No leaderboards configured yet.\n\n"
            "Use /add_leaderboard to add one!"
        )
        return

    lines = ["📊 **Configured Leaderboards**\n"]
    for config in configs:
        status = "🟢 Active" if config.enabled else "🔴 Disabled"
        lines.append(
            f"{status} - ID: {config.leaderboard_id} (Year {config.year})\n"
            f"   Poll interval: {config.poll_interval}s"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


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


def register_handlers(
    application, db_manager: DatabaseManager, polling_manager: PollingManager
) -> None:
    """Register all command handlers.

    Args:
        application: Telegram Application.
        db_manager: Database manager instance.
        polling_manager: Polling manager instance.
    """
    # Store shared objects in bot_data
    application.bot_data["database"] = db_manager
    application.bot_data["polling_manager"] = polling_manager

    # Register command handlers
    from telegram.ext import CommandHandler

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add_leaderboard", add_leaderboard_command))
    application.add_handler(
        CommandHandler("remove_leaderboard", remove_leaderboard_command)
    )
    application.add_handler(
        CommandHandler("list_leaderboards", list_leaderboards_command)
    )
    application.add_handler(CommandHandler("status", status_command))

    logger.info("Command handlers registered")
