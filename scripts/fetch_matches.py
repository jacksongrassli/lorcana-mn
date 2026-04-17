"""Step 2: Fetch match-level data for all tournament rounds."""

import json
import os
import sys
import time
import requests

from config import (
    MATCHES_URL, REQUEST_DELAY, REQUEST_TIMEOUT,
    EVENTS_FILE, MATCHES_FILE, DATA_DIR,
)
from models import Match


def load_events():
    """Load events with round IDs."""
    if not os.path.exists(EVENTS_FILE):
        print("No events file found. Run fetch_events.py first.")
        return []
    with open(EVENTS_FILE) as f:
        return json.load(f)


def load_existing_matches():
    """Load previously fetched matches."""
    if os.path.exists(MATCHES_FILE):
        with open(MATCHES_FILE) as f:
            return json.load(f)
    return []


def fetch_round_matches(round_id, page=1):
    """Fetch matches for a tournament round."""
    url = MATCHES_URL.format(round_id=round_id)
    params = {"page": page, "page_size": 100}
    resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def parse_match(match_data, event_id, event_name, event_date, round_id, round_number, store_name):
    """Parse a match from the API response into our Match model."""
    match_id = match_data.get("id", 0)

    # Extract player info from player_match_relationships
    relationships = match_data.get("player_match_relationships", [])
    if not relationships and match_data.get("playerMatchRelationships"):
        relationships = match_data["playerMatchRelationships"]

    player1_id = None
    player1_name = None
    player2_id = None
    player2_name = None

    for i, rel in enumerate(relationships):
        player = rel.get("player", {})
        pid = player.get("id")
        pname = (
            player.get("best_identifier")
            or player.get("bestIdentifier")
            or player.get("name")
            or f"Player {pid}"
        )
        if i == 0:
            player1_id = pid
            player1_name = pname
        elif i == 1:
            player2_id = pid
            player2_name = pname

    # Determine winner and match type
    winning_player = (
        match_data.get("winning_player")
        or match_data.get("winningPlayer")
    )

    is_bye = bool(
        match_data.get("match_is_bye")
        or match_data.get("matchIsBye")
    )

    is_draw = bool(
        match_data.get("match_is_intentional_draw")
        or match_data.get("matchIsIntentionalDraw")
        or match_data.get("match_is_unintentional_draw")
        or match_data.get("matchIsUnintentionalDraw")
    )

    games_won_by_winner = (
        match_data.get("games_won_by_winner")
        or match_data.get("gamesWonByWinner")
        or 0
    )
    games_won_by_loser = (
        match_data.get("games_won_by_loser")
        or match_data.get("gamesWonByLoser")
        or 0
    )

    # Only include completed matches
    status = match_data.get("status", "").upper()
    if status not in ("COMPLETE", "COMPLETED", ""):
        return None

    return Match(
        match_id=match_id,
        event_id=event_id,
        event_name=event_name,
        event_date=event_date,
        round_id=round_id,
        round_number=round_number,
        player1_id=player1_id,
        player1_name=player1_name,
        player2_id=player2_id,
        player2_name=player2_name,
        winner_id=winning_player,
        is_bye=is_bye,
        is_draw=is_draw,
        games_won_by_winner=games_won_by_winner,
        games_won_by_loser=games_won_by_loser,
        store_name=store_name,
    )


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    events = load_events()
    existing_matches = load_existing_matches()

    # Build set of already-fetched round IDs
    fetched_round_ids = set()
    for m in existing_matches:
        fetched_round_ids.add(m["round_id"])

    new_matches = []
    events_to_update = []

    for event in events:
        event_id = event["event_id"]
        round_ids = event.get("round_ids", [])

        if event.get("rounds_fetched"):
            continue

        if not round_ids:
            continue

        unfetched = [rid for rid in round_ids if rid not in fetched_round_ids]
        if not unfetched:
            event["rounds_fetched"] = True
            events_to_update.append(event)
            continue

        print(f"Fetching matches for: {event['name']} ({len(unfetched)} rounds)")

        all_rounds_ok = True
        for round_id in unfetched:
            page = 1
            while True:
                time.sleep(REQUEST_DELAY)
                try:
                    data = fetch_round_matches(round_id, page=page)
                except requests.RequestException as e:
                    print(f"  Error fetching round {round_id}: {e}")
                    all_rounds_ok = False
                    break

                results = data.get("results", [])
                if not results:
                    break

                for match_data in results:
                    # Determine round number from the event's round list
                    round_number = round_ids.index(round_id) + 1 if round_id in round_ids else 0

                    match = parse_match(
                        match_data,
                        event_id=event_id,
                        event_name=event["name"],
                        event_date=event["date"],
                        round_id=round_id,
                        round_number=round_number,
                        store_name=event["store_name"],
                    )
                    if match:
                        new_matches.append(match.to_dict())

                # Check for next page
                next_page = data.get("next_page_number") or data.get("next")
                if not next_page:
                    break
                page += 1

            fetched_round_ids.add(round_id)

        if all_rounds_ok:
            event["rounds_fetched"] = True
            events_to_update.append(event)

    # Save updated matches
    all_matches = existing_matches + new_matches
    with open(MATCHES_FILE, "w") as f:
        json.dump(all_matches, f, indent=2)

    # Update events with rounds_fetched flag
    if events_to_update:
        updated_map = {e["event_id"]: e for e in events_to_update}
        for i, event in enumerate(events):
            if event["event_id"] in updated_map:
                events[i] = updated_map[event["event_id"]]
        with open(EVENTS_FILE, "w") as f:
            json.dump(events, f, indent=2)

    print(f"\nDone! {len(new_matches)} new matches fetched. Total: {len(all_matches)}")
    return len(new_matches)


if __name__ == "__main__":
    new = main()
    sys.exit(0 if new >= 0 else 1)
