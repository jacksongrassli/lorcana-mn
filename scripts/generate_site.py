"""Step 4: Copy leaderboard and events data to docs/ for GitHub Pages."""

import json
import os
import shutil

from config import LEADERBOARD_FILE, EVENTS_FILE, MATCHES_FILE, DOCS_DIR

SET_CHAMP_KEYWORDS = ["set championship", "store championship", "set champ"]


def is_set_champ(name):
    n = (name or "").lower()
    return any(k in n for k in SET_CHAMP_KEYWORDS)


def main():
    docs_data = os.path.join(DOCS_DIR, "data")
    os.makedirs(docs_data, exist_ok=True)

    if not os.path.exists(LEADERBOARD_FILE):
        print("No leaderboard.json found. Run calculate_elo.py first.")
        return

    dest = os.path.join(docs_data, "leaderboard.json")
    shutil.copy2(LEADERBOARD_FILE, dest)

    # Build clean events list for the events page
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE) as f:
            raw_events = json.load(f)

        # Count matches per event
        match_counts = {}
        player_sets = {}
        if os.path.exists(MATCHES_FILE):
            with open(MATCHES_FILE) as f:
                for m in json.load(f):
                    eid = m.get("event_id")
                    if eid:
                        match_counts[eid] = match_counts.get(eid, 0) + 1
                        player_sets.setdefault(eid, set())
                        if m.get("player1_id"):
                            player_sets[eid].add(m["player1_id"])
                        if m.get("player2_id"):
                            player_sets[eid].add(m["player2_id"])

        events_out = []
        for e in raw_events:
            eid = e["event_id"]
            events_out.append({
                "event_id": eid,
                "name": e["name"],
                "date": (e.get("date") or "")[:10],
                "store": e.get("store_name", ""),
                "is_set_champ": is_set_champ(e["name"]),
                "matches": match_counts.get(eid, 0),
                "players": len(player_sets.get(eid, set())),
            })

        # Sort newest first
        events_out.sort(key=lambda e: e["date"], reverse=True)

        with open(os.path.join(docs_data, "events.json"), "w") as f:
            json.dump(events_out, f, indent=2)

        sc_count = sum(1 for e in events_out if e["is_set_champ"])
        print(f"Wrote {len(events_out)} events ({sc_count} set champs) to docs/data/events.json")

    with open(LEADERBOARD_FILE) as f:
        data = json.load(f)
    print(f"Copied leaderboard to {dest}")
    print(f"  Ranked players: {data.get('ranked_players', 0)}")
    print(f"  Total players: {data.get('total_players', 0)}")
    print(f"  Matches processed: {data.get('total_matches_processed', 0)}")


if __name__ == "__main__":
    main()
