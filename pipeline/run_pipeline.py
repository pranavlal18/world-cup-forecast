"""
pipeline/run_pipeline.py
Master pipeline runner.
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

elo_mod      = load_module(ROOT / "pipeline/update_elo.py", "update_elo")
update_elo   = elo_mod.run
load_ratings = elo_mod.load_ratings

MODEL_PATH    = ROOT / "data/processed/lgbm_model_v2.pkl"
FEATURES_PATH = ROOT / "data/processed/features_with_form.csv"
PROBS_PATH    = ROOT / "data/raw/future_match_probabilities_baseline.csv"
OUTPUT_JSON   = ROOT / "data/pipeline/champion_probabilities.json"
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

_team_stats_g = _model_g = _features_g = _match_probs_g = None

def _init_worker(team_stats, model, features, match_probs):
    global _team_stats_g, _model_g, _features_g, _match_probs_g
    _team_stats_g = team_stats; _model_g = model
    _features_g = features; _match_probs_g = match_probs

def _sim_worker(_):
    return run_simulation(_team_stats_g, _model_g, _features_g, _match_probs_g)

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

def sim_group(teams, team_stats, model, features, match_probs):
    s = {t:{"pts":0,"gd":0,"gf":0} for t in teams}
    for home,away in combinations(teams,2):
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
        if outcome=="home": s[home]["pts"]+=3
        elif outcome=="away": s[away]["pts"]+=3
        else: s[home]["pts"]+=1; s[away]["pts"]+=1
    return s

def rank_group(s):
    return sorted(s, key=lambda t:(s[t]["pts"],s[t]["gd"],s[t]["gf"],np.random.random()), reverse=True)

def ko_match(a, b, team_stats, model, features):
    hs,as_ = team_stats[a],team_stats[b]
    ph,pd_,pa = predict(model,features,hs,as_)
    return a if np.random.random() < ph+pd_*0.5 else b

def run_simulation(team_stats, model, features, match_probs):
    results = {t:"Group Stage" for g in GROUPS.values() for t in g}
    winners,thirds = {},[]
    for gname,teams in GROUPS.items():
        s = sim_group(teams,team_stats,model,features,match_probs)
        ranked = rank_group(s)
        winners[gname] = ranked[0]
        thirds.append({"team":ranked[2],"pts":s[ranked[2]]["pts"],"gd":s[ranked[2]]["gd"],"gf":s[ranked[2]]["gf"]})
        results[ranked[0]]="Round of 32"; results[ranked[1]]="Round of 32"
    third_sorted = sorted(thirds,key=lambda x:(x["pts"],x["gd"],x["gf"],np.random.random()),reverse=True)
    for t in third_sorted[:8]: results[t["team"]]="Round of 32"
    r32=[]; gkeys=list(GROUPS.keys())
    runners={gname:rank_group(sim_group(GROUPS[gname],team_stats,model,features,match_probs))[1] for gname in gkeys}
    for i in range(0,len(gkeys),2):
        g1,g2=gkeys[i],gkeys[i+1]
        r32.append((winners[g1],runners[g2])); r32.append((winners[g2],runners[g1]))
    tq=[t["team"] for t in third_sorted[:8]]
    for i in range(0,len(tq),2):
        if i+1<len(tq): r32.append((tq[i],tq[i+1]))
    def play(matchups,rname):
        w=[]
        for a,b in matchups:
            winner=ko_match(a,b,team_stats,model,features)
            results[winner]=rname; w.append(winner)
        return w
    r16=play(r32,"Round of 16")
    qf=play([(r16[i],r16[i+1]) for i in range(0,len(r16),2)],"Quarter-Final")
    sf=play([(qf[i],qf[i+1])   for i in range(0,len(qf),2)], "Semi-Final")
    fn=play([(sf[i],sf[i+1])   for i in range(0,len(sf),2)], "Final")
    if len(fn)>=2:
        champ=ko_match(fn[0],fn[1],team_stats,model,features); results[champ]="Champion"
    return results

def run_pipeline(force_simulate=False):
    from pipeline.api_client import fetch_completed_matches, load_fixtures_cache
    from pipeline.group_tracker import update_group_standings
    from backend.save_probabilities import save_probabilities_to_db

    print(f"\n{'='*60}")
    print(f"WC 2026 Pipeline  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print(f"{'='*60}")

    new_results = fetch_completed_matches()

    if new_results:
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

    if new_results or force_simulate:
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

    baseline_df=pd.read_csv(PROBS_PATH); match_probs={}
    for _,row in baseline_df.iterrows():
        home=PLAYOFF_MAP.get(row["home_team"],row["home_team"])
        away=PLAYOFF_MAP.get(row["away_team"],row["away_team"])
        match_probs[(home,away)]=(row["p_home_win"],row["p_draw"],row["p_away_win"])

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
              initargs=(team_stats,model,features,match_probs)) as pool:
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