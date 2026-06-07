"""backend/routers/groups.py"""
from fastapi import APIRouter
from backend.state import app_state
from backend.models import GroupResult
from backend.config import GROUPS
router = APIRouter()

@router.get("/", response_model=list[GroupResult])
def get_all_groups():
    result = []
    for gname, teams in GROUPS.items():
        standings_list = sorted(
            app_state.standings[gname].values(),
            key=lambda s: (s.points, s.gd, s.gf),
            reverse=True,
        )
        result.append(GroupResult(group=gname, standings=standings_list))
    return result

@router.get("/{group}", response_model=GroupResult)
def get_group(group: str):
    group = group.upper()
    if group not in GROUPS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Group {group} not found")
    standings_list = sorted(
        app_state.standings[group].values(),
        key=lambda s: (s.points, s.gd, s.gf),
        reverse=True,
    )
    return GroupResult(group=group, standings=standings_list)