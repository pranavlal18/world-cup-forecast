"""backend/routers/probabilities.py"""
from fastapi import APIRouter, HTTPException
from backend.state import app_state
from backend.models import TeamProbability
from backend.config import GROUPS

router = APIRouter()

def _team_group(team: str) -> str:
    return next((g for g, teams in GROUPS.items() if team in teams), "?")

@router.get("/", response_model=list[TeamProbability])
def get_all_probabilities():
    if not app_state.probabilities:
        raise HTTPException(status_code=503, detail="Simulation not yet complete")
    result = []
    for team, rounds in app_state.probabilities.items():
        result.append(TeamProbability(
            team=team,
            group=_team_group(team),
            elo=app_state.team_stats[team]["elo"],
            round_of_32=rounds.get("Round of 32", 0),
            round_of_16=rounds.get("Round of 16", 0),
            quarter_final=rounds.get("Quarter-Final", 0),
            semi_final=rounds.get("Semi-Final", 0),
            final=rounds.get("Final", 0),
            champion=rounds.get("Champion", 0),
        ))
    return sorted(result, key=lambda x: x.champion, reverse=True)

@router.get("/team/{team_name}", response_model=TeamProbability)
def get_team_probability(team_name: str):
    if not app_state.probabilities:
        raise HTTPException(status_code=503, detail="Simulation not yet complete")
    if team_name not in app_state.probabilities:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")
    rounds = app_state.probabilities[team_name]
    return TeamProbability(
        team=team_name,
        group=_team_group(team_name),
        elo=app_state.team_stats[team_name]["elo"],
        round_of_32=rounds.get("Round of 32", 0),
        round_of_16=rounds.get("Round of 16", 0),
        quarter_final=rounds.get("Quarter-Final", 0),
        semi_final=rounds.get("Semi-Final", 0),
        final=rounds.get("Final", 0),
        champion=rounds.get("Champion", 0),
    )