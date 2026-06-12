# backend/routers/bracket.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import importlib.util
import json

router = APIRouter()

ROOT = Path(__file__).parent.parent.parent
PROBS_PATH = ROOT / "data/pipeline/champion_probabilities.json"


def _load_wc_fixtures():
    spec = importlib.util.spec_from_file_location(
        "wc2026_fixtures", ROOT / "pipeline/wc2026_fixtures.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.FIXTURES


@router.get("/")
def get_bracket():
    try:
        from pipeline.knockout_tracker import get_bracket as resolve_bracket
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Bracket module unavailable: {e}")

    fixtures = _load_wc_fixtures()

    probs = {}
    if PROBS_PATH.exists():
        with open(PROBS_PATH) as f:
            data = json.load(f)
            probs = {t["team"]: t["champion"] for t in data["teams"]}

    try:
        resolved = resolve_bracket(fixtures)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not resolve bracket: {e}")

    knockout_stages = [
        "Round of 32", "Round of 16",
        "Quarter-final", "Semi-final",
        "Third-place play-off", "Final",
    ]

    bracket = {stage: [] for stage in knockout_stages}

    for f in resolved:
        result = f.get("result") or {}
        bracket.setdefault(f["stage"], []).append({
            "match_no":       f["match_no"],
            "date":           f["date"],
            "time":           f["time"],
            "team1":          f["team1"],
            "team2":          f["team2"],
            "score1":         result.get("home_score"),
            "score2":         result.get("away_score"),
            "winner":         result.get("winner"),
            "is_played":      f["is_played"],
            "both_teams_known": f["both_teams_known"],
            "team1_champion": probs.get(f["team1"]),
            "team2_champion": probs.get(f["team2"]),
        })

    return bracket