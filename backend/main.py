"""
backend/main.py
FastAPI application for WC 2026 Live Forecasting Platform.
"""

import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.database import init_db
from backend.state import app_state
from backend.models import MatchResult, SimulationStatus
from backend.simulator import run_simulation_background
from backend.routers.groups import router as groups_router
from backend.routers.probabilities import router as probabilities_router
from backend.routers.bracket import router as bracket_router
from backend.routers.matches import router as matches_router
from backend.routers.pipeline import router as pipeline_router
from backend.save_group_standing import initialize_group_standings
from backend.routers.match_probabilities import router as match_probabilities_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading model...")
    await app_state.initialize()
    try:
        init_db()
        initialize_group_standings()
    except Exception as e:
        print(f"⚠ DB init failed: {e} — app will still start")
    yield
    print("Shutting down...")


ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app = FastAPI(
    title="WC 2026 Forecast API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(groups_router,               prefix="/api/groups",              tags=["Groups"])
app.include_router(probabilities_router,        prefix="/api/probabilities",       tags=["Probabilities"])
app.include_router(bracket_router,              prefix="/api/bracket",             tags=["Bracket"])
app.include_router(matches_router,              prefix="/api/matches",             tags=["Matches"])
app.include_router(pipeline_router,             prefix="/api/pipeline",            tags=["Pipeline"])
app.include_router(match_probabilities_router,  prefix="/api/match-probabilities", tags=["Match Probabilities"])


@app.get("/")
def root():
    return {"status": "ok", "message": "WC 2026 Forecast API"}


@app.get("/api/status", response_model=SimulationStatus)
def get_status():
    return app_state.get_status()


@app.get("/api/progress")
def get_progress():
    from pipeline.run_pipeline import N_SIMULATIONS
    return {
        "is_running": app_state.sim_running,
        "completed":  app_state.sim_progress,
        "total":      N_SIMULATIONS,
        "percent":    round(app_state.sim_progress / N_SIMULATIONS * 100, 1),
    }


@app.post("/api/result")
async def post_result(result: MatchResult, background_tasks: BackgroundTasks):
    if not app_state.is_valid_match(result.home_team, result.away_team):
        raise HTTPException(status_code=400, detail="Unknown team(s) in match result")
    app_state.record_result(result)
    background_tasks.add_task(run_simulation_background, app_state)
    return {"status": "accepted", "message": "Result recorded, simulation queued"}