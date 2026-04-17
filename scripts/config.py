"""Configuration constants for the MN Lorcana leaderboard pipeline."""

import os

# API endpoints (no auth required)
API_BASE = "https://api.ravensburgerplay.com/api/v2"
PROXY_BASE = "https://cf-worker-middleware-hydra-prod.devion-villegas-76b.workers.dev/hydraproxy/api/v2"

EVENTS_URL = f"{PROXY_BASE}/events/"
EVENT_DETAIL_URL = f"{API_BASE}/events/{{event_id}}/"
MATCHES_URL = f"{API_BASE}/tournament-rounds/{{round_id}}/matches/paginated/"
STANDINGS_URL = f"{API_BASE}/tournament-rounds/{{round_id}}/standings/paginated/"
STORES_URL = f"{API_BASE}/game-stores/"

GAME_SLUG = "disney-lorcana"
STATE_FILTER = "MN"

# ELO settings
STARTING_ELO = 1200.0
K_FACTOR = 32
MIN_MATCHES_FOR_RANKING = 5

# Paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")

EVENTS_FILE = os.path.join(DATA_DIR, "events.json")
MATCHES_FILE = os.path.join(DATA_DIR, "matches.json")
LEADERBOARD_FILE = os.path.join(DATA_DIR, "leaderboard.json")
LAST_FETCH_FILE = os.path.join(DATA_DIR, "last_fetch.json")

# API request settings
PAGE_SIZE = 100
REQUEST_DELAY = 0.2  # seconds between API calls
REQUEST_TIMEOUT = 30

# Discord webhook (set via environment variable)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
