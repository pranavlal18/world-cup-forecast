"""
backend/models.py  —  Pydantic request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class MatchResult(BaseModel):
    home_team: str
    away_team: str
    home_score: int = Field(..., ge=0)
    away_score: int = Field(..., ge=0)
    stage: str = Field(default="Group Stage")   # "Group Stage" | "Round of 32" | etc.
    played_at: Optional[datetime] = None


class TeamProbability(BaseModel):
    team: str
    group: str
    elo: float
    round_of_32: float
    round_of_16: float
    quarter_final: float
    semi_final: float
    final: float
    champion: float


class GroupStanding(BaseModel):
    team: str
    played: int
    won: int
    drawn: int
    lost: int
    gf: int
    ga: int
    gd: int
    points: int


class GroupResult(BaseModel):
    group: str
    standings: list[GroupStanding]


class SimulationStatus(BaseModel):
    last_run: Optional[datetime]
    simulations: int
    is_running: bool
    results_available: bool


class KnockoutMatch(BaseModel):
    match_id: str
    round: str
    home_team: Optional[str]
    away_team: Optional[str]
    home_score: Optional[int]
    away_score: Optional[int]
    winner: Optional[str]
    home_win_prob: Optional[float]
    away_win_prob: Optional[float]