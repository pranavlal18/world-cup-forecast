"""
pipeline/group_tracker.py
Maintains group standings in Supabase (and local JSON as fallback).
"""

import json
import re
import importlib.util
from pathlib import Path

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

# ── Supabase read/write ────────────────────────────────────────────────────────

def _load_standings_from_db() -> dict | None:
    try:
        from backend.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT team, group_letter, played, won, drawn, lost,
                       gf, ga, gd, points
                FROM group_standings
            """)
            rows = cur.fetchall()
        if not rows:
            return None
        standings = {}
        for row in rows:
            team, g, played, won, drawn, lost, gf, ga, gd, points = row
            if g not in standings:
                standings[g] = {}
            standings[g][team] = {
                "team": team, "played": played, "won": won,
                "drawn": drawn, "lost": lost, "gf": gf,
                "ga": ga, "gd": gd, "points": points,
            }
        return standings
    except Exception as e:
        print(f"  ⚠ Could not load standings from DB: {e}")
        return None

def _save_standings_to_db(standings: dict):
    try:
        from backend.database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            for g, teams in standings.items():
                for team, r in teams.items():
                    cur.execute("""
                        INSERT INTO group_standings (
                            team, group_letter, played, won, drawn, lost,
                            gf, ga, gd, points
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (team) DO UPDATE SET
                            group_letter = EXCLUDED.group_letter,
                            played  = EXCLUDED.played,
                            won     = EXCLUDED.won,
                            drawn   = EXCLUDED.drawn,
                            lost    = EXCLUDED.lost,
                            gf      = EXCLUDED.gf,
                            ga      = EXCLUDED.ga,
                            gd      = EXCLUDED.gd,
                            points  = EXCLUDED.points
                    """, (
                        team, g, r["played"], r["won"], r["drawn"], r["lost"],
                        r["gf"], r["ga"], r["gd"], r["points"],
                    ))
        print("  Standings saved to Supabase ✅")
    except Exception as e:
        print(f"  ⚠ Could not save standings to DB: {e}")

# ── Persistence (DB first, JSON fallback) ─────────────────────────────────────

def load_standings() -> dict:
    db = _load_standings_from_db()
    if db:
        return db
    if STANDINGS_PATH.exists():
        with open(STANDINGS_PATH) as f:
            return json.load(f)
    blank = _blank_standings()
    _save_standings(blank)
    return blank

def _save_standings(standings: dict):
    # Save to both DB and local JSON
    _save_standings_to_db(standings)
    with open(STANDINGS_PATH, "w") as f:
        json.dump(standings, f, indent=2)

# ── Sorting ───────────────────────────────────────────────────────────────────

def get_sorted_group(group_letter: str, standings: dict) -> list:
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
    # Determine group by team membership instead of match_no lookup
    group_letter = None
    for g, teams in GROUP_TEAMS.items():
        if home in teams and away in teams:
            group_letter = g
            break

    if group_letter is None:
        print(f"  ⚠ Could not determine group for {home} vs {away}")
        return None

    standings = load_standings()

    if group_letter not in standings:
        standings[group_letter] = {
            team: _blank_team_row(team) for team in GROUP_TEAMS.get(group_letter, [])
        }

    grp = standings[group_letter]
    for team in (home, away):
        if team not in grp:
            grp[team] = _blank_team_row(team)

    h = grp[home]
    a = grp[away]

    h["played"] += 1;  a["played"] += 1
    h["gf"] += home_score;  h["ga"] += away_score
    a["gf"] += away_score;  a["ga"] += home_score
    h["gd"] = h["gf"] - h["ga"]
    a["gd"] = a["gf"] - a["ga"]

    if home_score > away_score:
        h["won"] += 1;  h["points"] += 3
        a["lost"] += 1
    elif away_score > home_score:
        a["won"] += 1;  a["points"] += 3
        h["lost"] += 1
    else:
        h["drawn"] += 1;  h["points"] += 1
        a["drawn"] += 1;  a["points"] += 1

    _save_standings(standings)
    print(f"  Group {group_letter} updated: {home} {home_score}–{away_score} {away}")
    return group_letter

# ── Resolve group slot ────────────────────────────────────────────────────────

def resolve_group_slot(placeholder: str, standings: dict) -> str:
    p = placeholder.strip()

    m = re.match(r"Group ([A-L]) winners?$", p, re.IGNORECASE)
    if m:
        g = m.group(1).upper()
        sorted_teams = get_sorted_group(g, standings)
        if not sorted_teams or sorted_teams[0]["played"] < 3:
            return placeholder
        return sorted_teams[0]["team"]

    m = re.match(r"Group ([A-L]) runners?-?up$", p, re.IGNORECASE)
    if m:
        g = m.group(1).upper()
        sorted_teams = get_sorted_group(g, standings)
        if len(sorted_teams) < 2 or sorted_teams[1]["played"] < 3:
            return placeholder
        return sorted_teams[1]["team"]

    m = re.match(r"Group ([A-L](?:/[A-L])+) third place$", p, re.IGNORECASE)
    if m:
        group_letters = [g.upper() for g in m.group(1).split("/")]
        third_place_rows = []
        for g in group_letters:
            sorted_teams = get_sorted_group(g, standings)
            if len(sorted_teams) < 3 or sorted_teams[2]["played"] < 3:
                return placeholder
            third_place_rows.append(sorted_teams[2])
        if not third_place_rows:
            return placeholder
        best = sorted(
            third_place_rows,
            key=lambda r: (r["points"], r["gd"], r["gf"]),
            reverse=True,
        )[0]
        return best["team"]

    return placeholder

# ── Pretty print ──────────────────────────────────────────────────────────────

def print_standings(group_letter: str | None = None):
    standings = load_standings()
    groups = [group_letter.upper()] if group_letter else sorted(standings.keys())
    for g in groups:
        print(f"\n  GROUP {g}")
        print(f"  {'Team':<28} {'P':>2} {'W':>2} {'D':>2} {'L':>2} {'GF':>3} {'GA':>3} {'GD':>4} {'Pts':>4}")
        print("  " + "─" * 58)
        for row in get_sorted_group(g, standings):
            print(f"  {row['team']:<28} {row['played']:>2} {row['won']:>2} "
                  f"{row['drawn']:>2} {row['lost']:>2} {row['gf']:>3} "
                  f"{row['ga']:>3} {row['gd']:>+4} {row['points']:>4}")

if __name__ == "__main__":
    print_standings()