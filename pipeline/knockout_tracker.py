"""
pipeline/knockout_tracker.py
Resolves "Winner Match 73" → actual team name using recorded results.
"""

import json
from pathlib import Path

RESULTS_PATH = Path("data/pipeline/match_results.json")
RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_results() -> dict:
    """Load all recorded match results keyed by match_id."""
    if not RESULTS_PATH.exists():
        return {}
    with open(RESULTS_PATH) as f:
        return json.load(f)


def save_result(match_id: int, home: str, away: str,
                home_score: int, away_score: int, stage: str):
    """Record a match result and determine winner/loser."""
    results = load_results()

    if home_score > away_score:
        winner, loser = home, away
    elif away_score > home_score:
        winner, loser = away, home
    else:
        # Penalties — you'll need to specify winner manually
        winner, loser = home, away  # default, update manually if needed

    results[str(match_id)] = {
        "match_id":   match_id,
        "home":       home,
        "away":       away,
        "home_score": home_score,
        "away_score": away_score,
        "winner":     winner,
        "loser":      loser,
        "stage":      stage,
    }

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"  Recorded Match {match_id}: {home} {home_score}-{away_score} {away} → Winner: {winner}")
    return winner


def resolve_team(placeholder: str, results: dict) -> str:
    """
    Converts "Winner Match 73" or "Loser Match 101" to actual team name.
    Returns the placeholder unchanged if match hasn't been played yet.
    """
    import re

    # Match "Winner Match 73"
    m = re.match(r"Winner Match (\d+)", placeholder)
    if m:
        match_id = m.group(1)
        if placeholder == "TBD":
            return "TBD"
        return placeholder

    # Match "Loser Match 101" (third-place play-off)
    m = re.match(r"Loser Match (\d+)", placeholder)
    if m:
        match_id = m.group(1)
        if match_id in results:
            return results[match_id]["loser"]
        return placeholder

    # Already a real team name
    return placeholder


def resolve_fixture(fixture: dict, results: dict) -> dict:
    """Returns fixture with placeholders replaced by real team names where known."""
    resolved = fixture.copy()
    resolved["team1"] = resolve_team(fixture["team1"], results)
    resolved["team2"] = resolve_team(fixture["team2"], results)
    return resolved


def get_upcoming_knockout_fixtures(fixtures: list) -> list:
    """
    Returns knockout fixtures where both teams are now known.
    Useful for the scraper to know what matches to look for.
    """
    results  = load_results()
    upcoming = []

    for f in fixtures:
        if f["stage"] in ("Group A","Group B","Group C","Group D",
                          "Group E","Group F","Group G","Group H",
                          "Group I","Group J","Group K","Group L"):
            continue  # skip group stage

        resolved = resolve_fixture(f, results)
        t1_known = not resolved["team1"].startswith(("Winner", "Loser"))
        t2_known = not resolved["team2"].startswith(("Winner", "Loser"))

        upcoming.append({
            **resolved,
            "both_teams_known": t1_known and t2_known,
        })

    return upcoming