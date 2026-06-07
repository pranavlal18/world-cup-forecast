"""backend/routers/bracket.py"""
from fastapi import APIRouter
from backend.state import app_state
from backend.config import GROUPS
router = APIRouter()

@router.get("/")
def get_bracket():
    """
    Returns current group leaders + runners-up for bracket display.
    Once results are recorded these will reflect actual standings.
    """
    bracket = {}
    for gname, teams in GROUPS.items():
        standings = sorted(
            app_state.standings[gname].values(),
            key=lambda s: (s.points, s.gd, s.gf),
            reverse=True,
        )
        bracket[gname] = {
            "winner":     standings[0].team if standings[0].played > 0 else None,
            "runner_up":  standings[1].team if standings[1].played > 0 else None,
            "standings":  [s.team for s in standings],
        }
    return bracket