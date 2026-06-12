from fastapi import APIRouter, HTTPException
from collections import defaultdict

router = APIRouter()

def _get_standings_from_db():
    from backend.database import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT team, group_letter, played, won, drawn, lost,
                   gf, ga, gd, points
            FROM group_standings
            ORDER BY group_letter, points DESC, gd DESC, gf DESC
        """)
        rows = cur.fetchall()
    if not rows:
        return None
    groups = defaultdict(list)
    for row in rows:
        team, g, played, won, drawn, lost, gf, ga, gd, points = row
        groups[g].append({
            "team": team, "played": played, "won": won,
            "drawn": drawn, "lost": lost, "gf": gf,
            "ga": ga, "gd": gd, "points": points,
        })
    return [
        {"group": g, "standings": teams}
        for g, teams in sorted(groups.items())
    ]

def _get_standings_from_json():
    from pathlib import Path
    import json
    PIPELINE_JSON = Path("data/pipeline/champion_probabilities.json")
    if not PIPELINE_JSON.exists():
        return None
    with open(PIPELINE_JSON) as f:
        data = json.load(f)
    groups = defaultdict(list)
    for team in data.get("teams", []):
        groups[team["group"]].append({
            "team": team["team"],
            "played": 0, "won": 0, "drawn": 0, "lost": 0,
            "gf": 0, "ga": 0, "gd": 0, "points": 0,
        })
    return [
        {"group": g, "standings": teams}
        for g, teams in sorted(groups.items())
    ]

def _get_standings():
    try:
        db = _get_standings_from_db()
        if db:
            return db
    except Exception as e:
        print(f"⚠ DB standings failed: {e} — falling back to JSON")
    result = _get_standings_from_json()
    if result:
        return result
    raise HTTPException(status_code=503, detail="Standings not available yet")

@router.get("/")
def get_all_groups():
    return _get_standings()

@router.get("/{group}")
def get_group(group: str):
    all_groups = _get_standings()
    group = group.upper()
    match = next((g for g in all_groups if g["group"] == group), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Group {group} not found")
    return match