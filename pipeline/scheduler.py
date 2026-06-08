"""
pipeline/scheduler.py
════════════════════════════════════════════════════════════════════════
Runs the full pipeline on a schedule.

Polling intervals:
  - 2  minutes  during a live match window (kickoff ± buffer)
  - 5  minutes  on a match day but outside a live window
  - 10 minutes  on non-match days

Match days and kickoff times are derived dynamically from FIXTURES
so no manual date maintenance is needed.

Usage:
    python pipeline/scheduler.py
════════════════════════════════════════════════════════════════════════
"""

import time
import schedule
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.run_pipeline import run_pipeline

# ── Load fixtures ─────────────────────────────────────────────────────────────
import importlib.util

def _load_fixtures():
    spec = importlib.util.spec_from_file_location(
        "wc2026_fixtures",
        ROOT / "pipeline/wc2026_fixtures.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.FIXTURES

FIXTURES = _load_fixtures()

# ── UTC offset map for all 16 venues ─────────────────────────────────────────
# Offsets are in hours relative to UTC (negative = behind UTC)
VENUE_UTC_OFFSET = {
    # EDT venues  UTC-4
    "MetLife Stadium":         -4,
    "Gillette Stadium":        -4,
    "Lincoln Financial Field": -4,
    "Hard Rock Stadium":       -4,
    "Mercedes-Benz Stadium":   -4,
    "BMO Field":               -4,
    # CDT venues  UTC-5
    "NRG Stadium":             -5,
    "AT&T Stadium":            -5,
    "Arrowhead Stadium":       -5,
    # PDT venues  UTC-7
    "SoFi Stadium":            -7,
    "Levi's Stadium":          -7,
    "BC Place":                -7,
    "Lumen Field":             -7,
    # Mexico venues  UTC-6
    "Estadio Azteca":          -6,
    "Estadio Akron":           -6,
    "Estadio BBVA":            -6,
}


# ── Dynamic match-day set ─────────────────────────────────────────────────────

def build_match_days() -> set:
    """
    Derives the set of all match dates directly from FIXTURES.
    Returns a set of 'YYYY-MM-DD' strings.
    """
    return {fixture["date"] for fixture in FIXTURES}

MATCH_DAYS = build_match_days()


# ── Live-window detection ─────────────────────────────────────────────────────

# In scheduler.py, replace get_live_window() with this:
def get_live_window(buffer_before: int = 60, buffer_after: int = 120) -> bool:
    """Uses UTC kickoff times from fixtures cache directly."""
    from pipeline.api_client import load_fixtures_cache
    now_utc = datetime.now(timezone.utc)
    today   = now_utc.strftime("%Y-%m-%d")

    fixtures = load_fixtures_cache()
    today_fixtures = [f for f in fixtures if f["date"] == today]

    for f in today_fixtures:
        h, m = map(int, f["time"].split(":"))
        kickoff_utc  = datetime.now(timezone.utc).replace(
            hour=h, minute=m, second=0, microsecond=0
        )
        window_start = kickoff_utc - timedelta(minutes=buffer_before)
        window_end   = kickoff_utc + timedelta(minutes=buffer_after)
        if window_start <= now_utc <= window_end:
            return True
    return False

# ── Match-day check ───────────────────────────────────────────────────────────

def is_match_day() -> bool:
    """Returns True if today (UTC) has at least one WC 2026 fixture."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return today in MATCH_DAYS


# ── Interval resolver ─────────────────────────────────────────────────────────

def get_poll_interval() -> int:
    """
    Returns the appropriate polling interval in minutes:
      2  — live match window active
      5  — match day but no live window
      10 — no matches today
    """
    if get_live_window():
        return 2
    if is_match_day():
        return 5
    return 10


# ── Pipeline job ──────────────────────────────────────────────────────────────

def job():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Scheduler triggered")
    try:
        from pipeline.api_client import save_fixtures_cache
        save_fixtures_cache()
        run_pipeline()
    except Exception as e:
        print(f"  ❌ Pipeline error: {e}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    print("WC 2026 Pipeline Scheduler started")
    print(f"  Total match days loaded from fixtures: {len(MATCH_DAYS)}")
    print(f"  First match day : {min(MATCH_DAYS)}")
    print(f"  Last  match day : {max(MATCH_DAYS)}")
    print(f"  Polling: 2 min (live) / 5 min (match day) / 10 min (idle)")

    # Run immediately on start
    job()

    current_interval = None

    while True:
        desired = get_poll_interval()

        # Only reschedule if the interval has changed
        if desired != current_interval:
            schedule.clear()
            schedule.every(desired).minutes.do(job)
            current_interval = desired
            print(
                f"  [{datetime.now().strftime('%H:%M:%S')}] "
                f"Poll interval → {desired} min "
                f"({'live' if desired == 2 else 'match day' if desired == 5 else 'idle'})"
            )

        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()