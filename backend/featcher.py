import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

RAPIDAPI_KEY = ""
WC_LEAGUE_ID = 1        # FIFA World Cup on API-Football
WC_SEASON    = 2026

async def fetch_and_update(state):
    """Fetch finished matches and record any new results."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api-football-v1.p.rapidapi.com/v3/fixtures",
            params={"league": WC_LEAGUE_ID, "season": WC_SEASON, "status": "FT"},
            headers={
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com",
            },
        )
        data = resp.json()

    already_recorded = {
        (r.home_team, r.away_team) for r in state.recorded_results
    }

    new_results = []
    for fixture in data.get("response", []):
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        hs   = fixture["goals"]["home"]
        as_  = fixture["goals"]["away"]

        if (home, away) not in already_recorded and hs is not None:
            from .models import MatchResult
            result = MatchResult(
                home_team=home, away_team=away,
                home_score=hs, away_score=as_,
                stage="Group Stage",
                played_at=datetime.utcnow(),
            )
            if state.is_valid_match(home, away):
                state.record_result(result)
                new_results.append(f"{home} {hs}-{as_} {away}")

    if new_results:
        print(f"New results fetched: {new_results}")
        from .simulator import run_simulation_background
        await run_simulation_background(state)
    else:
        print("No new results.")

def start_scheduler(state):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        fetch_and_update,
        "interval",
        minutes=5,
        args=[state],
        id="fetch_results",
    )
    scheduler.start()
    return scheduler