"""backend/routers/matches.py"""
from fastapi import APIRouter
from backend.state import app_state
from backend.models import MatchResult
router = APIRouter()

@router.get("/")
def get_all_results():
    return [r.model_dump() for r in app_state.recorded_results]