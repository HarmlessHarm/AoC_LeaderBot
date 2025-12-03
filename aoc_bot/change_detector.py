"""Change detection for leaderboard updates."""

import logging
from dataclasses import dataclass
from typing import List, Optional

from aoc_bot.state_manager import ProcessedLeaderboard

logger = logging.getLogger(__name__)


@dataclass
class NewStarEvent:
    """A member completed a star (day part)."""

    member_id: str
    member_name: str
    day: int
    part: int
    is_day_completion: bool  # True if part 2 (day fully completed)


@dataclass
class RankChangeEvent:
    """A member's rank changed."""

    member_id: str
    member_name: str
    old_rank: int
    new_rank: int

    @property
    def rank_delta(self) -> int:
        """Change in rank (negative = moved up)."""
        return self.new_rank - self.old_rank


@dataclass
class ScoreChangeEvent:
    """A member's score changed."""

    member_id: str
    member_name: str
    old_score: int
    new_score: int

    @property
    def score_delta(self) -> int:
        """Change in score."""
        return self.new_score - self.old_score


@dataclass
class NewMemberEvent:
    """A new member joined the leaderboard."""

    member_id: str
    member_name: str


@dataclass
class LeaderboardChanges:
    """Container for all detected changes."""

    new_stars: List[NewStarEvent]
    rank_changes: List[RankChangeEvent]
    score_changes: List[ScoreChangeEvent]
    new_members: List[NewMemberEvent]

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return (
            bool(self.new_stars)
            or bool(self.rank_changes)
            or bool(self.score_changes)
            or bool(self.new_members)
        )

    @property
    def total_changes(self) -> int:
        """Get total number of events."""
        return (
            len(self.new_stars)
            + len(self.rank_changes)
            + len(self.score_changes)
            + len(self.new_members)
        )


class ChangeDetector:
    """Detects changes between leaderboard states."""

    @staticmethod
    def detect_changes(
        old_state: Optional[ProcessedLeaderboard],
        new_state: ProcessedLeaderboard,
    ) -> LeaderboardChanges:
        """Detect all changes between two leaderboard states.

        Args:
            old_state: Previous leaderboard state (None on first run).
            new_state: Current leaderboard state.

        Returns:
            LeaderboardChanges with all detected changes.
        """
        changes = LeaderboardChanges(
            new_stars=[],
            rank_changes=[],
            score_changes=[],
            new_members=[],
        )

        # On first run, don't report changes
        if old_state is None:
            logger.info("First run - not reporting initial state as changes")
            return changes

        # Detect new members
        for member_id, member in new_state.members.items():
            if member_id not in old_state.members:
                changes.new_members.append(
                    NewMemberEvent(member_id=member_id, member_name=member.name)
                )

        # Detect changes for existing and returning members
        for member_id, new_member in new_state.members.items():
            if member_id not in old_state.members:
                continue  # Already handled as new member

            old_member = old_state.members[member_id]

            # Detect new stars
            new_completed_days = new_member.completed_days
            old_completed_days = old_member.completed_days

            for day in range(1, 26):
                new_parts = new_completed_days.get(day, set())
                old_parts = old_completed_days.get(day, set())

                # Check part 1
                if 1 in new_parts and 1 not in old_parts:
                    changes.new_stars.append(
                        NewStarEvent(
                            member_id=member_id,
                            member_name=new_member.name,
                            day=day,
                            part=1,
                            is_day_completion=(2 in new_parts),
                        )
                    )

                # Check part 2
                if 2 in new_parts and 2 not in old_parts:
                    changes.new_stars.append(
                        NewStarEvent(
                            member_id=member_id,
                            member_name=new_member.name,
                            day=day,
                            part=2,
                            is_day_completion=True,
                        )
                    )

            # Detect score changes
            if new_member.local_score != old_member.local_score:
                changes.score_changes.append(
                    ScoreChangeEvent(
                        member_id=member_id,
                        member_name=new_member.name,
                        old_score=old_member.local_score,
                        new_score=new_member.local_score,
                    )
                )

            # Detect rank changes
            if new_member.rank != old_member.rank:
                changes.rank_changes.append(
                    RankChangeEvent(
                        member_id=member_id,
                        member_name=new_member.name,
                        old_rank=old_member.rank,
                        new_rank=new_member.rank,
                    )
                )

        return changes
