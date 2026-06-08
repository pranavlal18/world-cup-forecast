# backend/routers/bracket.py
from fastapi import APIRouter
from pathlib import Path
import json

router = APIRouter()
FIXTURES_CACHE = Path("data/cache/fixtures.json")
RESULTS_PATH   = Path("data/pipeline/match_results.json")
PROBS_PATH     = Path("data/pipeline/champion_probabilities.json")

@router.get("/")
def get_bracket():
    with open(FIXTURES_CACHE) as f:
        fixtures = json.load(f)["fixtures"]

    results = {}
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            results = json.load(f)

    probs = {}
    if PROBS_PATH.exists():
        with open(PROBS_PATH) as f:
            data = json.load(f)
            probs = {t["team"]: t["champion"] for t in data["teams"]}

    knockout_stages = [
        "Round of 32", "Round of 16",
        "Quarter-Final", "Semi-Final", "Final"
    ]

    bracket = {}
    for stage in knockout_stages:
        stage_fixtures = [f for f in fixtures if f["stage"] == stage]
        matches = []
        for f in stage_fixtures:
            match_result = results.get(str(f["match_id"]), {})
            matches.append({
                "match_id":       f["match_id"],
                "date":           f["date"],
                "time":           f["time"],
                "team1":          f["team1"],
                "team2":          f["team2"],
                "score1":         match_result.get("home_score"),
                "score2":         match_result.get("away_score"),
                "winner":         match_result.get("winner"),
                "status":         f["status"],
                "team1_champion": probs.get(f["team1"]),
                "team2_champion": probs.get(f["team2"]),
            })
        bracket[stage] = matches

    return bracket