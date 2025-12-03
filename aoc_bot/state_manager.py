"""State management for leaderboard data."""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MemberState:
    """State of a single leaderboard member."""

    member_id: str
    name: str
    stars: int
    local_score: int
    rank: int = 0
    completed_days: Dict[int, Set[int]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "member_id": self.member_id,
            "name": self.name,
            "stars": self.stars,
            "local_score": self.local_score,
            "rank": self.rank,
            "completed_days": {
                str(day): sorted(list(parts))
                for day, parts in self.completed_days.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemberState":
        """Create from dictionary (loaded from JSON)."""
        return cls(
            member_id=data["member_id"],
            name=data["name"],
            stars=data["stars"],
            local_score=data["local_score"],
            rank=data.get("rank", 0),
            completed_days={
                int(day): set(parts)
                for day, parts in data.get("completed_days", {}).items()
            },
        )


@dataclass
class ProcessedLeaderboard:
    """Processed leaderboard state for easy comparison."""

    timestamp: float
    members: Dict[str, MemberState] = field(default_factory=dict)
    rankings: List[Tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "members": {
                member_id: member.to_dict()
                for member_id, member in self.members.items()
            },
            "rankings": self.rankings,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessedLeaderboard":
        """Create from dictionary (loaded from JSON)."""
        return cls(
            timestamp=data["timestamp"],
            members={
                member_id: MemberState.from_dict(member_data)
                for member_id, member_data in data.get("members", {}).items()
            },
            rankings=[(member_id, rank) for member_id, rank in data.get("rankings", [])],
        )


class StateManager:
    """Manages persistence of leaderboard state."""

    def __init__(self, state_file: Path):
        """Initialize the state manager.

        Args:
            state_file: Path to the JSON file for storing state.
        """
        self.state_file = Path(state_file)
        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def save_state(self, leaderboard_data: Dict[str, Any]) -> None:
        """Save leaderboard state to disk.

        Args:
            leaderboard_data: Raw leaderboard data from AoC API.
        """
        processed = self._process_leaderboard(leaderboard_data)
        state_dict = processed.to_dict()

        # Write to temp file first, then rename (atomic write)
        temp_file = self.state_file.with_suffix(".tmp")

        try:
            with open(temp_file, "w") as f:
                json.dump(state_dict, f, indent=2)
            temp_file.replace(self.state_file)
            logger.debug(f"Saved leaderboard state to {self.state_file}")
        except IOError as e:
            logger.error(f"Failed to save state: {e}")
            raise

    def load_state(self) -> Optional[ProcessedLeaderboard]:
        """Load previous leaderboard state from disk.

        Returns:
            ProcessedLeaderboard if file exists and is valid, None otherwise.
        """
        if not self.state_file.exists():
            logger.debug(f"State file not found at {self.state_file}")
            return None

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
            state = ProcessedLeaderboard.from_dict(data)
            logger.debug(f"Loaded leaderboard state from {self.state_file}")
            return state
        except (IOError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load state file: {e}. Starting fresh.")
            return None

    def _process_leaderboard(self, leaderboard_data: Dict[str, Any]) -> ProcessedLeaderboard:
        """Convert raw AoC API response to ProcessedLeaderboard.

        Args:
            leaderboard_data: Raw JSON response from AoC API.

        Returns:
            ProcessedLeaderboard with members and rankings.
        """
        members: Dict[str, MemberState] = {}
        member_scores: List[Tuple[str, int]] = []

        for member_id, member_data in leaderboard_data.get("members", {}).items():
            # Extract completed days and parts
            completed_days: Dict[int, Set[int]] = {}
            for day_str, day_data in member_data.get("completion_day_level", {}).items():
                day = int(day_str)
                completed_parts = set()
                for part_str in day_data.keys():
                    completed_parts.add(int(part_str))
                if completed_parts:
                    completed_days[day] = completed_parts

            member = MemberState(
                member_id=member_id,
                name=member_data.get("name", f"User {member_id}"),
                stars=member_data.get("stars", 0),
                local_score=member_data.get("local_score", 0),
                completed_days=completed_days,
            )
            members[member_id] = member
            member_scores.append((member_id, member_data.get("local_score", 0)))

        # Sort by score (descending) to get rankings
        member_scores.sort(key=lambda x: x[1], reverse=True)
        rankings = member_scores

        # Assign rank to each member with proper tie handling
        for i, (member_id, score) in enumerate(rankings):
            # Calculate rank: count how many people have strictly higher score
            rank = 1
            for j in range(i):
                if rankings[j][1] > score:
                    rank += 1
            members[member_id].rank = rank

        return ProcessedLeaderboard(
            timestamp=time.time(),
            members=members,
            rankings=[(member_id, score) for member_id, score in rankings],
        )
