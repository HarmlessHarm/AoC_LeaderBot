"""Entry point for the Advent of Code Telegram Bot (Multi-Chat)."""

import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram.ext import ApplicationBuilder

from aoc_bot.command_handlers import register_handlers
from aoc_bot.config import BotConfig, parse_args
from aoc_bot.database import DatabaseManager
from aoc_bot.polling_manager import PollingManager


def setup_logging(log_file: Path) -> logging.Logger:
    """Setup logging configuration.

    Args:
        log_file: Path to log file.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger("aoc_bot")
    logger.setLevel(logging.DEBUG)

    # Create formatters
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler with rotation
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10_000_000,  # 10 MB
        backupCount=5,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


async def main_async(config: BotConfig) -> None:
    """Main async entry point.

    Args:
        config: Bot configuration.
    """
    logger = logging.getLogger("aoc_bot")

    logger.info("=" * 60)
    logger.info("AoC Telegram Bot Starting (Multi-Chat Mode)")
    logger.info("=" * 60)

    # Initialize database
    logger.info(f"Initializing database: {config.database_path}")
    db_manager = DatabaseManager(config.database_path)
    await db_manager.initialize()

    # Create Telegram Application
    logger.info("Creating Telegram Application")
    application = ApplicationBuilder().token(config.bot_token).build()

    # Create polling manager
    polling_manager = PollingManager(db_manager, config.bot_token)

    # Register command handlers
    logger.info("Registering command handlers")
    register_handlers(application, db_manager, polling_manager)

    # Start both application and polling manager concurrently
    logger.info("Starting bot...")

    try:
        async with application:
            await application.start()

            # Start polling manager in background
            polling_task = asyncio.create_task(polling_manager.start())

            # Start receiving updates
            await application.updater.start_polling()

            logger.info("Bot is running! Press Ctrl+C to stop.")
            logger.info(
                "Use /start in Telegram to configure your first leaderboard."
            )

            # Wait for shutdown signal
            try:
                await polling_task
            except asyncio.CancelledError:
                logger.info("Polling manager cancelled")

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        logger.info("Shutting down...")
        await polling_manager.stop()

        if application.updater.running:
            await application.updater.stop()

        await application.stop()
        await db_manager.close()

        logger.info("Shutdown complete")


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        # Parse command-line arguments
        args = parse_args()

        # Create configuration from arguments
        config = BotConfig.from_args(args)

        # Validate configuration
        try:
            config.validate()
        except ValueError as e:
            print(f"Configuration Error:\n{e}", file=sys.stderr)
            return 1

        # Setup logging
        logger = setup_logging(config.log_file)

        # Run async main
        asyncio.run(main_async(config))

        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        logging.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
