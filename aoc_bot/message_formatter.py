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
    def format_changes(
        changes: LeaderboardChanges, user_links: Dict[str, str] = None
    ) -> List[str]:
        """Format all changes into one or more Telegram messages.

        Args:
            changes: LeaderboardChanges with all detected changes.
            user_links: Optional dict mapping member names to user IDs for mentions.

        Returns:
            List of formatted message strings.
        """
        if user_links is None:
            user_links = {}
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
                    MessageFormatter._format_new_star(event, user_links)
                )
            lines.append("")

        # Add rank changes
        if changes.rank_changes:
            lines.append("📈 Rank Changes:")
            for event in changes.rank_changes:
                lines.append(
                    MessageFormatter._format_rank_change(event, user_links)
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
                    MessageFormatter._format_score_change(event, user_links)
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
    def _format_member_name(member_name: str, user_links: Dict[str, str]) -> str:
        """Format a member name with mention if user is linked.

        Args:
            member_name: The member's name.
            user_links: Dict mapping member names to user IDs.

        Returns:
            Member name, potentially with mention.
        """
        if member_name in user_links:
            user_id = user_links[member_name]
            return f"{member_name} (<a href='tg://user?id={user_id}'>@{member_name}</a>)"
        return member_name

    @staticmethod
    def _format_new_star(event: NewStarEvent, user_links: Dict[str, str] = None) -> str:
        """Format a single new star event."""
        if user_links is None:
            user_links = {}

        member_display = MessageFormatter._format_member_name(
            event.member_name, user_links
        )

        if event.is_day_completion and event.part == 2:
            return f"  🌟 {member_display} - Day {event.day} (Complete!)"
        else:
            return f"  ⭐ {member_display} - Day {event.day} Part {event.part}"

    @staticmethod
    def _format_rank_change(
        event: RankChangeEvent, user_links: Dict[str, str] = None
    ) -> str:
        """Format a rank change event."""
        if user_links is None:
            user_links = {}

        member_display = MessageFormatter._format_member_name(
            event.member_name, user_links
        )

        delta = event.rank_delta
        if delta < 0:
            # Moved up
            arrow = f"↑ {abs(delta)}"
        else:
            # Moved down
            arrow = f"↓ {abs(delta)}"

        return f"  {member_display}: #{event.old_rank} → #{event.new_rank} ({arrow})"

    @staticmethod
    def _format_score_change(
        event: ScoreChangeEvent, user_links: Dict[str, str] = None
    ) -> str:
        """Format a score change event."""
        if user_links is None:
            user_links = {}

        member_display = MessageFormatter._format_member_name(
            event.member_name, user_links
        )

        delta = event.score_delta
        if delta > 0:
            return f"  {member_display}: {event.old_score} → {event.new_score} (+{delta})"
        else:
            return f"  {member_display}: {event.old_score} → {event.new_score} ({delta})"

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
            stars = member_data.get("stars", 0)
            # Only include members with at least 1 star
            if stars >= 1:
                member_list.append({
                    "name": member_data.get("name", "Anonymous"),
                    "score": member_data.get("local_score", 0),
                    "stars": stars,
                })

        if not member_list:
            lines.append("No members have earned any stars yet.")
            return lines

        member_list.sort(key=lambda m: (m["score"], m["stars"]), reverse=True)

        # Format rankings with proper handling of tied positions
        for i, member in enumerate(member_list):
            name = member["name"]
            score = member["score"]
            stars = member["stars"]

            # Calculate rank: count how many people have strictly higher score
            rank = 1
            for j in range(i):
                if member_list[j]["score"] > score:
                    rank += 1

            lines.append(f"{rank}. {name}: {score} points ({stars}⭐)")

        # Combine lines and split if necessary
        full_message = "\n".join(lines).strip()

        if len(full_message) <= MESSAGE_LIMIT:
            return [full_message]
        else:
            return MessageFormatter._split_long_message(full_message)
