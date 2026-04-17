"""Data models for the MN Lorcana leaderboard pipeline."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Match:
    match_id: int
    event_id: int
    event_name: str
    event_date: str  # ISO format
    round_id: int
    round_number: int
    player1_id: int
    player1_name: str
    player2_id: Optional[int]  # None for byes
    player2_name: Optional[str]
    winner_id: Optional[int]  # None for draws
    is_bye: bool
    is_draw: bool
    games_won_by_winner: int
    games_won_by_loser: int
    store_name: str

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class Event:
    event_id: int
    name: str
    date: str  # ISO format
    store_name: str
    store_state: str
    status: str
    round_ids: list = field(default_factory=list)
    rounds_fetched: bool = False

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class PlayerStats:
    player_id: int
    name: str
    elo: float = 1200.0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    current_streak: int = 0  # positive = wins, negative = losses
    best_win_streak: int = 0
    total_events: int = 0
    events_played: list = field(default_factory=list)
    stores_played_at: list = field(default_factory=list)
    last_played: str = ""
    elo_history: list = field(default_factory=list)

    @property
    def total_matches(self):
        return self.wins + self.losses + self.draws

    @property
    def win_rate(self):
        if self.total_matches == 0:
            return 0.0
        return self.wins / self.total_matches

    @property
    def record_str(self):
        return f"{self.wins}-{self.losses}"

    def to_dict(self):
        d = asdict(self)
        d["total_matches"] = self.total_matches
        d["win_rate"] = round(self.win_rate * 100, 2)
        d["record"] = self.record_str
        return d

    @classmethod
    def from_dict(cls, d):
        # Remove computed fields
        d.pop("total_matches", None)
        d.pop("win_rate", None)
        d.pop("record", None)
        return cls(**d)
