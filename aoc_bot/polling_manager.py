"""Management of concurrent leaderboard polling tasks."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

from aoc_bot.aoc_api import AoCAPIClient, AoCAPIError
from aoc_bot.change_detector import ChangeDetector
from aoc_bot.database import ChatConfig, DatabaseManager
from aoc_bot.message_formatter import MessageFormatter
from aoc_bot.state_manager import StateManager
from aoc_bot.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)

# Task key: (chat_id, leaderboard_id, year)
TaskKey = Tuple[str, str, int]


@dataclass
class TaskStatus:
    """Status of a polling task."""

    task_key: TaskKey
    status: str  # 'running', 'stopped', 'error'
    last_poll: Optional[datetime] = None
    next_poll: Optional[datetime] = None
    error_message: Optional[str] = None
    error_count: int = 0


class PollingManager:
    """Manages multiple concurrent leaderboard polling tasks."""

    def __init__(self, db_manager: DatabaseManager, bot_token: str):
        """Initialize polling manager.

        Args:
            db_manager: Database manager instance.
            bot_token: Telegram bot token.
        """
        self.db = db_manager
        self.bot_token = bot_token
        self.active_tasks: Dict[TaskKey, asyncio.Task] = {}
        self.task_status: Dict[TaskKey, TaskStatus] = {}
        self.shutdown_event = asyncio.Event()
        self.logger = logging.getLogger(__name__)
        self.notifier = TelegramNotifier(bot_token)

    async def start(self) -> None:
        """Load configs and start all polling tasks.

        This method loads all enabled configurations from the database
        and starts a polling task for each one.
        """
        self.logger.info("Starting polling manager...")

        try:
            # Load all enabled configs
            configs = await self.db.get_all_enabled_configs()
            self.logger.info(f"Found {len(configs)} enabled configuration(s)")

            # Start task for each config
            for config in configs:
                try:
                    await self.add_leaderboard(
                        config.chat_id, config.leaderboard_id, config.year
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to start polling for {config.chat_id}, "
                        f"{config.leaderboard_id}, {config.year}: {e}"
                    )

            # Keep running until shutdown
            await self.shutdown_event.wait()

        except Exception as e:
            self.logger.error(f"Error in polling manager: {e}", exc_info=True)

    async def stop(self) -> None:
        """Gracefully stop all polling tasks."""
        self.logger.info("Stopping polling manager...")
        self.shutdown_event.set()

        # Cancel all active tasks
        for task_key, task in list(self.active_tasks.items()):
            self.logger.info(f"Canceling task {task_key}")
            task.cancel()

        # Wait for all to finish
        if self.active_tasks:
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)

        self.logger.info("All polling tasks stopped")

    async def add_leaderboard(self, chat_id: str, leaderboard_id: str, year: int) -> None:
        """Start monitoring a leaderboard.

        Args:
            chat_id: Telegram chat ID.
            leaderboard_id: AoC leaderboard ID.
            year: AoC event year.

        Raises:
            ValueError: If configuration not found.
        """
        task_key = (chat_id, leaderboard_id, year)

        if task_key in self.active_tasks:
            self.logger.warning(f"Task {task_key} already running")
            return

        # Get config from database
        config = await self.db.get_config(chat_id, leaderboard_id, year)
        if not config:
            raise ValueError(f"Config not found for {task_key}")

        # Create and start task
        task = asyncio.create_task(self._poll_leaderboard(config))
        self.active_tasks[task_key] = task

        # Initialize status
        self.task_status[task_key] = TaskStatus(
            task_key=task_key,
            status="running",
            last_poll=None,
            next_poll=datetime.now(),
            error_message=None,
            error_count=0,
        )

        self.logger.info(f"Started monitoring {task_key}")

    async def remove_leaderboard(self, chat_id: str, leaderboard_id: str, year: int) -> None:
        """Stop monitoring a leaderboard.

        Args:
            chat_id: Telegram chat ID.
            leaderboard_id: AoC leaderboard ID.
            year: AoC event year.
        """
        task_key = (chat_id, leaderboard_id, year)

        if task_key not in self.active_tasks:
            self.logger.warning(f"Task {task_key} not running")
            return

        # Cancel task
        self.active_tasks[task_key].cancel()
        del self.active_tasks[task_key]

        # Update status
        if task_key in self.task_status:
            self.task_status[task_key].status = "stopped"

        self.logger.info(f"Stopped monitoring {task_key}")

    def get_task_status(self, task_key: TaskKey) -> Optional[TaskStatus]:
        """Get status for a specific task.

        Args:
            task_key: Task key (chat_id, leaderboard_id, year).

        Returns:
            TaskStatus if task exists, None otherwise.
        """
        return self.task_status.get(task_key)

    async def _poll_leaderboard(self, config: ChatConfig) -> None:
        """Individual polling task for one leaderboard.

        This task runs continuously, polling the AoC leaderboard at regular
        intervals and sending notifications when changes are detected.

        Args:
            config: Chat configuration for the leaderboard.
        """
        task_key = (config.chat_id, config.leaderboard_id, config.year)

        # Initialize components
        aoc_client = AoCAPIClient(config.session_cookie, config.year, config.leaderboard_id)
        state_file = self._get_state_file(config)
        state_manager = StateManager(state_file)

        self.logger.info(f"Polling task {task_key} started")

        try:
            while not self.shutdown_event.is_set():
                try:
                    # Poll once
                    self.logger.debug(f"Polling {task_key}...")

                    current_data = await asyncio.to_thread(aoc_client.fetch_leaderboard)
                    previous_state = state_manager.load_state()
                    processed_state = state_manager._process_leaderboard(current_data)
                    changes = ChangeDetector.detect_changes(previous_state, processed_state)

                    if changes.has_changes:
                        self.logger.info(
                            f"Changes detected for {task_key}: "
                            f"{changes.total_changes} event(s)"
                        )
                        messages = MessageFormatter.format_changes(changes)
                        await self.notifier.send_messages(config.chat_id, messages)

                    state_manager.save_state(current_data)

                    # Update status
                    now = datetime.now()
                    self.task_status[task_key].last_poll = now
                    self.task_status[task_key].next_poll = now + timedelta(
                        seconds=config.poll_interval
                    )
                    self.task_status[task_key].error_count = 0
                    self.task_status[task_key].error_message = None
                    self.task_status[task_key].status = "running"

                    # Sleep until next poll
                    try:
                        await asyncio.sleep(config.poll_interval)
                    except asyncio.CancelledError:
                        self.logger.info(f"Task {task_key} cancelled during sleep")
                        raise

                except AoCAPIError as e:
                    self.logger.error(f"AoC API error for {task_key}: {e}")
                    self.task_status[task_key].error_count += 1
                    self.task_status[task_key].error_message = str(e)
                    self.task_status[task_key].status = "error"

                    # Handle authentication errors specially
                    if "Authentication failed" in str(e):
                        self.logger.warning(
                            f"Authentication failed for {task_key}, disabling config"
                        )
                        await self.notifier.send_message(
                            config.chat_id,
                            f"❌ Session cookie invalid for leaderboard {config.leaderboard_id}.\n"
                            f"Please update it with /add_leaderboard.",
                        )
                        # Disable config
                        await self.db.disable_config(
                            config.chat_id, config.leaderboard_id, config.year
                        )
                        break  # Stop this task

                    # Continue polling after transient error
                    try:
                        await asyncio.sleep(config.poll_interval)
                    except asyncio.CancelledError:
                        self.logger.info(f"Task {task_key} cancelled during error sleep")
                        raise

                except asyncio.CancelledError:
                    self.logger.info(f"Task {task_key} cancelled")
                    raise

                except Exception as e:
                    self.logger.error(
                        f"Unexpected error for {task_key}: {e}", exc_info=True
                    )
                    self.task_status[task_key].error_count += 1
                    self.task_status[task_key].error_message = str(e)
                    self.task_status[task_key].status = "error"

                    # Continue despite errors (fault isolation)
                    try:
                        await asyncio.sleep(config.poll_interval)
                    except asyncio.CancelledError:
                        self.logger.info(f"Task {task_key} cancelled during error sleep")
                        raise

        except asyncio.CancelledError:
            self.logger.info(f"Polling task {task_key} cancelled")
        except Exception as e:
            self.logger.error(
                f"Fatal error in polling task {task_key}: {e}", exc_info=True
            )
            self.task_status[task_key].status = "error"
            self.task_status[task_key].error_message = str(e)

    @staticmethod
    def _get_state_file(config: ChatConfig) -> Path:
        """Generate state file path for configuration.

        Args:
            config: Chat configuration.

        Returns:
            Path to state file.
        """
        # Sanitize chat_id (replace negative sign with 'n')
        clean_chat_id = str(config.chat_id).replace("-", "n")
        return (
            Path("data")
            / f"state_{clean_chat_id}_{config.leaderboard_id}_{config.year}.json"
        )
