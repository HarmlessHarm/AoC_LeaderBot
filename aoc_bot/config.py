"""Configuration management for the AoC Telegram Bot (Multi-Chat)."""

import argparse
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BotConfig:
    """Minimal bot configuration for multi-chat mode."""

    bot_token: str
    database_path: Path = None
    log_file: Path = None

    def __post_init__(self):
        """Set defaults for optional fields."""
        if self.database_path is None:
            self.database_path = Path("data") / "bot_config.db"

        if self.log_file is None:
            self.log_file = Path("logs") / "aoc_bot.log"

    def validate(self) -> None:
        """Validate configuration parameters.

        Raises:
            ValueError: If required parameters are missing or invalid.
        """
        errors = []

        if not self.bot_token or not str(self.bot_token).strip():
            errors.append("bot_token is required")

        if not self.bot_token.count(":") >= 1:
            errors.append("bot_token format should be 'TOKEN_ID:TOKEN_STRING'")

        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "BotConfig":
        """Create BotConfig from parsed command-line arguments.

        Args:
            args: Parsed argparse.Namespace with configuration values.

        Returns:
            BotConfig instance.
        """
        return cls(
            bot_token=args.bot_token,
            database_path=Path(args.database) if args.database else None,
            log_file=Path(args.log_file) if args.log_file else None,
        )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace with parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Multi-chat Telegram bot that monitors Advent of Code leaderboards"
    )

    # Required: bot token
    parser.add_argument(
        "--bot-token",
        default=os.getenv("TELEGRAM_BOT_TOKEN"),
        required=not os.getenv("TELEGRAM_BOT_TOKEN"),
        help="Telegram bot token from @BotFather "
        "(or set TELEGRAM_BOT_TOKEN environment variable)"
    )

    # Optional: database path
    parser.add_argument(
        "--database",
        default="data/bot_config.db",
        help="Path to SQLite database file (default: data/bot_config.db)"
    )

    # Optional: log file
    parser.add_argument(
        "--log-file",
        default="logs/aoc_bot.log",
        help="Path to log file (default: logs/aoc_bot.log)"
    )

    return parser.parse_args()
