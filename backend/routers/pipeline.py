"""
backend/routers/pipeline.py
Serves the champion_probabilities.json produced by the pipeline.
Add this router to main.py for the React UI to consume.
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
import json

router = APIRouter()

JSON_PATH = Path("data/pipeline/champion_probabilities.json")



@router.get("/meta")
def get_pipeline_meta():
    """Returns just the metadata (generated_at, simulations) without team data."""
    if not JSON_PATH.exists():
        raise HTTPException(status_code=503, detail="No pipeline output found")
    with open(JSON_PATH) as f:
        data = json.load(f)
    return {
        "generated_at": data.get("generated_at"),
        "simulations":  data.get("simulations"),
        "team_count":   len(data.get("teams", [])),
    }

@router.get("/groups")
def get_pipeline_groups():
    """Returns group standings derived from pipeline JSON."""
    if not JSON_PATH.exists():
        raise HTTPException(status_code=503, detail="Pipeline has not run yet")
    with open(JSON_PATH) as f:
        data = json.load(f)
    # Group teams by group letter
    from collections import defaultdict
    groups = defaultdict(list)
    for team in data.get("teams", []):
        groups[team["group"]].append(team)
    return [{"group": g, "teams": teams} for g, teams in sorted(groups.items())]
@router.get("/")
def get_pipeline_probabilities():
    from backend.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT team, group_letter, elo, round_of_32, round_of_16,
                   quarter_final, semi_final, final, champion, generated_at
            FROM probabilities
            ORDER BY champion DESC
        """)
        rows = cur.fetchall()
    if not rows:
        raise HTTPException(status_code=503, detail="No probabilities yet")
    return {
        "teams": [
            {
                "team": r[0], "group": r[1], "elo": r[2],
                "round_of_32": r[3], "round_of_16": r[4],
                "quarter_final": r[5], "semi_final": r[6],
                "final": r[7], "champion": r[8],
            }
            for r in rows
        ],
        "generated_at": rows[0][9].isoformat() if rows[0][9] else None,
    }