"""
pipeline/run_pipeline.py
════════════════════════════════════════════════════════════════════════
Master pipeline runner. Orchestrates:
  1. Fetch new results from football-data.org API
  2. Update Elo ratings
  3. Re-run Monte Carlo simulation (parallel), locking in real results
  4. Write champion_probabilities.json for React UI
════════════════════════════════════════════════════════════════════════
"""

import sys, os, json, pickle
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from itertools import combinations
from multiprocessing import Pool
import importlib.util

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
_WC_FIXTURES_CACHE = None

def _get_wc_fixtures():
    """Lazily load wc2026_fixtures.py's FIXTURES list (cached)."""
    global _WC_FIXTURES_CACHE
    if _WC_FIXTURES_CACHE is None:
        mod = load_module(ROOT / "pipeline/wc2026_fixtures.py", "wc2026_fixtures")
        _WC_FIXTURES_CACHE = mod.FIXTURES
    return _WC_FIXTURES_CACHE

elo_mod      = load_module(ROOT / "pipeline/update_elo.py", "update_elo")
update_elo   = elo_mod.run
load_ratings = elo_mod.load_ratings

MODEL_PATH    = ROOT / "data/processed/lgbm_model_v2.pkl"
FEATURES_PATH = ROOT / "data/processed/features_with_form.csv"
PROBS_PATH    = ROOT / "data/raw/future_match_probabilities_baseline.csv"
OUTPUT_JSON   = ROOT / "data/pipeline/champion_probabilities.json"
COMPLETED_RESULTS_PATH = ROOT / "data/pipeline/completed_results.json"
OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

N_SIMULATIONS     = 5_000
TOURNAMENT_WEIGHT = 5
WORLD_CUP_AVG_ELO = 1750

GROUPS = {
    "A": ["Mexico","South Africa","South Korea","Czechia"],
    "B": ["Canada","Bosnia and Herzegovina","Qatar","Switzerland"],
    "C": ["Brazil","Morocco","Haiti","Scotland"],
    "D": ["United States","Paraguay","Australia","Turkey"],
    "E": ["Germany","Curaçao","Ivory Coast","Ecuador"],
    "F": ["Netherlands","Japan","Sweden","Tunisia"],
    "G": ["Belgium","Egypt","Iran","New Zealand"],
    "H": ["Spain","Cape Verde","Saudi Arabia","Uruguay"],
    "I": ["France","Senegal","Iraq","Norway"],
    "J": ["Argentina","Algeria","Austria","Jordan"],
    "K": ["Portugal","DR Congo","Uzbekistan","Colombia"],
    "L": ["England","Croatia","Ghana","Panama"],
}

ROUND_ORDER = [
    "Group Stage","Round of 32","Round of 16",
    "Quarter-Final","Semi-Final","Final","Champion",
]

NAME_MAP = {
    "Czechia":"Czech Republic","Ivory Coast":"Ivory Coast",
    "Cape Verde":"Cape Verde","DR Congo":"DR Congo",
    "South Korea":"South Korea","New Zealand":"New Zealand",
    "United States":"United States","Bosnia and Herzegovina":"Bosnia and Herzegovina",
}

PLAYOFF_MAP = {
    "UEFA_Playoff_A":"Bosnia and Herzegovina","UEFA_Playoff_B":"Sweden",
    "UEFA_Playoff_C":"Turkey","UEFA_Playoff_D":"Czechia",
    "Interconf_Playoff_1":"DR Congo","Interconf_Playoff_2":"Iraq",
    "Cape_Verde":"Cape Verde","Côte d'Ivoire":"Ivory Coast",
}

_team_stats_g = _model_g = _features_g = _match_probs_g = _completed_g = None
_ko_lookup_g = _elimination_cap_g = None

def _init_worker(team_stats, model, features, match_probs, completed_results, ko_lookup, elimination_cap):
    global _team_stats_g, _model_g, _features_g, _match_probs_g, _completed_g
    global _ko_lookup_g, _elimination_cap_g
    _team_stats_g = team_stats; _model_g = model
    _features_g = features; _match_probs_g = match_probs
    _completed_g = completed_results
    _ko_lookup_g = ko_lookup; _elimination_cap_g = elimination_cap

def _sim_worker(_):
    return run_simulation(_team_stats_g, _model_g, _features_g, _match_probs_g, _completed_g, _ko_lookup_g, _elimination_cap_g)


# ── Completed results persistence ─────────────────────────────────────────────

def _load_completed_results() -> dict:
    """
    Returns dict keyed by (home_team, away_team) -> (home_score, away_score)
    for every Group Stage match that has actually been played.
    """
    if not COMPLETED_RESULTS_PATH.exists():
        return {}
    with open(COMPLETED_RESULTS_PATH) as f:
        data = json.load(f)
    results = {}
    for r in data:
        results[(r["home_team"], r["away_team"])] = (r["home_score"], r["away_score"])
    return results


def _append_completed_results(new_results: list[dict]):
    """
    Appends newly-finished matches to completed_results.json so future
    simulations lock in their real outcome instead of re-simulating.
    """
    existing = []
    if COMPLETED_RESULTS_PATH.exists():
        with open(COMPLETED_RESULTS_PATH) as f:
            existing = json.load(f)

    existing_keys = {(r["home_team"], r["away_team"]) for r in existing}

    for r in new_results:
        key = (r["home_team"], r["away_team"])
        if key not in existing_keys:
            existing.append({
                "home_team":  r["home_team"],
                "away_team":  r["away_team"],
                "home_score": r["home_score"],
                "away_score": r["away_score"],
                "stage":      r["stage"],
            })
            existing_keys.add(key)

    COMPLETED_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COMPLETED_RESULTS_PATH, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"  Saved {len(existing)} completed match result(s) → {COMPLETED_RESULTS_PATH}")


def get_team_stats(df, team, current_elo=None):
    csv_name  = NAME_MAP.get(team, team)
    home_rows = df[df["home_team"] == csv_name].copy()
    away_rows = df[df["away_team"] == csv_name].copy()
    home_rows["_side"] = "home"; away_rows["_side"] = "away"
    all_rows = pd.concat([home_rows, away_rows]).sort_values("date")
    stats = {"elo":1500.0,"form5":0.35,"weighted_form5":0.35,
             "goals_scored5":0.9,"goals_conceded5":1.4,
             "avg_opp_elo5":1500.0,"elo_momentum":0.0}
    if not all_rows.empty:
        last = all_rows.iloc[-1]; p = last["_side"]
        stats["elo"]             = last[f"{p}_elo"]
        stats["form5"]           = last[f"{p}_form5"]
        stats["weighted_form5"]  = last[f"{p}_weighted_form5"]
        stats["goals_scored5"]   = last[f"{p}_goals_scored5"]
        stats["goals_conceded5"] = last[f"{p}_goals_conceded5"]
        stats["avg_opp_elo5"]    = last[f"{p}_avg_opp_elo5"]
        stats["elo_momentum"]    = last[f"{p}_elo_momentum"]
    if current_elo is not None:
        stats["elo"] = current_elo
    return stats

def adjust_stats(stats):
    opp_elo = stats["avg_opp_elo5"]
    if opp_elo >= WORLD_CUP_AVG_ELO:
        stats["elo_momentum"] = max(-3.0, min(3.0, stats["elo_momentum"]))
        return stats
    ratio = opp_elo / WORLD_CUP_AVG_ELO
    adj = stats.copy()
    adj["goals_scored5"]   = stats["goals_scored5"]   * ratio
    adj["goals_conceded5"] = stats["goals_conceded5"] / ratio
    adj["form5"]           = stats["form5"]            * ratio
    adj["weighted_form5"]  = stats["weighted_form5"]   * ratio
    adj["elo_momentum"]    = max(-3.0, min(3.0, stats["elo_momentum"]))
    return adj

def build_features(hs, as_, feature_list):
    row = {
        "home_elo":hs["elo"],"away_elo":as_["elo"],
        "elo_diff":hs["elo"]-as_["elo"],
        "home_elo_momentum":hs["elo_momentum"],"away_elo_momentum":as_["elo_momentum"],
        "home_avg_opp_elo5":hs["avg_opp_elo5"],"away_avg_opp_elo5":as_["avg_opp_elo5"],
        "home_advantage":0,"tournament_weight":TOURNAMENT_WEIGHT,"month":6,
        "form_diff":hs["form5"]-as_["form5"],
        "weighted_form_diff":hs["weighted_form5"]-as_["weighted_form5"],
        "goals_diff":hs["goals_scored5"]-as_["goals_scored5"],
        "conceded_diff":hs["goals_conceded5"]-as_["goals_conceded5"],
    }
    return pd.DataFrame([{f: row[f] for f in feature_list}])

def predict(model, features, hs, as_, match_probs=None, home=None, away=None):
    if match_probs and home and away and (home,away) in match_probs:
        p = match_probs[(home,away)]; return p[0],p[1],p[2]
    X = build_features(hs, as_, features); p = model.predict_proba(X)[0]
    return p[2],p[1],p[0]

def sim_match(ph, pd_, pa):
    r = np.random.random()
    if r < ph: return "home"
    elif r < ph+pd_: return "draw"
    else: return "away"

def sim_group(teams, team_stats, model, features, match_probs, completed_results=None):
    """
    Simulates a group's round-robin. Matches that have already been played
    (present in completed_results) use the real final score instead of
    being re-simulated.
    """
    completed_results = completed_results or {}
    s = {t:{"pts":0,"gd":0,"gf":0} for t in teams}
    for home,away in combinations(teams,2):
        if (home,away) in completed_results:
            gh, ga = completed_results[(home,away)]
        elif (away,home) in completed_results:
            # stored with reversed home/away — flip scores back
            ga, gh = completed_results[(away,home)]
        else:
            ph,pd_,pa = predict(model,features,team_stats[home],team_stats[away],match_probs,home,away)
            outcome = sim_match(ph,pd_,pa)
            lh = max(0.3, team_stats[home]["goals_scored5"]*(1+(team_stats[home]["elo"]-team_stats[away]["elo"])/1000))
            la = max(0.3, team_stats[away]["goals_scored5"]*(1+(team_stats[away]["elo"]-team_stats[home]["elo"])/1000))
            gh,ga = np.random.poisson(lh),np.random.poisson(la)
            if outcome=="home" and gh<=ga: gh,ga=ga+1,max(0,ga-1)
            elif outcome=="away" and ga<=gh: ga,gh=gh+1,max(0,gh-1)
            elif outcome=="draw": ga=gh

        s[home]["gf"]+=gh; s[home]["gd"]+=gh-ga
        s[away]["gf"]+=ga; s[away]["gd"]+=ga-gh
        if gh>ga: s[home]["pts"]+=3
        elif ga>gh: s[away]["pts"]+=3
        else: s[home]["pts"]+=1; s[away]["pts"]+=1
    return s

def rank_group(s):
    return sorted(s, key=lambda t:(s[t]["pts"],s[t]["gd"],s[t]["gf"],np.random.random()), reverse=True)

def ko_match(a, b, team_stats, model, features):
    hs,as_ = team_stats[a],team_stats[b]
    ph,pd_,pa = predict(model,features,hs,as_)
    return a if np.random.random() < ph+pd_*0.5 else b

def run_simulation(team_stats, model, features, match_probs, completed_results=None, ko_lookup=None, elimination_cap=None):
    completed_results = completed_results or {}
    ko_lookup = ko_lookup or {}
    elimination_cap = elimination_cap or {}
    results = {t:"Group Stage" for g in GROUPS.values() for t in g}
    winners,runners,thirds = {},{},[]
    for gname,teams in GROUPS.items():
        s = sim_group(teams,team_stats,model,features,match_probs,completed_results)
        ranked = rank_group(s)
        winners[gname] = ranked[0]
        runners[gname] = ranked[1]
        thirds.append({"team":ranked[2],"pts":s[ranked[2]]["pts"],"gd":s[ranked[2]]["gd"],"gf":s[ranked[2]]["gf"]})
        results[ranked[0]]="Round of 32"; results[ranked[1]]="Round of 32"
    third_sorted = sorted(thirds,key=lambda x:(x["pts"],x["gd"],x["gf"],np.random.random()),reverse=True)
    for t in third_sorted[:8]: results[t["team"]]="Round of 32"

    def simulate_fn(a, b):
        return ko_match(a, b, team_stats, model, features)

    from pipeline.bracket_resolver import run_bracket
    bracket_results = run_bracket(
        winners, runners, third_sorted[:8], ko_lookup, simulate_fn,
    )
    results.update(bracket_results)

    for team in results:
        if team in elimination_cap:
            cap_round=elimination_cap[team]
            cap_idx=ROUND_ORDER.index(cap_round)
            actual_idx=ROUND_ORDER.index(results[team])
            if actual_idx>cap_idx:
                results[team]=cap_round
    return results

def _build_ko_position_map():
    """Build a position-based mapping from API fixtures to wc2026 match_nos,
    grouped by stage. When team-name resolution fails, this is the fallback."""
    from pipeline.api_client import load_fixtures_cache
    api_fixtures = load_fixtures_cache()
    wc_fixtures = _get_wc_fixtures()

    knockout_stages = {"Round of 32", "Round of 16", "Quarter-Final",
                       "Quarter-final", "Semi-Final", "Semi-final",
                       "Third-Place Play-off", "Third-place play-off", "Final"}

    api_by_stage = {}
    for f in api_fixtures:
        s = f["stage"]
        if s == "Group Stage" or s not in knockout_stages:
            continue
        api_by_stage.setdefault(s, []).append(f)

    wc_by_stage = {}
    for f in wc_fixtures:
        s = f["stage"]
        if s == "Group Stage" or s not in knockout_stages:
            continue
        wc_by_stage.setdefault(s, []).append(f)

    mapping = {}
    for stage in set(list(api_by_stage.keys()) + list(wc_by_stage.keys())):
        api_list = api_by_stage.get(stage, [])
        wc_list = wc_by_stage.get(stage, [])
        for i, af in enumerate(api_list):
            if i < len(wc_list):
                key = (af.get("team1", ""), af.get("team2", ""), stage)
                mapping[key] = wc_list[i]["match_no"]

    return mapping


def _record_missing_ko_results():
    """Check for completed knockout matches that are missing from match_results.json
    and record them. Uses team-name matching first, falls back to position-based mapping."""
    from pipeline.api_client import load_fixtures_cache
    from pipeline.knockout_tracker import save_result, resolve_fixture, load_results, load_results_from_db
    from pipeline.group_tracker import load_standings

    completed = _load_completed_results()
    if not completed:
        return 0

    ko_results = load_results_from_db()
    if not ko_results:
        ko_results = load_results()

    recorded = set()
    for r in ko_results.values():
        recorded.add(frozenset([r["home"], r["away"]]))

    fixtures = load_fixtures_cache()
    ko_fixtures = [f for f in fixtures if f["stage"] != "Group Stage"]

    position_map = _build_ko_position_map()
    results = load_results()
    standings = load_standings()
    wc_fixtures = _get_wc_fixtures()

    count = 0
    for af in ko_fixtures:
        t1, t2 = af.get("team1", "TBD"), af.get("team2", "TBD")
        if t1 == "TBD" or t2 == "TBD":
            continue
        teams = frozenset([t1, t2])
        if teams in recorded:
            continue
        stage = af["stage"]
        score = completed.get((t1, t2)) or completed.get((t2, t1))
        if score is None:
            continue

        match_no_found = None
        for f in wc_fixtures:
            if f["stage"] == "Group Stage" or f.get("group"):
                continue
            resolved = resolve_fixture(f, results, standings)
            if (resolved["team1"] == t1 and resolved["team2"] == t2) or \
               (resolved["team1"] == t2 and resolved["team2"] == t1):
                match_no_found = f["match_no"]
                break

        if match_no_found is None:
            match_no_found = position_map.get((t1, t2, stage)) or position_map.get((t2, t1, stage))

        if match_no_found is not None:
            hs, as_ = score
            save_result(match_no_found, t1, t2, hs, as_, stage)
            recorded.add(teams)
            count += 1
        else:
            print(f"  ⚠ Could not match knockout result {t1} vs {t2} to a fixture")

    return count


def run_pipeline(force_simulate=False):
    from pipeline.api_client import fetch_completed_matches, load_fixtures_cache
    from pipeline.group_tracker import update_group_standings
    from backend.save_probabilities import save_probabilities_to_db

    print(f"\n{'='*60}")
    print(f"WC 2026 Pipeline  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print(f"{'='*60}")

    new_results = fetch_completed_matches()

    if new_results:
        _append_completed_results(new_results)

        fixtures = load_fixtures_cache()
        for r in new_results:
            if r["stage"] == "Group Stage":
                match = next(
                    (f for f in fixtures
                     if f["team1"] == r["home_team"] and f["team2"] == r["away_team"]),
                    None
                )
                match_no = match["match_id"] if match else 0
                update_group_standings(
                    match_no, r["home_team"], r["away_team"],
                    r["home_score"], r["away_score"]
                )
            else:
                from pipeline.knockout_tracker import save_result, resolve_fixture, load_results
                from pipeline.group_tracker import load_standings

                wc_fixtures = elo_mod and _get_wc_fixtures()
                results   = load_results()
                standings = load_standings()

                match_no_found = None
                for f in wc_fixtures:
                    if f["stage"] == "Group Stage" or f.get("group"):
                        continue
                    resolved = resolve_fixture(f, results, standings)
                    if (resolved["team1"] == r["home_team"] and resolved["team2"] == r["away_team"]) or \
                       (resolved["team1"] == r["away_team"] and resolved["team2"] == r["home_team"]):
                        match_no_found = f["match_no"]
                        break

                if match_no_found is None:
                    position_map = _build_ko_position_map()
                    match_no_found = position_map.get(
                        (r["home_team"], r["away_team"], r["stage"])
                    ) or position_map.get(
                        (r["away_team"], r["home_team"], r["stage"])
                    )

                if match_no_found is None:
                    print(f"  ⚠ Could not match knockout result {r['home_team']} vs "
                          f"{r['away_team']} to a fixture — skipping bracket update")
                else:
                    save_result(
                        match_no_found, r["home_team"], r["away_team"],
                        r["home_score"], r["away_score"], r["stage"]
                    )
    if new_results:
        current_ratings = update_elo()
    else:
        current_ratings = load_ratings()

    if not new_results and not force_simulate:
        print("\nNo new results — skipping simulation.")
        return

    print("\n[Step 3] Loading model and running simulation...")
    with open(MODEL_PATH,"rb") as f: saved=pickle.load(f)
    model=saved["model"]; features=saved["features"]; model.n_jobs=1

    df=pd.read_csv(FEATURES_PATH); df["date"]=pd.to_datetime(df["date"])

    # NOTE: baseline_df / match_probs is pre-tournament group-stage data only.
    # Once the tournament starts, group match outcomes must be predicted from
    # LIVE Elo (via build_features), not these frozen pre-tournament numbers.
    # We keep loading it for reference/logging, but pass an empty dict to the
    # simulator so predict() always falls through to build_features().
    baseline_df=pd.read_csv(PROBS_PATH)
    match_probs = {}   # ← intentionally empty; live Elo drives all predictions now

    # Load all completed group-stage results (including from earlier runs)
    completed_results = _load_completed_results()
    if completed_results:
        print(f"  {len(completed_results)} completed match(es) locked into simulation:")
        for (h,a),(hs,as_) in completed_results.items():
            print(f"    {h} {hs}-{as_} {a}")

    # Reconcile: record any knockout results that are missing from match_results.json
    missing_ko = _record_missing_ko_results()
    if missing_ko:
        print(f"  Recorded {missing_ko} missing knockout result(s)")

    # Load knockout results to lock in real outcomes
    from pipeline.knockout_tracker import load_results as load_ko_results
    ko_data = load_ko_results()
    ko_lookup = {}
    elimination_cap = {}
    for mno, r in ko_data.items():
        teams = frozenset([r["home"], r["away"]])
        ko_lookup[teams] = r["winner"]
        loser = r["loser"]
        stage = r["stage"]
        if loser not in elimination_cap:
            elimination_cap[loser] = stage
    if ko_lookup:
        print(f"  {len(ko_lookup)} knockout result(s) locked into simulation. Capped teams:")
        for t, s in sorted(elimination_cap.items()):
            print(f"    {t} — eliminated at {s}")

    all_teams=[t for g in GROUPS.values() for t in g]
    team_stats={}
    for team in all_teams:
        stats=get_team_stats(df,team,current_elo=current_ratings.get(team))
        team_stats[team]=adjust_stats(stats)

    np.random.seed(None)
    n_workers = int(os.getenv("N_WORKERS", max(1, (os.cpu_count() or 2) - 1)))
    print(f"  Running {N_SIMULATIONS:,} simulations on {n_workers} cores...")
    counts={t:{r:0 for r in ROUND_ORDER} for t in all_teams}

    with Pool(processes=n_workers,initializer=_init_worker,
              initargs=(team_stats,model,features,match_probs,completed_results,ko_lookup,elimination_cap)) as pool:
        for i,sim in enumerate(pool.imap_unordered(_sim_worker,range(N_SIMULATIONS)),1):
            for team,furthest in sim.items():
                idx=ROUND_ORDER.index(furthest)
                for r in ROUND_ORDER[1:idx+1]: counts[team][r]+=1
            if i%1000==0: print(f"  {i:,}/{N_SIMULATIONS:,}...",flush=True)

    print(f"  {N_SIMULATIONS:,}/{N_SIMULATIONS:,} done!")

    output={"generated_at":datetime.utcnow().isoformat(),"simulations":N_SIMULATIONS,"teams":[]}
    for team in all_teams:
        group=next(g for g,teams in GROUPS.items() if team in teams)
        output["teams"].append({
            "team":team,"group":group,
            "elo":round(current_ratings.get(team,team_stats[team]["elo"]),1),
            "round_of_32":  round(counts[team]["Round of 32"]   /N_SIMULATIONS*100,1),
            "round_of_16":  round(counts[team]["Round of 16"]   /N_SIMULATIONS*100,1),
            "quarter_final":round(counts[team]["Quarter-Final"] /N_SIMULATIONS*100,1),
            "semi_final":   round(counts[team]["Semi-Final"]    /N_SIMULATIONS*100,1),
            "final":        round(counts[team]["Final"]         /N_SIMULATIONS*100,1),
            "champion":     round(counts[team]["Champion"]      /N_SIMULATIONS*100,1),
        })

    save_probabilities_to_db(output["teams"])
    print("Saved probabilities to Supabase")
    output["teams"].sort(key=lambda x:-x["champion"])

    with open(OUTPUT_JSON,"w") as f: json.dump(output,f,indent=2)
    print(f"\n✅ Done! Results → {OUTPUT_JSON}")
    print("\nTOP 5:")
    for t in output["teams"][:5]:
        print(f"  {t['team']:25s}  Champion: {t['champion']}%")

if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--force",action="store_true")
    args=parser.parse_args()
    run_pipeline(force_simulate=args.force)