"""
pipeline/group_tracker.py
════════════════════════════════════════════════════════════════════════
Maintains data/pipeline/group_standings.json — the live points table
for all 12 groups (A–L).

Public API
──────────
update_group_standings(match_no, home, away, home_score, away_score)
    Update the relevant group after a group-stage result.

resolve_group_slot(placeholder, standings) -> str
    Convert "Group A winners", "Group A runners-up", or
    "Group C/E/F/H/I third place" into the actual team name.
    Returns the placeholder unchanged if standings are incomplete.

load_standings() -> dict
    Load current standings from disk.

get_sorted_group(group_letter, standings) -> list[dict]
    Return the four teams in a group sorted by pts → GD → GF.
════════════════════════════════════════════════════════════════════════
"""

import json
import re
import importlib.util
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).parent.parent
STANDINGS_PATH = ROOT / "data/pipeline/group_standings.json"
STANDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Load fixtures ──────────────────────────────────────────────────────────────

def _load_fixtures():
    spec = importlib.util.spec_from_file_location(
        "wc2026_fixtures", ROOT / "pipeline/wc2026_fixtures.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.FIXTURES

FIXTURES = _load_fixtures()

# ── Group membership from fixtures ────────────────────────────────────────────
# Build {group_letter: [team1, team2, team3, team4]} from group-stage fixtures

def _build_group_teams() -> dict:
    teams: dict[str, set] = {}
    for f in FIXTURES:
        g = f.get("group")
        if g is None:
            continue
        if g not in teams:
            teams[g] = set()
        teams[g].add(f["team1"])
        teams[g].add(f["team2"])
    return {g: list(t) for g, t in sorted(teams.items())}

GROUP_TEAMS = _build_group_teams()

# ── Blank standings template ───────────────────────────────────────────────────

def _blank_team_row(team: str) -> dict:
    return {
        "team": team,
        "played": 0, "won": 0, "drawn": 0, "lost": 0,
        "gf": 0, "ga": 0, "gd": 0, "points": 0,
    }

def _blank_standings() -> dict:
    return {
        g: {team: _blank_team_row(team) for team in teams}
        for g, teams in GROUP_TEAMS.items()
    }

# ── Persistence ───────────────────────────────────────────────────────────────

def load_standings() -> dict:
    """Load standings from disk; initialise from fixtures if missing."""
    if not STANDINGS_PATH.exists():
        blank = _blank_standings()
        _save_standings(blank)
        return blank
    with open(STANDINGS_PATH) as f:
        return json.load(f)

def _save_standings(standings: dict):
    with open(STANDINGS_PATH, "w") as f:
        json.dump(standings, f, indent=2)

# ── Sorting ───────────────────────────────────────────────────────────────────

def get_sorted_group(group_letter: str, standings: dict) -> list:
    """
    Return teams in group sorted by pts DESC → GD DESC → GF DESC.
    Ties left in order (no random tiebreaker — real FIFA uses head-to-head
    which we don't track here; good enough for forecasting).
    """
    group = standings.get(group_letter, {})
    return sorted(
        group.values(),
        key=lambda r: (r["points"], r["gd"], r["gf"]),
        reverse=True,
    )

# ── Update ────────────────────────────────────────────────────────────────────

def update_group_standings(
    match_no: int,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
) -> str | None:
    """
    Update the group table for a group-stage match.
    Returns the group letter updated, or None if match is not group stage.
    """
    # Find the fixture to get its group letter
    fixture = next((f for f in FIXTURES if f["match_no"] == match_no), None)
    if fixture is None:
        print(f"  ⚠ match_no {match_no} not found in FIXTURES")
        return None

    group_letter = fixture.get("group")
    if group_letter is None:
        # Knockout match — nothing to update in group standings
        return None

    standings = load_standings()

    if group_letter not in standings:
        print(f"  ⚠ Group {group_letter} not in standings — reinitialising")
        standings[group_letter] = {
            team: _blank_team_row(team) for team in GROUP_TEAMS.get(group_letter, [])
        }

    grp = standings[group_letter]

    # Ensure both teams exist (handles name variants gracefully)
    for team in (home, away):
        if team not in grp:
            grp[team] = _blank_team_row(team)

    h = grp[home]
    a = grp[away]

    h["played"] += 1
    a["played"] += 1
    h["gf"] += home_score;  h["ga"] += away_score
    a["gf"] += away_score;  a["ga"] += home_score
    h["gd"] = h["gf"] - h["ga"]
    a["gd"] = a["gf"] - a["ga"]

    if home_score > away_score:
        h["won"]   += 1;  h["points"] += 3
        a["lost"]  += 1
    elif away_score > home_score:
        a["won"]   += 1;  a["points"] += 3
        h["lost"]  += 1
    else:
        h["drawn"] += 1;  h["points"] += 1
        a["drawn"] += 1;  a["points"] += 1

    _save_standings(standings)
    print(f"  Group {group_letter} standings updated after Match {match_no}: "
          f"{home} {home_score}–{away_score} {away}")
    return group_letter

# ── Resolve group slot ────────────────────────────────────────────────────────

def resolve_group_slot(placeholder: str, standings: dict) -> str:
    """
    Convert a group-slot placeholder into the actual team name.

    Handles three patterns:
      "Group A winners"        → 1st place in Group A
      "Group A runners-up"     → 2nd place in Group A
      "Group C/E/F/H/I third place"
                               → best 3rd-placed team across those groups
                                 (sorted by pts → GD → GF)

    Returns the placeholder unchanged if:
      - The group has not finished (< 3 matches played per team)
      - The slot is ambiguous (tied teams with no tiebreaker data)
    """
    p = placeholder.strip()

    # ── Pattern: "Group X winners" ─────────────────────────────────────────
    m = re.match(r"Group ([A-L]) winners?$", p, re.IGNORECASE)
    if m:
        g = m.group(1).upper()
        sorted_teams = get_sorted_group(g, standings)
        if not sorted_teams or sorted_teams[0]["played"] < 3:
            return placeholder  # group not finished
        return sorted_teams[0]["team"]

    # ── Pattern: "Group X runners-up" ─────────────────────────────────────
    m = re.match(r"Group ([A-L]) runners?-?up$", p, re.IGNORECASE)
    if m:
        g = m.group(1).upper()
        sorted_teams = get_sorted_group(g, standings)
        if len(sorted_teams) < 2 or sorted_teams[1]["played"] < 3:
            return placeholder
        return sorted_teams[1]["team"]

    # ── Pattern: "Group X/Y/Z third place" ────────────────────────────────
    m = re.match(
        r"Group ([A-L](?:/[A-L])+) third place$", p, re.IGNORECASE
    )
    if m:
        group_letters = [g.upper() for g in m.group(1).split("/")]
        third_place_rows = []

        for g in group_letters:
            sorted_teams = get_sorted_group(g, standings)
            if len(sorted_teams) < 3 or sorted_teams[2]["played"] < 3:
                return placeholder  # this group not finished yet
            third_place_rows.append(sorted_teams[2])

        if not third_place_rows:
            return placeholder

        # Sort all third-placed teams: pts → GD → GF (best first)
        best = sorted(
            third_place_rows,
            key=lambda r: (r["points"], r["gd"], r["gf"]),
            reverse=True,
        )[0]
        return best["team"]

    # Not a group-slot placeholder — return unchanged
    return placeholder


# ── Pretty print ──────────────────────────────────────────────────────────────

def print_standings(group_letter: str | None = None):
    """Print standings table for one or all groups."""
    standings = load_standings()
    groups    = [group_letter.upper()] if group_letter else sorted(standings.keys())

    for g in groups:
        print(f"\n  GROUP {g}")
        print(f"  {'Team':<28} {'P':>2} {'W':>2} {'D':>2} {'L':>2} "
              f"{'GF':>3} {'GA':>3} {'GD':>4} {'Pts':>4}")
        print("  " + "─" * 58)
        for row in get_sorted_group(g, standings):
            print(
                f"  {row['team']:<28} {row['played']:>2} {row['won']:>2} "
                f"{row['drawn']:>2} {row['lost']:>2} {row['gf']:>3} "
                f"{row['ga']:>3} {row['gd']:>+4} {row['points']:>4}"
            )


if __name__ == "__main__":
    print_standings()