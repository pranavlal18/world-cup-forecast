"""
pipeline/knockout_tracker.py
Resolves "Winner Match 73" → actual team name using recorded results.
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


def save_result(match_no: int, home: str, away: str,
                home_score: int, away_score: int, stage: str,
                penalty_winner: str | None = None):
    """
    Record a knockout match result and determine winner/loser.
    For draws (Third-Place/Final etc. that go to penalties), pass
    penalty_winner explicitly — otherwise winner defaults to `home`.
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
            print(f"  ⚠ Match {match_no} ended in a draw with no penalty_winner specified — "
                  f"defaulting winner to {home}. Update manually if incorrect.")
            winner, loser = home, away

    results[str(match_no)] = {
        "match_no":   match_no,
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

    print(f"  Recorded Match {match_no}: {home} {home_score}-{away_score} {away} → Winner: {winner}")
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
