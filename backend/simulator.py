"""
backend/simulator.py  —  Monte Carlo simulation runner.
Runs in a background thread to avoid blocking the API.
"""

import numpy as np
import pandas as pd
import asyncio
from datetime import datetime
from itertools import combinations
from multiprocessing import Pool
from .config import GROUPS, ROUND_ORDER, N_SIMULATIONS, TOURNAMENT_WEIGHT
from backend.database import get_db


# ── Module-level globals for multiprocessing worker ───────────────────────────
_team_stats  = None
_model       = None
_features    = None
_match_probs = None


def _pool_initializer(team_stats, model, features, match_probs):
    global _team_stats, _model, _features, _match_probs
    _team_stats  = team_stats
    _model       = model
    _features    = features
    _match_probs = match_probs


def _run_sim_wrapper(_):
    return _run_single_simulation(_team_stats, _model, _features, _match_probs)


# ── Core simulation logic ─────────────────────────────────────────────────────

def _build_match_features(home_stats, away_stats, feature_list):
    row = {
        "home_elo":           home_stats["elo"],
        "away_elo":           away_stats["elo"],
        "elo_diff":           home_stats["elo"] - away_stats["elo"],
        "home_elo_momentum":  home_stats["elo_momentum"],
        "away_elo_momentum":  away_stats["elo_momentum"],
        "home_avg_opp_elo5":  home_stats["avg_opp_elo5"],
        "away_avg_opp_elo5":  away_stats["avg_opp_elo5"],
        "home_advantage":     0,
        "tournament_weight":  TOURNAMENT_WEIGHT,
        "month":              6,
        "form_diff":          home_stats["form5"] - away_stats["form5"],
        "weighted_form_diff": home_stats["weighted_form5"] - away_stats["weighted_form5"],
        "goals_diff":         home_stats["goals_scored5"] - away_stats["goals_scored5"],
        "conceded_diff":      home_stats["goals_conceded5"] - away_stats["goals_conceded5"],
    }
    return pd.DataFrame([{f: row[f] for f in feature_list}])


def _predict_match(model, features, hs, as_, home_team=None, away_team=None, match_probs=None):
    X = _build_match_features(hs, as_, features)
    probs = model.predict_proba(X)[0]

    return probs[2], probs[1], probs[0]

def _simulate_match(p_home, p_draw, p_away):
    r = np.random.random()
    if r < p_home:           return "home"
    elif r < p_home + p_draw: return "draw"
    else:                     return "away"


def _simulate_group(group_teams, team_stats, model, features, match_probs):
    standings = {t: {"pts": 0, "gd": 0, "gf": 0} for t in group_teams}
    for home, away in combinations(group_teams, 2):
        hs, as_ = team_stats[home], team_stats[away]
        p_h, p_d, p_a = _predict_match(
            model, features, hs, as_,
            home_team=home, away_team=away, match_probs=match_probs
        )
        outcome = _simulate_match(p_h, p_d, p_a)
        lam_h = max(0.3, hs["goals_scored5"] * (1 + (hs["elo"] - as_["elo"]) / 1000))
        lam_a = max(0.3, as_["goals_scored5"] * (1 + (as_["elo"] - hs["elo"]) / 1000))
        gh = np.random.poisson(lam_h)
        ga = np.random.poisson(lam_a)
        if outcome == "home" and gh <= ga:
            gh, ga = ga + 1, max(0, ga - 1)
        elif outcome == "away" and ga <= gh:
            ga, gh = gh + 1, max(0, gh - 1)
        elif outcome == "draw":
            ga = gh
        standings[home]["gf"] += gh; standings[home]["gd"] += gh - ga
        standings[away]["gf"] += ga; standings[away]["gd"] += ga - gh
        if outcome == "home":        standings[home]["pts"] += 3
        elif outcome == "away":      standings[away]["pts"] += 3
        else: standings[home]["pts"] += 1; standings[away]["pts"] += 1
    return standings


def _rank_group(standings):
    return sorted(
        standings.keys(),
        key=lambda t: (standings[t]["pts"], standings[t]["gd"], standings[t]["gf"], np.random.random()),
        reverse=True,
    )


def _simulate_knockout_match(team_a, team_b, team_stats, model, features):
    hs, as_ = team_stats[team_a], team_stats[team_b]
    p_h, p_d, p_a = _predict_match(model, features, hs, as_)
    p_h_adj = p_h + p_d * 0.5
    return team_a if np.random.random() < p_h_adj else team_b


def _run_single_simulation(team_stats, model, features, match_probs):
    results = {t: "Group Stage" for g in GROUPS.values() for t in g}
    group_winners, group_runners, third_place_teams = {}, {}, []

    for gname, teams in GROUPS.items():
        standings = _simulate_group(teams, team_stats, model, features, match_probs)
        ranked = _rank_group(standings)
        group_winners[gname] = ranked[0]
        group_runners[gname] = ranked[1]
        third_place_teams.append({
            "team": ranked[2], "pts": standings[ranked[2]]["pts"],
            "gd":  standings[ranked[2]]["gd"], "gf": standings[ranked[2]]["gf"],
        })
        results[ranked[0]] = "Round of 32"
        results[ranked[1]] = "Round of 32"

    third_sorted = sorted(
        third_place_teams,
        key=lambda x: (x["pts"], x["gd"], x["gf"], np.random.random()),
        reverse=True,
    )
    for t in third_sorted[:8]:
        results[t["team"]] = "Round of 32"

    r32_teams = []
    group_order = list(GROUPS.keys())
    for i in range(0, len(group_order), 2):
        g1, g2 = group_order[i], group_order[i + 1]
        r32_teams.append((group_winners[g1], group_runners[g2]))
        r32_teams.append((group_winners[g2], group_runners[g1]))

    third_qualifiers = [t["team"] for t in third_sorted[:8]]
    for i in range(0, len(third_qualifiers), 2):
        if i + 1 < len(third_qualifiers):
            r32_teams.append((third_qualifiers[i], third_qualifiers[i + 1]))

    def play_round(matchups, round_name):
        winners = []
        for a, b in matchups:
            w = _simulate_knockout_match(a, b, team_stats, model, features)
            results[w] = round_name
            winners.append(w)
        return winners

    r16  = play_round(r32_teams, "Round of 16")
    qf   = play_round([(r16[i], r16[i+1]) for i in range(0, len(r16), 2)], "Quarter-Final")
    sf   = play_round([(qf[i],  qf[i+1])  for i in range(0, len(qf),  2)], "Semi-Final")
    fin  = play_round([(sf[i],  sf[i+1])  for i in range(0, len(sf),  2)], "Final")
    if len(fin) >= 2:
        champ = _simulate_knockout_match(fin[0], fin[1], team_stats, model, features)
        results[champ] = "Champion"

    return results


# ── Background runner ─────────────────────────────────────────────────────────
async def run_simulation_background(state):
    if state.sim_running:
        return
    state.sim_running = True
    state.sim_progress = 0
    loop = asyncio.get_event_loop()

    try:
        counts = await loop.run_in_executor(
            None,
            _run_mc_sync,
            state,
        )

        probs = {}
        all_teams = [t for g in GROUPS.values() for t in g]
        for team in all_teams:
            probs[team] = {}
            for r in ROUND_ORDER[1:]:
                probs[team][r] = round(counts[team][r] / N_SIMULATIONS * 100, 1)

        state.probabilities = probs

        conn = get_db()
        cur = conn.cursor()

        cur.execute("DELETE FROM probabilities")

        for team, rounds in probs.items():
            cur.execute("""
                INSERT INTO probabilities (
                    team,
                    round_of_32,
                    round_of_16,
                    quarter_final,
                    semi_final,
                    final,
                    champion
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                team,
                rounds.get("Round of 32", 0),
                rounds.get("Round of 16", 0),
                rounds.get("Quarter-Final", 0),
                rounds.get("Semi-Final", 0),
                rounds.get("Final", 0),
                rounds.get("Champion", 0),
            ))

        conn.commit()
        conn.close()
        state.save_cache()
        state.last_sim_run  = datetime.utcnow()
        state.n_simulations_run = N_SIMULATIONS
        print(f"Simulation complete — {N_SIMULATIONS:,} runs")

    finally:
        state.sim_running = False


def _run_mc_sync(state):
    import os
    team_stats  = state.team_stats
    model       = state.model
    features    = state.features
    match_probs = state.match_probs

    all_teams = [t for g in GROUPS.values() for t in g]
    counts = {t: {r: 0 for r in ROUND_ORDER} for t in all_teams}

    n_workers = max(1, os.cpu_count() - 1)
    print(f"  Simulating on {n_workers} cores...", flush=True)

    with Pool(
        processes=n_workers,
        initializer=_pool_initializer,
        initargs=(team_stats, model, features, match_probs),
    ) as pool:
        for i, sim_results in enumerate(
            pool.imap_unordered(_run_sim_wrapper, range(N_SIMULATIONS)), 1
        ):
            for team, furthest in sim_results.items():
                idx = ROUND_ORDER.index(furthest)
                for r in ROUND_ORDER[1:idx + 1]:
                    counts[team][r] += 1
            state.sim_progress = i
            if i % 2000 == 0:
                print(f"  {i:,}/{N_SIMULATIONS:,}...", flush=True)

    return counts