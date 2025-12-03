"""Message formatting for Telegram notifications."""

import logging
from typing import Any, Dict, List

from aoc_bot.change_detector import (
    LeaderboardChanges,
    NewMemberEvent,
    NewStarEvent,
    RankChangeEvent,
    ScoreChangeEvent,
)

logger = logging.getLogger(__name__)

# Telegram message character limit
MESSAGE_LIMIT = 4096


class MessageFormatter:
    """Formats leaderboard changes into Telegram messages."""

    @staticmethod
    def format_changes(changes: LeaderboardChanges) -> List[str]:
        """Format all changes into one or more Telegram messages.

        Args:
            changes: LeaderboardChanges with all detected changes.

        Returns:
            List of formatted message strings.
        """
        if not changes.has_changes:
            return []

        messages: List[str] = []

        # Build message content
        lines: List[str] = []
        lines.append("📊 Leaderboard Update")
        lines.append("")

        # Add new stars
        if changes.new_stars:
            lines.append("⭐ New Stars:")
            for event in changes.new_stars:
                lines.append(
                    MessageFormatter._format_new_star(event)
                )
            lines.append("")

        # Add rank changes
        if changes.rank_changes:
            lines.append("📈 Rank Changes:")
            for event in changes.rank_changes:
                lines.append(
                    MessageFormatter._format_rank_change(event)
                )
            lines.append("")

        # Add score changes (exclude members with new stars already listed)
        star_members = {event.member_id for event in changes.new_stars}
        score_changes = [
            event for event in changes.score_changes
            if event.member_id not in star_members
        ]
        if score_changes:
            lines.append("💰 Score Changes:")
            for event in score_changes:
                lines.append(
                    MessageFormatter._format_score_change(event)
                )
            lines.append("")

        # Add new members
        if changes.new_members:
            lines.append("👥 New Members:")
            for event in changes.new_members:
                lines.append(f"  • {event.member_name}")
            lines.append("")

        # Combine lines and split if necessary
        full_message = "\n".join(lines).strip()

        if len(full_message) <= MESSAGE_LIMIT:
            messages.append(full_message)
        else:
            # Split into multiple messages if too long
            messages = MessageFormatter._split_long_message(full_message)

        return messages

    @staticmethod
    def _format_new_star(event: NewStarEvent) -> str:
        """Format a single new star event."""
        if event.is_day_completion and event.part == 2:
            return f"  🌟 {event.member_name} - Day {event.day} (Complete!)"
        else:
            return f"  ⭐ {event.member_name} - Day {event.day} Part {event.part}"

    @staticmethod
    def _format_rank_change(event: RankChangeEvent) -> str:
        """Format a rank change event."""
        delta = event.rank_delta
        if delta < 0:
            # Moved up
            arrow = f"↑ {abs(delta)}"
        else:
            # Moved down
            arrow = f"↓ {abs(delta)}"

        return f"  {event.member_name}: #{event.old_rank} → #{event.new_rank} ({arrow})"

    @staticmethod
    def _format_score_change(event: ScoreChangeEvent) -> str:
        """Format a score change event."""
        delta = event.score_delta
        if delta > 0:
            return f"  {event.member_name}: {event.old_score} → {event.new_score} (+{delta})"
        else:
            return f"  {event.member_name}: {event.old_score} → {event.new_score} ({delta})"

    @staticmethod
    def _split_long_message(message: str) -> List[str]:
        """Split a long message into multiple messages.

        Args:
            message: The full message that exceeds the limit.

        Returns:
            List of messages, each within the character limit.
        """
        messages: List[str] = []
        current_message = ""

        for line in message.split("\n"):
            if len(current_message) + len(line) + 1 <= MESSAGE_LIMIT:
                if current_message:
                    current_message += "\n"
                current_message += line
            else:
                if current_message:
                    messages.append(current_message)
                current_message = line

        if current_message:
            messages.append(current_message)

        return messages

    @staticmethod
    def format_leaderboard(leaderboard_data: Dict[str, Any], year: int) -> List[str]:
        """Format current leaderboard rankings into messages.

        Args:
            leaderboard_data: Leaderboard JSON data from AoC API.
            year: The year of the event.

        Returns:
            List of formatted message strings.
        """
        lines: List[str] = []
        lines.append(f"🏆 Leaderboard Rankings ({year})")
        lines.append("")

        # Extract and sort members by local score
        members = leaderboard_data.get("members", {})
        if not members:
            lines.append("No members on this leaderboard yet.")
            return lines

        # Convert to list and sort by local_score (descending)
        member_list = []
        for member_id, member_data in members.items():
            member_list.append({
                "name": member_data.get("name", "Anonymous"),
                "score": member_data.get("local_score", 0),
                "stars": member_data.get("stars", 0),
            })

        member_list.sort(key=lambda m: (m["score"], m["stars"]), reverse=True)

        # Format rankings
        for rank, member in enumerate(member_list, 1):
            name = member["name"]
            score = member["score"]
            stars = member["stars"]
            lines.append(f"{rank}. {name}: {score} points ({stars}⭐)")

        # Combine lines and split if necessary
        full_message = "\n".join(lines).strip()

        if len(full_message) <= MESSAGE_LIMIT:
            return [full_message]
        else:
            return MessageFormatter._split_long_message(full_message)
