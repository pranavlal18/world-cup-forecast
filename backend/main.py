"""
backend/main.py
FastAPI application for WC 2026 Live Forecasting Platform.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from backend.state import app_state
from backend.models import MatchResult, SimulationStatus
from backend.simulator import run_simulation_background
from backend.routers.groups import router as groups_router
from backend.routers.probabilities import router as probabilities_router
from backend.routers.bracket import router as bracket_router
from backend.routers.matches import router as matches_router
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading LightGBM model...")
    await app_state.initialize()
    if not app_state.probabilities:
        print("No cache found, running simulation...")
        asyncio.create_task(run_simulation_background(app_state))
    else:
        print("Cache loaded, skipping simulation.")
    yield
app = FastAPI(
    title="WC 2026 Forecast API",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten to your Vercel URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(groups_router,        prefix="/api/groups",        tags=["Groups"])
app.include_router(probabilities_router, prefix="/api/probabilities", tags=["Probabilities"])
app.include_router(bracket_router,       prefix="/api/bracket",       tags=["Bracket"])
app.include_router(matches_router,       prefix="/api/matches",       tags=["Matches"])
@app.get("/")
def root():
    return {"status": "ok", "message": "WC 2026 Forecast API"}


@app.get("/api/status", response_model=SimulationStatus)
def get_status():
    return app_state.get_status()

@app.get("/api/progress")
def get_progress():
    total = 10_000
    return {
        "is_running": app_state.sim_running,
        "completed": app_state.sim_progress,
        "total": total,
        "percent": round(app_state.sim_progress / total * 100, 1)
    }
@app.post("/api/result")
async def post_result(result: MatchResult, background_tasks: BackgroundTasks):
    """
    Ingest a real match result, update standings, and trigger re-simulation.
    """
    if not app_state.is_valid_match(result.home_team, result.away_team):
        raise HTTPException(status_code=400, detail="Unknown team(s) in match result")

    app_state.record_result(result)
    background_tasks.add_task(run_simulation_background, app_state)

    return {"status": "accepted", "message": "Result recorded, simulation queued"}