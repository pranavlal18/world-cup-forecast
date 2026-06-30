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

    db_results = load_results_from_db()
    results = db_results if db_results else load_results()
    standings = load_standings()

    wc_resolved = {}
    for wcf in WC_FIXTURES:
        if wcf["stage"] == "Group Stage":
            continue
        resolved = resolve_fixture(wcf, results, standings)
        t1, t2 = resolved["team1"], resolved["team2"]
        t1_ok = t1 != "TBD" and not t1.startswith("Winner") and not t1.startswith("Loser") and not t1.startswith("Group ")
        t2_ok = t2 != "TBD" and not t2.startswith("Winner") and not t2.startswith("Loser") and not t2.startswith("Group ")
        if t1_ok and t2_ok:
            wc_resolved[wcf["stage"].lower()] = wc_resolved.get(wcf["stage"].lower(), [])
            wc_resolved[wcf["stage"].lower()].append({"team1": t1, "team2": t2})

    api_by_stage = {}
    for f in fixtures:
        if f["stage"] == "Group Stage":
            continue
        stage_key = f["stage"].lower()
        api_by_stage.setdefault(stage_key, []).append(f)

    mapping = {}
    for stage_key, api_list in api_by_stage.items():
        wc_list = wc_resolved.get(stage_key, [])
        for i, af in enumerate(api_list):
            if i < len(wc_list):
                af1 = af.get("team1", "TBD")
                af2 = af.get("team2", "TBD")
                wf1 = wc_list[i]["team1"]
                wf2 = wc_list[i]["team2"]

                def _is_tbd(name):
                    return name == "TBD" or name.startswith("Winner") or name.startswith("Loser") or name.startswith("Group ")

                new_t1 = wf1 if _is_tbd(af1) else af1
                new_t2 = wf2 if _is_tbd(af2) else af2
                mapping[af.get("match_id")] = (new_t1, new_t2)

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
