from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
from collections import defaultdict

router = APIRouter()

STANDINGS_PATH = Path("data/pipeline/group_standings.json")
PIPELINE_JSON  = Path("data/pipeline/champion_probabilities.json")

def _get_standings():
    # Use real standings if available
    if STANDINGS_PATH.exists():
        with open(STANDINGS_PATH) as f:
            standings = json.load(f)
        result = []
        for group_letter, teams in sorted(standings.items()):
            sorted_teams = sorted(
                teams.values(),
                key=lambda t: (t["points"], t["gd"], t["gf"]),
                reverse=True,
            )
            result.append({"group": group_letter, "standings": sorted_teams})
        return result

    # Fall back to pipeline JSON (pre-tournament)
    if PIPELINE_JSON.exists():
        with open(PIPELINE_JSON) as f:
            data = json.load(f)
        groups = defaultdict(list)
        for team in data.get("teams", []):
            groups[team["group"]].append({
                "team":    team["team"],
                "played":  0, "won": 0, "drawn": 0, "lost": 0,
                "gf":      0, "ga":  0, "gd":    0, "points": 0,
            })
        return [
            {"group": g, "standings": teams}
            for g, teams in sorted(groups.items())
        ]

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