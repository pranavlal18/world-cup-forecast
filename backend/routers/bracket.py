# backend/routers/bracket.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json

router = APIRouter()

ROOT = Path(__file__).parent.parent.parent
PROBS_PATH = ROOT / "data/pipeline/champion_probabilities.json"
FIXTURES_CACHE = ROOT / "data/cache/fixtures.json"


def _load_api_fixtures() -> list[dict]:
    if not FIXTURES_CACHE.exists():
        return []
    with open(FIXTURES_CACHE) as f:
        data = json.load(f)
    return data.get("fixtures", [])


def _load_match_results() -> dict:
    from pipeline.knockout_tracker import load_results_from_db, load_results
    db_results = load_results_from_db()
    if db_results:
        return db_results
    return load_results()


def _resolve_all_fixtures(fixtures):
    try:
        from pipeline.knockout_tracker import resolve_fixture, load_results_from_db, load_results
        from pipeline.group_tracker import load_standings
        from pipeline.wc2026_fixtures import FIXTURES as WC_FIXTURES
    except Exception:
        return {}

    from datetime import datetime, timedelta

    db_results = load_results_from_db()
    results = db_results if db_results else load_results()
    standings = load_standings()

    VENUE_TZ = {
        "NRG Stadium": -5,
        "Lincoln Financial Field": -4,
        "MetLife Stadium": -4,
        "Estadio Azteca": -6,
        "AT&T Stadium": -5,
        "SoFi Stadium": -7,
        "BC Place": -7,
        "Hard Rock Stadium": -4,
        "Mercedes-Benz Stadium": -4,
        "Gillette Stadium": -4,
        "Arrowhead Stadium": -5,
        "Levi's Stadium": -7,
        "Estadio BBVA": -6,
        "Lumen Field": -7,
    }

    def _local_to_utc(date_str, time_str, venue):
        tz_offset = VENUE_TZ.get(venue, 0)
        local_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return local_dt - timedelta(hours=tz_offset)

    def _is_tbd(name):
        return name == "TBD" or name.startswith("Winner") or name.startswith("Loser") or name.startswith("Group ")

    wc_lookup = {}
    for wcf in WC_FIXTURES:
        if wcf["stage"] == "Group Stage":
            continue
        resolved = resolve_fixture(wcf, results, standings)
        t1, t2 = resolved["team1"], resolved["team2"]
        t1_real = not _is_tbd(t1)
        t2_real = not _is_tbd(t2)
        utc_dt = _local_to_utc(wcf["date"], wcf["time"], wcf["venue"])
        wc_lookup[wcf["match_no"]] = {
            "team1": t1, "team2": t2,
            "t1_real": t1_real, "t2_real": t2_real,
            "stage": wcf["stage"].lower(),
            "utc_dt": utc_dt,
        }

    mapping = {}
    for f in fixtures:
        if f["stage"] == "Group Stage":
            continue

        api_stage = f["stage"].lower()
        try:
            api_dt = datetime.strptime(f"{f['date']} {f['time']}", "%Y-%m-%d %H:%M")
        except (ValueError, KeyError):
            continue

        best_match = None
        best_diff = timedelta(hours=6)

        for mno, wc in wc_lookup.items():
            if wc["stage"] != api_stage:
                continue
            diff = abs(api_dt - wc["utc_dt"])
            if diff < best_diff:
                best_diff = diff
                best_match = mno

        if best_match is not None:
            wc = wc_lookup[best_match]
            t1 = wc["team1"] if wc["t1_real"] else "TBD"
            t2 = wc["team2"] if wc["t2_real"] else "TBD"
            mapping[f.get("match_id")] = (t1, t2)

    return mapping


@router.get("/")
def get_bracket():
    probs = {}
    if PROBS_PATH.exists():
        with open(PROBS_PATH) as f:
            data = json.load(f)
            probs = {t["team"]: t["champion"] for t in data["teams"]}

    api_fixtures = _load_api_fixtures()
    if not api_fixtures:
        raise HTTPException(status_code=503, detail="Fixtures not available")

    stage_map = {
        "Round of 32":          "Round of 32",
        "Round of 16":          "Round of 16",
        "Quarter-Final":        "Quarter-final",
        "Quarter-final":        "Quarter-final",
        "Semi-Final":           "Semi-final",
        "Semi-final":           "Semi-final",
        "Third-Place Play-off": "Third-place play-off",
        "Third-place play-off": "Third-place play-off",
        "Final":                "Final",
    }

    ko_stages = [
        "Round of 32", "Round of 16",
        "Quarter-final", "Semi-final",
        "Third-place play-off", "Final",
    ]

    bracket = {stage: [] for stage in ko_stages}
    match_results = _load_match_results()
    resolution = _resolve_all_fixtures(api_fixtures)

    def _is_tbd(name):
        return name == "TBD" or name.startswith("Winner Match") or name.startswith("Loser Match")

    for f in api_fixtures:
        raw_stage = f["stage"]
        stage = stage_map.get(raw_stage)
        if stage is None:
            continue

        mid = f.get("match_id")
        if mid in resolution:
            team1, team2 = resolution[mid]
        else:
            team1 = f.get("team1", "TBD")
            team2 = f.get("team2", "TBD")

        result = None
        if not _is_tbd(team1) and not _is_tbd(team2):
            for r in match_results.values():
                if r["stage"] != raw_stage:
                    continue
                if r["home"] == team1 and r["away"] == team2:
                    result = r
                    break
                if r["home"] == team2 and r["away"] == team1:
                    result = r
                    break

        score1, score2 = None, None
        if result:
            if result["home"] == team1:
                score1 = result.get("home_score")
                score2 = result.get("away_score")
            else:
                score1 = result.get("away_score")
                score2 = result.get("home_score")

        bracket[stage].append({
            "match_id":       mid,
            "date":           f.get("date", ""),
            "time":           f.get("time", ""),
            "team1":          team1,
            "team2":          team2,
            "score1":         score1,
            "score2":         score2,
            "winner":         result.get("winner") if result else None,
            "is_played":      result is not None,
            "both_teams_known": not _is_tbd(team1) and not _is_tbd(team2),
            "team1_champion": probs.get(team1),
            "team2_champion": probs.get(team2),
        })

    return bracket
