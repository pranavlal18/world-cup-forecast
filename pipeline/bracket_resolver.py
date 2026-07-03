"""
pipeline/bracket_resolver.py
Resolves the actual FIFA bracket from wc2026_fixtures.py using simulated
group standings and knockout results. Used by both simulator.py and
run_pipeline.py to ensure bracket structure matches real tournament.
"""
import re
from pipeline.wc2026_fixtures import FIXTURES as WC_FIXTURES


def _build_sim_standings(group_winners, group_runners, third_place_teams):
    """
    Convert simulation group results into the standings format
    that resolve_group_slot expects.
    """
    standings = {}
    for g, winner in group_winners.items():
        standings[g] = {}
        standings[g][winner] = {
            "team": winner, "played": 3, "won": 3, "drawn": 0, "lost": 0,
            "points": 9, "gd": 99, "gf": 99,
        }
        runner = group_runners.get(g)
        if runner:
            standings[g][runner] = {
                "team": runner, "played": 3, "won": 2, "drawn": 0, "lost": 1,
                "points": 6, "gd": 50, "gf": 50,
            }
        for t in third_place_teams:
            if t["team"] not in [winner, runner]:
                standings[g][t["team"]] = {
                    "team": t["team"], "played": 3,
                    "won": 0, "drawn": 0, "lost": 3,
                    "points": t["pts"], "gd": t["gd"], "gf": t["gf"],
                }
                break
    return standings


def _resolve_group_slot(placeholder, standings):
    """Resolve group-based placeholders using simulated standings."""
    p = placeholder.strip()

    m = re.match(r"Group ([A-L]) winners?$", p, re.IGNORECASE)
    if m:
        g = m.group(1).upper()
        if g in standings:
            sorted_teams = sorted(
                standings[g].values(),
                key=lambda r: (r["points"], r["gd"], r["gf"]),
                reverse=True,
            )
            if sorted_teams:
                return sorted_teams[0]["team"]
        return placeholder

    m = re.match(r"Group ([A-L]) runners?-?up$", p, re.IGNORECASE)
    if m:
        g = m.group(1).upper()
        if g in standings:
            sorted_teams = sorted(
                standings[g].values(),
                key=lambda r: (r["points"], r["gd"], r["gf"]),
                reverse=True,
            )
            if len(sorted_teams) >= 2:
                return sorted_teams[1]["team"]
        return placeholder

    m = re.match(r"Group ([A-L](?:/[A-L])+) third place$", p, re.IGNORECASE)
    if m:
        group_letters = [g.upper() for g in m.group(1).split("/")]
        third_place_rows = []
        for g in group_letters:
            if g in standings:
                sorted_teams = sorted(
                    standings[g].values(),
                    key=lambda r: (r["points"], r["gd"], r["gf"]),
                    reverse=True,
                )
                if len(sorted_teams) >= 3:
                    third_place_rows.append(sorted_teams[2])
        if third_place_rows:
            best = sorted(
                third_place_rows,
                key=lambda r: (r["points"], r["gd"], r["gf"]),
                reverse=True,
            )
            return best[0]["team"]
        return placeholder

    return placeholder


def _resolve_placeholder(placeholder, standings, ko_results):
    """Resolve any placeholder (group or Winner Match N) to a real team."""
    p = placeholder.strip()
    if p == "TBD":
        return placeholder

    if p.startswith("Group "):
        return _resolve_group_slot(p, standings)

    m = re.match(r"Winner Match (\d+)", p)
    if m:
        match_no = m.group(1)
        if match_no in ko_results:
            return ko_results[match_no]["winner"]
        return placeholder

    m = re.match(r"Loser Match (\d+)", p)
    if m:
        match_no = m.group(1)
        if match_no in ko_results:
            return ko_results[match_no]["loser"]
        return placeholder

    return placeholder


def _is_resolved(name):
    """Check if a name is a real team (not a placeholder)."""
    if name == "TBD":
        return False
    if name.startswith("Group ") or name.startswith("Winner") or name.startswith("Loser"):
        return False
    return True


def run_bracket(group_winners, group_runners, third_place_teams,
                ko_lookup, simulate_fn):
    """
    Simulate the full FIFA bracket using actual bracket structure.

    Args:
        group_winners: dict {group_letter: team_name}
        group_runners: dict {group_letter: team_name}
        third_place_teams: list of {"team", "pts", "gd", "gf"}
        ko_lookup: dict {frozenset([team_a, team_b]): winner} for real results
        simulate_fn: callable(team_a, team_b) -> winner

    Returns:
        dict with all results keyed by team -> furthest round reached
    """
    import numpy as np

    standings = _build_sim_standings(group_winners, group_runners, third_place_teams)

    results = {}
    knockout_fixtures = [f for f in WC_FIXTURES if f["stage"] != "Group Stage"
                         and not f["stage"].startswith("Group ")
                         and f["stage"] not in ("Third-place play-off", "Third-Place Play-off")]
    knockout_fixtures.sort(key=lambda f: f["match_no"])

    ko_results = {}
    round_fixtures = {}
    round_winners = {}

    STAGE_NORM = {
        "Round of 32":  "Round of 32",
        "Round of 16":  "Round of 16",
        "Quarter-final": "Quarter-Final",
        "Quarter-Final": "Quarter-Final",
        "Semi-final":   "Semi-Final",
        "Semi-Final":   "Semi-Final",
        "Final":        "Final",
    }

    for fixture in knockout_fixtures:
        mno = fixture["match_no"]
        stage = fixture["stage"]

        t1 = _resolve_placeholder(fixture["team1"], standings, ko_results)
        t2 = _resolve_placeholder(fixture["team2"], standings, ko_results)

        if not _is_resolved(t1) or not _is_resolved(t2):
            round_fixtures[mno] = (t1, t2)
            round_winners[mno] = None
            continue

        teams = frozenset([t1, t2])
        if teams in ko_lookup:
            winner = ko_lookup[teams]
        else:
            winner = simulate_fn(t1, t2)

        loser = t2 if winner == t1 else t1
        ko_results[str(mno)] = {
            "winner": winner, "loser": loser,
            "home": t1, "away": t2,
        }
        round_fixtures[mno] = (t1, t2)
        round_winners[mno] = winner

        norm_stage = STAGE_NORM.get(stage, stage)
        results[winner] = norm_stage
        results[loser] = norm_stage

    final_fixtures = [f for f in knockout_fixtures if f["stage"] == "Final"]
    if final_fixtures:
        final_mno = str(final_fixtures[0]["match_no"])
        if final_mno in ko_results:
            results[ko_results[final_mno]["winner"]] = "Champion"

    return results
