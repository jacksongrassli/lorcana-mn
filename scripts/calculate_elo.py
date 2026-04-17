"""Step 3: Calculate ELO ratings and player stats from match data.

Computes two parallel sets of stats for every player:
  - "all"       — every event
  - "set_champ" — set championship / major events only
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime

from config import (
    STARTING_ELO, K_FACTOR, MIN_MATCHES_FOR_RANKING,
    MATCHES_FILE, LEADERBOARD_FILE, EVENTS_FILE, DATA_DIR,
)
from models import PlayerStats

USERNAMES_FILE = os.path.join(DATA_DIR, "usernames.json")

# Keywords that identify an official set championship
SET_CHAMP_KEYWORDS = [
    "set championship",
    "store championship",
    "set champ",
]


def is_set_champ(event_name):
    name = (event_name or "").lower()
    return any(k in name for k in SET_CHAMP_KEYWORDS)


# ---------------------------------------------------------------------------
# ELO math
# ---------------------------------------------------------------------------

def expected_score(rating_a, rating_b):
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def update_elo(winner_elo, loser_elo, k=K_FACTOR):
    exp_w = expected_score(winner_elo, loser_elo)
    return round(winner_elo + k * (1.0 - exp_w), 2), round(loser_elo + k * (0.0 - (1.0 - exp_w)), 2)


def update_elo_draw(elo_a, elo_b, k=K_FACTOR):
    exp_a = expected_score(elo_a, elo_b)
    return round(elo_a + k * (0.5 - exp_a), 2), round(elo_b + k * (0.5 - (1.0 - exp_a)), 2)


# ---------------------------------------------------------------------------
# Per-player state containers
# ---------------------------------------------------------------------------

@dataclass
class Track:
    """One ELO track (all or set-champ-only) for a single player."""
    elo: float = STARTING_ELO
    wins: int = 0
    losses: int = 0
    draws: int = 0
    current_streak: int = 0
    best_win_streak: int = 0
    total_events: int = 0
    events_played: list = field(default_factory=list)
    elo_history: list = field(default_factory=list)

    @property
    def total_matches(self):
        return self.wins + self.losses + self.draws

    @property
    def win_rate(self):
        return self.wins / self.total_matches if self.total_matches else 0.0

    def to_dict(self):
        return {
            "elo": self.elo,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "record": f"{self.wins}-{self.losses}",
            "win_rate": round(self.win_rate * 100, 2),
            "total_matches": self.total_matches,
            "total_events": self.total_events,
            "current_streak": self.current_streak,
            "best_win_streak": self.best_win_streak,
            "elo_history": self.elo_history[-50:],
        }


def get_or_create(registry, pid, name):
    if pid not in registry:
        registry[pid] = {
            "name": name,
            "all": Track(),
            "sc": Track(),
            "last_played": "",
            "stores": [],
        }
    else:
        registry[pid]["name"] = name
    return registry[pid]


def update_streak(track, won):
    if won:
        track.current_streak = track.current_streak + 1 if track.current_streak > 0 else 1
        track.best_win_streak = max(track.best_win_streak, track.current_streak)
    else:
        track.current_streak = track.current_streak - 1 if track.current_streak < 0 else -1


def apply_match_to_track(track, pid, winner_id, p2_id, is_bye, is_draw,
                          partner_track, event_id, event_date):
    """Apply one match result to a track. Returns True if applied."""
    if event_id and event_id not in track.events_played:
        track.events_played.append(event_id)
        track.total_events = len(track.events_played)
    if event_date:
        # elo_history recorded after ELO update below
        pass

    if is_bye or not p2_id:
        track.wins += 1
        update_streak(track, True)
        return

    if is_draw:
        track.draws += 1
        track.elo, partner_track.elo = update_elo_draw(track.elo, partner_track.elo)
        track.current_streak = 0
        partner_track.current_streak = 0
    elif winner_id == pid:
        track.wins += 1
        partner_track.losses += 1
        track.elo, partner_track.elo = update_elo(track.elo, partner_track.elo)
        update_streak(track, True)
        update_streak(partner_track, False)
    else:
        track.losses += 1
        partner_track.wins += 1
        partner_track.elo, track.elo = update_elo(partner_track.elo, track.elo)
        update_streak(track, False)
        update_streak(partner_track, True)

    if event_date:
        track.elo_history.append([track.elo, event_date])
        partner_track.elo_history.append([partner_track.elo, event_date])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(MATCHES_FILE):
        print("No matches file found. Run fetch_matches.py first.")
        return

    with open(MATCHES_FILE) as f:
        matches = json.load(f)

    if not matches:
        print("No matches to process.")
        return

    # Load usernames
    usernames = {}
    if os.path.exists(USERNAMES_FILE):
        with open(USERNAMES_FILE) as f:
            usernames = json.load(f)  # {str(player_id): username}

    # Load event metadata
    event_lookup = {}
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE) as f:
            for ev in json.load(f):
                eid = ev["event_id"]
                event_lookup[eid] = {
                    "name": ev.get("name", ""),
                    "date": (ev.get("date", "") or "")[:10],
                    "store": ev.get("store_name", ""),
                    "is_set_champ": is_set_champ(ev.get("name", "")),
                }

    matches.sort(key=lambda m: (m.get("event_date", ""), m.get("round_number", 0)))

    # registry[player_id] = {name, all: Track, sc: Track, last_played, stores}
    registry = {}
    # per-player per-event record: {pid: {eid: {wins, losses, draws, is_set_champ}}}
    event_records = {}

    def ensure_rec(pid, eid):
        event_records.setdefault(pid, {})
        event_records[pid].setdefault(eid, {"wins": 0, "losses": 0, "draws": 0})
        return event_records[pid][eid]

    processed = 0

    for match in matches:
        p1_id = match.get("player1_id")
        p1_name = match.get("player1_name", "Unknown")
        p2_id = match.get("player2_id")
        p2_name = match.get("player2_name")
        winner_id = match.get("winner_id")
        is_bye = match.get("is_bye", False)
        is_draw = match.get("is_draw", False) or (winner_id is None and not is_bye and p2_id)
        event_date = match.get("event_date", "")
        event_id = match.get("event_id")
        store_name = match.get("store_name", "")
        event_name = match.get("event_name", event_lookup.get(event_id, {}).get("name", ""))
        sc = is_set_champ(event_name)

        if not p1_id:
            continue

        p1 = get_or_create(registry, p1_id, p1_name)
        if store_name and store_name not in p1["stores"]:
            p1["stores"].append(store_name)
        if event_date:
            p1["last_played"] = max(p1["last_played"], event_date) if p1["last_played"] else event_date

        # Determine outcome for event records
        if is_bye or not p2_id:
            if event_id:
                ensure_rec(p1_id, event_id)["wins"] += 1
            apply_match_to_track(p1["all"], p1_id, winner_id, p2_id, True, False,
                                  None, event_id, event_date)
            if sc:
                apply_match_to_track(p1["sc"], p1_id, winner_id, p2_id, True, False,
                                      None, event_id, event_date)
            processed += 1
            continue

        p2 = get_or_create(registry, p2_id, p2_name or "Unknown")
        if store_name and store_name not in p2["stores"]:
            p2["stores"].append(store_name)
        if event_date:
            p2["last_played"] = max(p2["last_played"], event_date) if p2["last_played"] else event_date

        # Event records (for all events)
        if event_id:
            r1, r2 = ensure_rec(p1_id, event_id), ensure_rec(p2_id, event_id)
            if is_draw:
                r1["draws"] += 1; r2["draws"] += 1
            elif winner_id == p1_id:
                r1["wins"] += 1; r2["losses"] += 1
            elif winner_id == p2_id:
                r2["wins"] += 1; r1["losses"] += 1

        # Apply to "all" track
        apply_match_to_track(p1["all"], p1_id, winner_id, p2_id, False, is_draw,
                              p2["all"], event_id, event_date)

        # Apply to "sc" track only for set-champ events
        if sc:
            apply_match_to_track(p1["sc"], p1_id, winner_id, p2_id, False, is_draw,
                                  p2["sc"], event_id, event_date)

        processed += 1

    # ---------------------------------------------------------------------------
    # Build leaderboard output
    # ---------------------------------------------------------------------------

    def build_event_records(pid):
        recs = event_records.get(pid, {})
        result = []
        for eid, rec in recs.items():
            ev = event_lookup.get(eid, {})
            result.append({
                "event_id": eid,
                "name": ev.get("name", "Unknown Event"),
                "date": ev.get("date", ""),
                "store": ev.get("store", ""),
                "is_set_champ": ev.get("is_set_champ", False),
                "wins": rec["wins"],
                "losses": rec["losses"],
                "draws": rec["draws"],
            })
        result.sort(key=lambda e: e["date"], reverse=True)
        return result

    def build_entry(pid, data):
        return {
            "player_id": pid,
            "name": data["name"],
            "username": usernames.get(str(pid), ""),
            "last_played": data["last_played"],
            "stores_played_at": data["stores"],
            "all": data["all"].to_dict(),
            "sc": data["sc"].to_dict(),
            "event_records": build_event_records(pid),
        }

    all_entries = [build_entry(pid, data) for pid, data in registry.items()]

    # Rank by "all" ELO first
    def ranked_list(entries, track_key):
        eligible = [e for e in entries if e[track_key]["total_matches"] >= MIN_MATCHES_FOR_RANKING]
        ineligible = [e for e in entries if e[track_key]["total_matches"] < MIN_MATCHES_FOR_RANKING]
        eligible.sort(key=lambda e: e[track_key]["elo"], reverse=True)
        ineligible.sort(key=lambda e: e[track_key]["elo"], reverse=True)
        for i, e in enumerate(eligible, 1):
            e[f"{track_key}_rank"] = i
        for e in ineligible:
            e[f"{track_key}_rank"] = None
        return eligible, ineligible

    all_ranked, all_unranked = ranked_list(all_entries, "all")
    sc_ranked, _ = ranked_list(all_entries, "sc")

    # Assign sc ranks (already set by ranked_list above)

    leaderboard = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total_players": len(all_entries),
        "ranked_players": len(all_ranked),
        "sc_ranked_players": len(sc_ranked),
        "total_matches_processed": processed,
        "min_matches_for_ranking": MIN_MATCHES_FOR_RANKING,
        "ranked": all_ranked,
        "unranked": all_unranked,
    }

    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(leaderboard, f, indent=2)

    print(f"Processed {processed} matches across {len(all_entries)} players")
    print(f"All-events ranked: {len(all_ranked)} | SC ranked: {len(sc_ranked)}")
    if all_ranked:
        print("\nTop 5 (all events):")
        for e in all_ranked[:5]:
            a = e["all"]
            print(f"  {e['name']}: ELO {a['elo']:.0f} ({a['record']}, {a['win_rate']:.1f}%)")
    if sc_ranked:
        print("\nTop 5 (set champs):")
        for e in sc_ranked[:5]:
            s = e["sc"]
            print(f"  {e['name']}: ELO {s['elo']:.0f} ({s['record']}, {s['win_rate']:.1f}%)")


if __name__ == "__main__":
    main()
