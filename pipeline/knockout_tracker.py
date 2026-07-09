"""
pipeline/knockout_tracker.py
Resolves "Winner Match 73" -> actual team name using recorded results.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
RESULTS_PATH = ROOT / "data/pipeline/match_results.json"
RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_results() -> dict:
    """Load all recorded knockout match results keyed by match_no (str)."""
    if not RESULTS_PATH.exists():
        return {}
    with open(RESULTS_PATH) as f:
        return json.load(f)


def _save_result_to_db(match_no, home, away, home_score, away_score, winner, loser, stage):
    """Write a knockout result to the Supabase knockout_results table."""
    try:
        from backend.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO knockout_results (match_no, home, away, home_score, away_score, winner, loser, stage)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (match_no) DO UPDATE SET
                    home = EXCLUDED.home,
                    away = EXCLUDED.away,
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    winner = EXCLUDED.winner,
                    loser = EXCLUDED.loser,
                    stage = EXCLUDED.stage,
                    recorded_at = NOW()
            """, (match_no, home, away, home_score, away_score, winner, loser, stage))
    except Exception as e:
        print(f"  Warning: could not write match {match_no} to database: {e}")


def load_results_from_db() -> dict:
    """Load knockout results from Supabase. Returns {} if table doesn't exist."""
    try:
        from backend.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT match_no, home, away, home_score, away_score, winner, loser, stage FROM knockout_results")
            rows = cur.fetchall()
        return {
            str(r[0]): {
                "match_no": r[0], "home": r[1], "away": r[2],
                "home_score": r[3], "away_score": r[4],
                "winner": r[5], "loser": r[6], "stage": r[7],
            }
            for r in rows
        }
    except Exception:
        return {}


def save_result(match_no: int, home: str, away: str,
                home_score: int, away_score: int, stage: str,
                penalty_winner: str | None = None):
    """
    Record a knockout match result and determine winner/loser.
    Writes to both local JSON file and Supabase database.
    """
    results = load_results()

    if home_score > away_score:
        winner, loser = home, away
    elif away_score > home_score:
        winner, loser = away, home
    else:
        if penalty_winner:
            winner = penalty_winner
            loser = away if winner == home else home
        else:
            print(f"   Match {match_no} ended in a draw with no penalty_winner specified — "
                  f"defaulting winner to {home}. Update manually if incorrect.")
            winner, loser = home, away

    entry = {
        "match_no":   match_no,
        "home":       home,
        "away":       away,
        "home_score": home_score,
        "away_score": away_score,
        "winner":     winner,
        "loser":      loser,
        "stage":      stage,
    }

    results[str(match_no)] = entry
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)

    _save_result_to_db(match_no, home, away, home_score, away_score, winner, loser, stage)

    print(f"  Recorded Match {match_no}: {home} {home_score}-{away_score} {away} -> Winner: {winner}")
    return winner


def resolve_team(placeholder: str, results: dict, standings: dict | None = None) -> str:
    """
    Converts a bracket placeholder to a real team name if known, otherwise
    returns the placeholder unchanged.

    Handles:
      - "Winner Match N"
      - "Loser Match N"
      - "Group X winners" / "Group X runners-up" / "Group A/B/C third place"
        (delegated to group_tracker.resolve_group_slot)
      - Already-resolved real team names (returned as-is)
    """
    p = placeholder.strip()

    m = re.match(r"Winner Match (\d+)", p)
    if m:
        match_no = m.group(1)
        if match_no in results:
            return results[match_no]["winner"]
        return placeholder

    m = re.match(r"Loser Match (\d+)", p)
    if m:
        match_no = m.group(1)
        if match_no in results:
            return results[match_no]["loser"]
        return placeholder

    if p.startswith("Group "):
        from pipeline.group_tracker import resolve_group_slot, load_standings
        st = standings if standings is not None else load_standings()
        return resolve_group_slot(p, st)

    # Already a real team name
    return placeholder


def resolve_fixture(fixture: dict, results: dict, standings: dict | None = None) -> dict:
    """Returns fixture with placeholders replaced by real team names where known."""
    resolved = fixture.copy()
    resolved["team1"] = resolve_team(fixture["team1"], results, standings)
    resolved["team2"] = resolve_team(fixture["team2"], results, standings)
    return resolved


def get_bracket(fixtures: list) -> list:
    """
    Returns ALL knockout fixtures (Round of 32 through Final) with
    placeholders resolved as far as currently possible, plus a
    `both_teams_known` flag and `is_played` flag.
    """
    from pipeline.group_tracker import load_standings

    results   = load_results()
    standings = load_standings()
    bracket   = []

    knockout_stages = {
        "Round of 32", "Round of 16", "Quarter-final",
        "Semi-final", "Third-place play-off", "Final",
    }

    for f in fixtures:
        if f["stage"] not in knockout_stages:
            continue

        resolved = resolve_fixture(f, results, standings)
        t1_known = not (resolved["team1"].startswith("Group ") or resolved["team1"].startswith(("Winner", "Loser")))
        t2_known = not (resolved["team2"].startswith("Group ") or resolved["team2"].startswith(("Winner", "Loser")))

        match_result = results.get(str(f["match_no"]))

        bracket.append({
            **resolved,
            "both_teams_known": t1_known and t2_known,
            "is_played": match_result is not None,
            "result": match_result,
        })

    return bracket


def get_upcoming_knockout_fixtures(fixtures: list) -> list:
    """
    Returns knockout fixtures where both teams are now known but the
    match hasn't been played yet. Useful for knowing what to look for
    in the API next.
    """
    return [f for f in get_bracket(fixtures) if f["both_teams_known"] and not f["is_played"]]
