"""Fetch PlayHub usernames for all known players via event registrations.

The match endpoint only returns truncated real names (e.g. "Ernest P").
The registrations endpoint returns the actual PlayHub username (e.g. "Ep3").
We build a player_id -> username map and save it to data/usernames.json.
"""

import json
import os
import sys
import time
import requests

from config import (
    API_BASE, REQUEST_DELAY, REQUEST_TIMEOUT,
    EVENTS_FILE, DATA_DIR,
)

USERNAMES_FILE = os.path.join(DATA_DIR, "usernames.json")
REGISTRATIONS_URL = API_BASE + "/events/{event_id}/registrations/"


def load_existing():
    if os.path.exists(USERNAMES_FILE):
        with open(USERNAMES_FILE) as f:
            return json.load(f)
    return {}  # {str(player_id): username}


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(EVENTS_FILE):
        print("No events file found. Run fetch_events.py first.")
        return

    with open(EVENTS_FILE) as f:
        events = json.load(f)

    usernames = load_existing()
    new_found = 0

    for event in events:
        eid = event["event_id"]
        page = 1
        while True:
            time.sleep(REQUEST_DELAY)
            url = REGISTRATIONS_URL.format(event_id=eid)
            try:
                resp = requests.get(url, params={"page": page, "page_size": 100}, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  Error fetching registrations for event {eid}: {e}")
                break

            results = resp.json().get("results", [])
            if not results:
                break

            for reg in results:
                uid = reg.get("user", {}).get("id")
                username = reg.get("best_identifier", "").strip()
                if uid and username:
                    key = str(uid)
                    if key not in usernames:
                        usernames[key] = username
                        new_found += 1
                    # Always update to latest username in case it changed
                    else:
                        usernames[key] = username

            if not resp.json().get("next_page_number"):
                break
            page += 1

    with open(USERNAMES_FILE, "w") as f:
        json.dump(usernames, f, indent=2, sort_keys=True)

    print(f"Done! {new_found} new usernames. Total: {len(usernames)}")


if __name__ == "__main__":
    main()
