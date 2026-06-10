"""
backend/routers/match_probabilities.py
Serves per-match win/draw/loss probabilities using the LightGBM model.
Used by the Matches page to show upcoming fixture predictions.
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
from datetime import datetime, timezone
import json

from backend.state import app_state
from backend.database import get_db

router = APIRouter()

FIXTURES_PATH = Path("data/cache/fixtures.json")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_fixtures() -> list[dict]:
    if not FIXTURES_PATH.exists():
        return []
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("fixtures", [])


def _load_probabilities() -> dict:
    """Load champion probabilities from DB keyed by team name."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT team, group_letter, elo, round_of_32, round_of_16,
                       quarter_final, semi_final, final, champion
                FROM probabilities
            """)
            rows = cur.fetchall()
        return {
            r[0]: {
                "team":          r[0],
                "group":         r[1],
                "elo":           float(r[2] or 0),
                "round_of_32":   float(r[3] or 0),
                "round_of_16":   float(r[4] or 0),
                "quarter_final": float(r[5] or 0),
                "semi_final":    float(r[6] or 0),
                "final":         float(r[7] or 0),
                "champion":      float(r[8] or 0),
            }
            for r in rows
        }
    except Exception:
        return {}


def _predict_match(home_team: str, away_team: str) -> dict:
    """
    Use the loaded LightGBM model from app_state to predict match outcome.
    Returns p_home_win, p_draw, p_away_win as percentages.
    """
    if not app_state.model or not app_state.team_stats:
        return {"p_home_win": None, "p_draw": None, "p_away_win": None}

    hs  = app_state.team_stats.get(home_team)
    as_ = app_state.team_stats.get(away_team)

    if not hs or not as_:
        return {"p_home_win": None, "p_draw": None, "p_away_win": None}

    import pandas as pd
    from backend.config import TOURNAMENT_WEIGHT

    row = {
        "home_elo":           hs["elo"],
        "away_elo":           as_["elo"],
        "elo_diff":           hs["elo"] - as_["elo"],
        "home_elo_momentum":  hs["elo_momentum"],
        "away_elo_momentum":  as_["elo_momentum"],
        "home_avg_opp_elo5":  hs["avg_opp_elo5"],
        "away_avg_opp_elo5":  as_["avg_opp_elo5"],
        "home_advantage":     0,
        "tournament_weight":  TOURNAMENT_WEIGHT,
        "month":              6,
        "form_diff":          hs["form5"] - as_["form5"],
        "weighted_form_diff": hs["weighted_form5"] - as_["weighted_form5"],
        "goals_diff":         hs["goals_scored5"] - as_["goals_scored5"],
        "conceded_diff":      hs["goals_conceded5"] - as_["goals_conceded5"],
    }

    X      = pd.DataFrame([{f: row[f] for f in app_state.features}])
    probs  = app_state.model.predict_proba(X)[0]

    # LightGBM returns [away_win, draw, home_win] — index 0=away,1=draw,2=home
    p_home = round(float(probs[2]) * 100, 1)
    p_draw = round(float(probs[1]) * 100, 1)
    p_away = round(float(probs[0]) * 100, 1)

    return {"p_home_win": p_home, "p_draw": p_draw, "p_away_win": p_away}


def _build_match_response(fixture: dict, probs: dict, match_probs: dict) -> dict:
    home  = fixture["team1"]
    away  = fixture["team2"]
    known = home != "TBD" and away != "TBD"

    return {
        "match_id":       fixture["match_id"],
        "date":           fixture["date"],
        "time":           fixture["time"],
        "stage":          fixture["stage"],
        "group":          fixture.get("group"),
        "status":         fixture.get("status", "TIMED"),
        "team1":          home,
        "team2":          away,
        # Match outcome probabilities from model
        "p_home_win":     match_probs.get("p_home_win") if known else None,
        "p_draw":         match_probs.get("p_draw")     if known else None,
        "p_away_win":     match_probs.get("p_away_win") if known else None,
        # Tournament champion probabilities from simulation
        "home_champion":  probs.get(home, {}).get("champion") if known else None,
        "away_champion":  probs.get(away, {}).get("champion") if known else None,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/")
def get_all_match_probabilities():
    """All fixtures with match outcome + champion probabilities."""
    fixtures = _load_fixtures()
    if not fixtures:
        raise HTTPException(status_code=503, detail="Fixtures cache not available")

    probs = _load_probabilities()

    result = []
    for f in fixtures:
        home, away = f["team1"], f["team2"]
        mp = _predict_match(home, away) if home != "TBD" and away != "TBD" else {}
        result.append(_build_match_response(f, probs, mp))

    return result


@router.get("/upcoming")
def get_upcoming_matches(days: int = 3):
    """
    Fixtures in the next N days with predictions.
    Default: next 3 days.
    """
    fixtures = _load_fixtures()
    if not fixtures:
        raise HTTPException(status_code=503, detail="Fixtures cache not available")

    today    = datetime.now(timezone.utc).date()
    probs    = _load_probabilities()
    result   = []

    for f in fixtures:
        try:
            match_date = datetime.strptime(f["date"], "%Y-%m-%d").date()
        except ValueError:
            continue

        delta = (match_date - today).days
        if 0 <= delta <= days and f["status"] not in ("FINISHED",):
            home, away = f["team1"], f["team2"]
            mp = _predict_match(home, away) if home != "TBD" and away != "TBD" else {}
            result.append(_build_match_response(f, probs, mp))

    return result


@router.get("/today")
def get_today_matches():
    """Today's fixtures with live predictions."""
    return get_upcoming_matches(days=0)


@router.get("/stage/{stage_name}")
def get_matches_by_stage(stage_name: str):
    """
    All fixtures for a given stage.
    e.g. /api/match-probabilities/stage/Group%20Stage
    """
    fixtures = _load_fixtures()
    probs    = _load_probabilities()

    filtered = [f for f in fixtures if f["stage"].lower() == stage_name.lower()]
    if not filtered:
        raise HTTPException(status_code=404, detail=f"No fixtures found for stage: {stage_name}")

    result = []
    for f in filtered:
        home, away = f["team1"], f["team2"]
        mp = _predict_match(home, away) if home != "TBD" and away != "TBD" else {}
        result.append(_build_match_response(f, probs, mp))

    return result


@router.get("/{match_id}")
def get_match_probability(match_id: int):
    """Single fixture by match_id."""
    fixtures = _load_fixtures()
    fixture  = next((f for f in fixtures if f["match_id"] == match_id), None)

    if not fixture:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

    probs = _load_probabilities()
    home, away = fixture["team1"], fixture["team2"]
    mp = _predict_match(home, away) if home != "TBD" and away != "TBD" else {}

    return _build_match_response(fixture, probs, mp)