"""
pipeline/api_client.py
════════════════════════════════════════════════════════════════════════
Football-data.org API client for WC 2026.
Replaces scraper.py entirely.

Phases implemented:
  Phase 1 — fetch_completed_matches() replaces scrape()
  Phase 2 — save_fixtures_cache() replaces wc2026_fixtures.py
  Phase 3 — processed-match tracking prevents duplicate Elo updates

Usage:
    from pipeline.api_client import fetch_completed_matches
    new_results = fetch_completed_matches()

Environment:
    Set FOOTBALL_DATA_API_KEY in your .env file or environment.
    Free tier: 10 req/min, full WC access confirmed.
════════════════════════════════════════════════════════════════════════
"""

import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()
# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT             = Path(__file__).parent.parent
CACHE_DIR        = ROOT / "data" / "cache"
FIXTURES_CACHE   = CACHE_DIR / "fixtures.json"
PROCESSED_PATH   = CACHE_DIR / "processed_matches.json"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── API config ─────────────────────────────────────────────────────────────────
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
BASE_URL     = "https://api.football-data.org/v4"
COMPETITION  = "WC"
SEASON       = 2026
REQUEST_DELAY = 6   # seconds between requests (free tier: 10 req/min)

# ── Stage label map → your pipeline's stage names ─────────────────────────────
STAGE_MAP = {
    "GROUP_STAGE":        "Group Stage",
    "LAST_32":            "Round of 32",
    "LAST_16":            "Round of 16",
    "QUARTER_FINALS":     "Quarter-Final",
    "SEMI_FINALS":        "Semi-Final",
    "THIRD_PLACE":        "Third-Place Play-off",
    "FINAL":              "Final",
}

# ── Team name normalisation → your GROUPS names ───────────────────────────────
TEAM_NAME_MAP = {
    "USA":                          "United States",
    "United States":                "United States",
    "Korea Republic":               "South Korea",
    "IR Iran":                      "Iran",
    "Côte d'Ivoire":                "Ivory Coast",
    "Cote d'Ivoire":                "Ivory Coast",
    "Congo DR":                     "DR Congo",
    "Democratic Republic of Congo": "DR Congo",
    "Bosnia & Herzegovina":         "Bosnia and Herzegovina",
    "Czech Republic":               "Czechia",
    "Curacao":                      "Curaçao",
    "Cape Verde Islands":           "Cape Verde",
}

def _normalise(name) -> str:
    """Normalise team name; returns 'TBD' for None (knockout placeholder)."""
    if name is None:
        return "TBD"
    return TEAM_NAME_MAP.get(name.strip(), name.strip())


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = None) -> dict:
    """Make a single authenticated GET request with basic retry."""
    if not API_KEY:
        raise EnvironmentError(
            "FOOTBALL_DATA_API_KEY is not set. "
            "Add it to your .env file or environment variables."
        )
    url     = f"{BASE_URL}/{endpoint}"
    headers = {"X-Auth-Token": API_KEY}

    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 429:
                wait = int(resp.headers.get("X-RequestCounter-Reset", 60))
                print(f"  Rate limited — waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"  API request failed (attempt {attempt+1}/3): {e}")
            time.sleep(REQUEST_DELAY * (attempt + 1))

    raise RuntimeError(f"API request failed after 3 attempts: {endpoint}")


# ── Phase 1: Fetch matches ────────────────────────────────────────────────────

def fetch_all_matches() -> list[dict]:
    """
    Fetch all 104 WC 2026 matches from football-data.org.
    Returns raw API match objects.
    """
    data = _get(
        f"competitions/{COMPETITION}/matches",
        params={"season": SEASON},
    )
    return data.get("matches", [])


def _transform_match(match: dict) -> dict:
    """
    Transform a football-data.org match object into the format
    expected by update_elo.py:
      home_team, away_team, home_score, away_score, stage, date, source
    """
    home = _normalise((match.get("homeTeam") or {}).get("name"))
    away = _normalise((match.get("awayTeam") or {}).get("name"))
    score = match.get("score", {})
    ft    = score.get("fullTime", {})

    # Use fullTime score; fall back to regularTime
    home_score = ft.get("home") or score.get("regularTime", {}).get("home", 0) or 0
    away_score = ft.get("away") or score.get("regularTime", {}).get("away", 0) or 0

    stage_raw = match.get("stage", "GROUP_STAGE")
    stage     = STAGE_MAP.get(stage_raw, "Group Stage")

    date_raw = match.get("utcDate", "")
    date     = date_raw[:10] if date_raw else ""

    return {
        "match_id":   match["id"],
        "home_team":  home,
        "away_team":  away,
        "home_score": int(home_score),
        "away_score": int(away_score),
        "stage":      stage,
        "date":       date,
        "source":     "football-data.org",
    }


def fetch_completed_matches() -> list[dict]:
    """
    Phase 1 + Phase 3:
    Fetch finished matches not yet processed.
    Returns a list of dicts in the same format as scraper.run().
    Saves new_results.csv for update_elo.py compatibility.
    """
    print(f"  [{datetime.now().strftime('%H:%M:%S')}] Fetching from football-data.org...")

    try:
        all_matches = fetch_all_matches()
    except Exception as e:
        print(f"  ❌ API fetch failed: {e}")
        return []

    finished = [m for m in all_matches if m.get("status") == "FINISHED"]
    print(f"  Found {len(finished)} finished match(es) in API")

    # Phase 3: filter out already-processed match IDs
    processed = _load_processed()
    new = [
        m for m in finished
        if m["id"] not in processed
    ]
    print(f"  {len(new)} new (unprocessed) match(es)")

    if not new:
        return []

    transformed = [_transform_match(m) for m in new]

    # Save to new_results.csv (update_elo.py reads this)
    _save_new_results_csv(transformed)

    # Phase 3: mark these matches as processed
    _mark_processed([m["id"] for m in new])

    return transformed


def fetch_live_matches() -> list[dict]:
    """
    Returns matches currently in play.
    Useful for future live score tracking.
    """
    try:
        all_matches = fetch_all_matches()
    except Exception as e:
        print(f"  ❌ API fetch failed: {e}")
        return []

    live = [m for m in all_matches if m.get("status") == "IN_PLAY"]
    return [_transform_match(m) for m in live]


# ── Phase 2: Fixtures cache ───────────────────────────────────────────────────

def save_fixtures_cache() -> list[dict]:
    """
    Phase 2: Fetch all fixtures from API and save to data/cache/fixtures.json.
    The scheduler can load this instead of wc2026_fixtures.py.
    Returns the list of fixture dicts in the same shape as wc2026_fixtures.py.
    """
    print("  Fetching fixtures from football-data.org for cache...")
    all_matches = fetch_all_matches()

    fixtures = []
    for m in all_matches:
        date_utc  = m.get("utcDate", "")
        date_str  = date_utc[:10]
        time_str  = date_utc[11:16] if len(date_utc) >= 16 else "00:00"
        stage_raw = m.get("stage", "GROUP_STAGE")
        group_raw = m.get("group")                 # e.g. "GROUP_A" or None
        group_letter = group_raw.replace("GROUP_", "") if group_raw else None

        fixtures.append({
            "match_id":  m["id"],
            "date":      date_str,
            "time":      time_str,                 # UTC
            "time_tz":   "UTC",
            "stage":     STAGE_MAP.get(stage_raw, stage_raw),
            "group":     group_letter,
            "team1":     _normalise((m.get("homeTeam") or {}).get("name")),
            "team2":     _normalise((m.get("awayTeam") or {}).get("name")),
            "venue":     m.get("venue", ""),
            "status":    m.get("status", ""),
        })

    fixtures.sort(key=lambda x: (x["date"], x["time"]))

    with open(FIXTURES_CACHE, "w") as f:
        json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(), "fixtures": fixtures}, f, indent=2)

    print(f"  Saved {len(fixtures)} fixtures → {FIXTURES_CACHE}")
    return fixtures


def load_fixtures_cache() -> list[dict]:
    """
    Load fixtures from cache. Refreshes from API if cache is missing.
    Use this in scheduler.py instead of importing wc2026_fixtures.py.
    """
    if not FIXTURES_CACHE.exists():
        print("  Fixtures cache missing — fetching from API...")
        return save_fixtures_cache()
    with open(FIXTURES_CACHE) as f:
        data = json.load(f)
    return data.get("fixtures", [])


# ── Phase 3: Processed match tracking ────────────────────────────────────────

# Replace _load_processed() with:
def _load_processed() -> set:
    from backend.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT match_id FROM processed_matches")
        return {row[0] for row in cur.fetchall()}

# Replace _mark_processed() with:
def _mark_processed(match_ids: list):
    from backend.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.executemany(
            "INSERT INTO processed_matches (match_id) VALUES (%s) ON CONFLICT DO NOTHING",
            [(mid,) for mid in match_ids]
        )

def reset_processed():
    """
    Clear processed match history — use if you need to rerun Elo
    from scratch (e.g. after fixing team name mappings).
    """
    if PROCESSED_PATH.exists():
        PROCESSED_PATH.unlink()
    print("  Processed match history cleared.")


# ── CSV helper (update_elo.py compatibility) ──────────────────────────────────
def save_fixtures_to_db(fixtures):
    from backend.database import get_db

    with get_db() as conn:
        cur = conn.cursor()

        for f in fixtures:
            cur.execute("""
                INSERT INTO fixtures (
                    match_id,
                    date,
                    time_utc,
                    stage,
                    group_letter,
                    team1,
                    team2,
                    status
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (match_id)
                DO UPDATE SET
                    date = EXCLUDED.date,
                    time_utc = EXCLUDED.time_utc,
                    stage = EXCLUDED.stage,
                    group_letter = EXCLUDED.group_letter,
                    team1 = EXCLUDED.team1,
                    team2 = EXCLUDED.team2,
                    status = EXCLUDED.status
            """, (
                int(f["match_id"]),
                f["date"],
                f["time"],
                f["stage"],
                f["group"],
                f["team1"],
                f["team2"],
                f["status"]
            ))

def _save_new_results_csv(results: list[dict]):
    """Write new_results.csv in the format expected by update_elo.py."""
    import csv
    csv_path = ROOT / "data" / "pipeline" / "new_results.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fields = ["home_team", "away_team", "home_score", "away_score",
              "stage", "date", "source"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"  Saved {len(results)} result(s) → {csv_path}")


# ── CLI helpers ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="football-data.org API client")
    parser.add_argument("--fetch",    action="store_true", help="Fetch completed matches")
    parser.add_argument("--cache",    action="store_true", help="Refresh fixtures cache")
    parser.add_argument("--live",     action="store_true", help="Show live matches")
    parser.add_argument("--reset",    action="store_true", help="Reset processed match history")
    parser.add_argument("--status",   action="store_true", help="Show processed match count")
    args = parser.parse_args()

    if args.reset:
        reset_processed()

    elif args.cache:
        fixtures = save_fixtures_cache( )
        save_fixtures_to_db(fixtures)
        print(f"Saved {len(fixtures)} fixtures to database")
        print(f"Last  fixture: {fixtures[-1]}")

    elif args.live:
        live = fetch_live_matches()
        if live:
            for m in live:
                print(f"  🔴 LIVE: {m['home_team']} vs {m['away_team']}")
        else:
            print("  No matches currently live.")

    elif args.fetch:
        results = fetch_completed_matches()
        if results:
            for r in results:
                print(f"  ✅ {r['home_team']} {r['home_score']}–{r['away_score']} {r['away_team']} ({r['stage']})")
        else:
            print("  No new completed matches.")

    elif args.status:
        processed = _load_processed()
        print(f"  Processed matches: {len(processed)}")
        if processed:
            print(f"  IDs: {sorted(processed)}")

    else:
        parser.print_help()

