"""Step 1: Discover completed Lorcana events at Minnesota stores.

Strategy: First discover all MN store IDs by scanning events, then fetch
events per store using the `store` filter param — much faster than paging
through 100K+ global events.
"""

import json
import os
import sys
import time
import requests

from config import (
    EVENTS_URL, EVENT_DETAIL_URL, GAME_SLUG, STATE_FILTER,
    PAGE_SIZE, REQUEST_DELAY, REQUEST_TIMEOUT,
    EVENTS_FILE, LAST_FETCH_FILE, DATA_DIR,
)
from models import Event

# Known MN store IDs (discovered from API). New stores are auto-discovered
# when events appear with state=MN.
MN_STORE_IDS = [
    19, 265, 595, 1329, 1331, 1333, 1334, 1421, 1579, 1941, 1973, 2047,
    2627, 2671, 2680, 2834, 3100, 4302, 4331, 4338, 4522, 4711, 4735,
    4767, 5253, 5282, 15874, 18292,
]


def load_existing_events():
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE) as f:
            return {e["event_id"]: Event.from_dict(e) for e in json.load(f)}
    return {}


def load_last_fetch():
    if os.path.exists(LAST_FETCH_FILE):
        with open(LAST_FETCH_FILE) as f:
            return json.load(f)
    return {"last_event_date": None, "known_store_ids": MN_STORE_IDS}


def save_last_fetch(cursor):
    with open(LAST_FETCH_FILE, "w") as f:
        json.dump(cursor, f, indent=2)


def fetch_events_for_store(store_id, page=1, start_date_after=None):
    """Fetch events for a specific store."""
    params = {
        "game_slug": GAME_SLUG,
        "store": store_id,
        "page": page,
        "page_size": PAGE_SIZE,
    }
    if start_date_after:
        params["start_date_after"] = start_date_after

    resp = requests.get(EVENTS_URL, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_event_detail(event_id):
    """Fetch detailed event info including tournament round IDs."""
    url = EVENT_DETAIL_URL.format(event_id=event_id)
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def extract_round_ids(event_detail):
    """Extract round IDs from event detail response."""
    round_ids = []
    for phase in event_detail.get("tournament_phases", []):
        for rnd in phase.get("rounds", []):
            round_ids.append(rnd["id"])
    return round_ids


def is_completed(event_data):
    status = (event_data.get("display_status") or "").upper()
    return status in ("COMPLETE", "COMPLETED", "FINISHED")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    existing = load_existing_events()
    cursor = load_last_fetch()
    store_ids = list(set(cursor.get("known_store_ids", []) + MN_STORE_IDS))

    print(f"Existing events: {len(existing)}")
    print(f"MN stores to scan: {len(store_ids)}")

    start_after = cursor.get("last_event_date")
    new_events = 0
    latest_date = start_after

    for store_id in store_ids:
        page = 1
        while True:
            time.sleep(REQUEST_DELAY)
            try:
                data = fetch_events_for_store(store_id, page=page, start_date_after=start_after)
            except requests.RequestException as e:
                print(f"  Error fetching store {store_id} page {page}: {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            for event_data in results:
                event_id = event_data.get("id")
                if not event_id or event_id in existing:
                    continue

                if not is_completed(event_data):
                    continue

                store = event_data.get("store") or {}
                store_name = store.get("name", "Unknown Store")
                store_state = (store.get("state") or "").upper()
                event_date = event_data.get("start_datetime", "")
                event_name = event_data.get("name", "")

                # Verify it's actually MN (in case store moved)
                if store_state != STATE_FILTER:
                    continue

                # Fetch detail to get round IDs
                time.sleep(REQUEST_DELAY)
                try:
                    detail = fetch_event_detail(event_id)
                    round_ids = extract_round_ids(detail)
                except requests.RequestException as e:
                    print(f"  Error fetching detail for event {event_id}: {e}")
                    round_ids = []

                # Skip events with no rounds (no tournament data)
                if not round_ids:
                    continue

                event = Event(
                    event_id=event_id,
                    name=event_name,
                    date=event_date,
                    store_name=store_name,
                    store_state=store_state,
                    status="COMPLETE",
                    round_ids=round_ids,
                    rounds_fetched=False,
                )
                existing[event_id] = event
                new_events += 1

                if event_date and (not latest_date or event_date > latest_date):
                    latest_date = event_date

                print(f"  {event_name} at {store_name} ({event_date[:10]}) — {len(round_ids)} rounds")

            next_page = data.get("next_page_number")
            if not next_page:
                break
            page += 1

    # Save results
    all_events = sorted(existing.values(), key=lambda e: e.date)
    with open(EVENTS_FILE, "w") as f:
        json.dump([e.to_dict() for e in all_events], f, indent=2)

    save_last_fetch({
        "last_event_date": latest_date,
        "known_store_ids": store_ids,
    })

    print(f"\nDone! {new_events} new MN events found. Total: {len(existing)}")
    return new_events


if __name__ == "__main__":
    new = main()
    sys.exit(0 if new >= 0 else 1)
