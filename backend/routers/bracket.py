# backend/routers/bracket.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json

router = APIRouter()

ROOT = Path(__file__).parent.parent.parent
PROBS_PATH = ROOT / "data/pipeline/champion_probabilities.json"
FIXTURES_CACHE = ROOT / "data/cache/fixtures.json"


def _load_api_fixtures() -> list[dict]:
    if not FIXTURES_CACHE.exists():
        return []
    with open(FIXTURES_CACHE) as f:
        data = json.load(f)
    return data.get("fixtures", [])


def _load_match_results() -> dict:
    try:
        from pipeline.knockout_tracker import load_results
        return load_results()
    except Exception:
        return {}


@router.get("/")
def get_bracket():
    probs = {}
    if PROBS_PATH.exists():
        with open(PROBS_PATH) as f:
            data = json.load(f)
            probs = {t["team"]: t["champion"] for t in data["teams"]}

    api_fixtures = _load_api_fixtures()
    if not api_fixtures:
        raise HTTPException(status_code=503, detail="Fixtures not available")

    stage_map = {
        "Round of 32":          "Round of 32",
        "Round of 16":          "Round of 16",
        "Quarter-Final":        "Quarter-final",
        "Quarter-final":        "Quarter-final",
        "Semi-Final":           "Semi-final",
        "Semi-final":           "Semi-final",
        "Third-Place Play-off": "Third-place play-off",
        "Third-place play-off": "Third-place play-off",
        "Final":                "Final",
    }

    ko_stages = [
        "Round of 32", "Round of 16",
        "Quarter-final", "Semi-final",
        "Third-place play-off", "Final",
    ]

    bracket = {stage: [] for stage in ko_stages}
    match_results = _load_match_results()

    for f in api_fixtures:
        raw_stage = f["stage"]
        stage = stage_map.get(raw_stage)
        if stage is None:
            continue

        team1 = f.get("team1", "TBD")
        team2 = f.get("team2", "TBD")

        # Find matching result in match_results.json by team names
        result = None
        for r in match_results.values():
            teams_r = {r["home"], r["away"]}
            teams_f = {team1, team2}
            if "TBD" in teams_f:
                known = {t for t in teams_f if t != "TBD"}
                if known and known <= teams_r:
                    result = r
                    break
            elif teams_f == teams_r:
                result = r
                break

        bracket[stage].append({
            "match_id":       f.get("match_id"),
            "date":           f.get("date", ""),
            "time":           f.get("time", ""),
            "team1":          team1,
            "team2":          team2,
            "score1":         result.get("home_score") if result else None,
            "score2":         result.get("away_score") if result else None,
            "winner":         result.get("winner") if result else None,
            "is_played":      result is not None,
            "both_teams_known": "TBD" not in (team1, team2),
            "team1_champion": probs.get(team1),
            "team2_champion": probs.get(team2),
        })

    return bracket
