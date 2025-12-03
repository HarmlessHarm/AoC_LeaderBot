"""Database management for bot configuration."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class ChatConfig:
    """Configuration for a chat-leaderboard pair."""

    chat_id: str
    leaderboard_id: str
    session_cookie: str
    year: int
    poll_interval: int = 900
    enabled: bool = True
    id: Optional[int] = None


class DatabaseManager:
    """Manages SQLite database for bot configuration."""

    def __init__(self, db_path: Path):
        """Initialize database manager.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize database connection and create schema."""
        try:
            self.conn = await aiosqlite.connect(str(self.db_path))
            await self._create_schema()
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def close(self) -> None:
        """Close database connection."""
        if self.conn:
            await self.conn.close()
            logger.debug("Database connection closed")

    async def _create_schema(self) -> None:
        """Create database tables if they don't exist."""
        schema = """
        CREATE TABLE IF NOT EXISTS chat_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL UNIQUE,
            leaderboard_id TEXT NOT NULL,
            session_cookie TEXT NOT NULL,
            year INTEGER NOT NULL,
            poll_interval INTEGER NOT NULL DEFAULT 900,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_chat_id ON chat_configs(chat_id);
        CREATE INDEX IF NOT EXISTS idx_enabled ON chat_configs(enabled);
        """

        try:
            await self.conn.executescript(schema)
            await self.conn.commit()
            logger.debug("Database schema created/verified")
        except Exception as e:
            logger.error(f"Failed to create schema: {e}")
            raise

    async def add_config(
        self,
        chat_id: str,
        leaderboard_id: str,
        session_cookie: str,
        year: int,
        poll_interval: int = 900,
    ) -> None:
        """Add or update chat configuration (one per chat).

        Args:
            chat_id: Telegram chat ID.
            leaderboard_id: AoC leaderboard ID.
            session_cookie: AoC session cookie.
            year: AoC event year.
            poll_interval: Seconds between polls (default: 900).
        """
        try:
            # Check if config already exists for this chat
            existing = await self.get_config_for_chat(chat_id)

            if existing:
                # Update existing config
                await self.conn.execute(
                    """UPDATE chat_configs
                       SET leaderboard_id=?, session_cookie=?, year=?, poll_interval=?, enabled=1, updated_at=CURRENT_TIMESTAMP
                       WHERE chat_id=?""",
                    (leaderboard_id, session_cookie, year, poll_interval, chat_id),
                )
                logger.info(
                    f"Updated config: chat={chat_id}, "
                    f"leaderboard={leaderboard_id}, year={year}"
                )
            else:
                # Insert new config
                await self.conn.execute(
                    """INSERT INTO chat_configs
                       (chat_id, leaderboard_id, session_cookie, year, poll_interval, enabled)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                    (chat_id, leaderboard_id, session_cookie, year, poll_interval),
                )
                logger.info(
                    f"Added config: chat={chat_id}, "
                    f"leaderboard={leaderboard_id}, year={year}"
                )

            await self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to add config: {e}")
            raise

    async def remove_config(self, chat_id: str, leaderboard_id: str = None, year: int = None) -> None:
        """Remove a chat configuration.

        Args:
            chat_id: Telegram chat ID.
            leaderboard_id: (Optional) AoC leaderboard ID - kept for compatibility but ignored.
            year: (Optional) AoC event year - kept for compatibility but ignored.
        """
        try:
            cursor = await self.conn.execute(
                "DELETE FROM chat_configs WHERE chat_id=?",
                (chat_id,),
            )
            await self.conn.commit()

            if cursor.rowcount == 0:
                logger.warning(f"Config not found for deletion: chat={chat_id}")
            else:
                logger.info(f"Removed config: chat={chat_id}")
        except Exception as e:
            logger.error(f"Failed to remove config: {e}")
            raise

    async def get_config(
        self, chat_id: str, leaderboard_id: str, year: int
    ) -> Optional[ChatConfig]:
        """Get a specific configuration (deprecated - kept for compatibility).

        Args:
            chat_id: Telegram chat ID.
            leaderboard_id: AoC leaderboard ID.
            year: AoC event year.

        Returns:
            ChatConfig if found, None otherwise.
        """
        try:
            async with self.conn.execute(
                """SELECT id, chat_id, leaderboard_id, session_cookie, year,
                          poll_interval, enabled
                   FROM chat_configs
                   WHERE chat_id=?""",
                (chat_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_config(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            raise

    async def get_config_for_chat(self, chat_id: str) -> Optional[ChatConfig]:
        """Get the leaderboard configuration for a chat (one per chat).

        Args:
            chat_id: Telegram chat ID.

        Returns:
            ChatConfig if found, None otherwise.
        """
        try:
            async with self.conn.execute(
                """SELECT id, chat_id, leaderboard_id, session_cookie, year,
                          poll_interval, enabled
                   FROM chat_configs
                   WHERE chat_id=?""",
                (chat_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_config(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get config for chat: {e}")
            raise

    async def get_configs_for_chat(self, chat_id: str) -> List[ChatConfig]:
        """Get all configurations for a chat.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            List of ChatConfig for the chat.
        """
        try:
            async with self.conn.execute(
                """SELECT id, chat_id, leaderboard_id, session_cookie, year,
                          poll_interval, enabled
                   FROM chat_configs
                   WHERE chat_id=?
                   ORDER BY created_at""",
                (chat_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_config(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get configs for chat: {e}")
            raise

    async def get_all_enabled_configs(self) -> List[ChatConfig]:
        """Get all enabled configurations for polling.

        Returns:
            List of all enabled ChatConfig.
        """
        try:
            async with self.conn.execute(
                """SELECT id, chat_id, leaderboard_id, session_cookie, year,
                          poll_interval, enabled
                   FROM chat_configs
                   WHERE enabled=1
                   ORDER BY created_at""",
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_config(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get all enabled configs: {e}")
            raise

    async def config_exists(
        self, chat_id: str, leaderboard_id: str, year: int
    ) -> bool:
        """Check if a configuration exists.

        Args:
            chat_id: Telegram chat ID.
            leaderboard_id: AoC leaderboard ID.
            year: AoC event year.

        Returns:
            True if configuration exists, False otherwise.
        """
        try:
            async with self.conn.execute(
                """SELECT 1 FROM chat_configs
                   WHERE chat_id=? AND leaderboard_id=? AND year=?""",
                (chat_id, leaderboard_id, year),
            ) as cursor:
                return await cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check config existence: {e}")
            raise

    async def disable_config(self, chat_id: str, leaderboard_id: str, year: int) -> None:
        """Disable a configuration without deleting it.

        Args:
            chat_id: Telegram chat ID.
            leaderboard_id: AoC leaderboard ID.
            year: AoC event year.
        """
        try:
            await self.conn.execute(
                """UPDATE chat_configs SET enabled=0
                   WHERE chat_id=? AND leaderboard_id=? AND year=?""",
                (chat_id, leaderboard_id, year),
            )
            await self.conn.commit()
            logger.info(
                f"Disabled config: chat={chat_id}, "
                f"leaderboard={leaderboard_id}, year={year}"
            )
        except Exception as e:
            logger.error(f"Failed to disable config: {e}")
            raise

    async def enable_config(self, chat_id: str, leaderboard_id: str, year: int) -> None:
        """Enable a previously disabled configuration.

        Args:
            chat_id: Telegram chat ID.
            leaderboard_id: AoC leaderboard ID.
            year: AoC event year.
        """
        try:
            await self.conn.execute(
                """UPDATE chat_configs SET enabled=1
                   WHERE chat_id=? AND leaderboard_id=? AND year=?""",
                (chat_id, leaderboard_id, year),
            )
            await self.conn.commit()
            logger.info(
                f"Enabled config: chat={chat_id}, "
                f"leaderboard={leaderboard_id}, year={year}"
            )
        except Exception as e:
            logger.error(f"Failed to enable config: {e}")
            raise

    @staticmethod
    def _row_to_config(row: tuple) -> ChatConfig:
        """Convert database row to ChatConfig.

        Args:
            row: Database row tuple.

        Returns:
            ChatConfig instance.
        """
        return ChatConfig(
            id=row[0],
            chat_id=row[1],
            leaderboard_id=row[2],
            session_cookie=row[3],
            year=row[4],
            poll_interval=row[5],
            enabled=bool(row[6]),
        )
