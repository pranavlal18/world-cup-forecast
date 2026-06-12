"""
pipeline/update_elo.py
════════════════════════════════════════════════════════════════════════
Reads new_results.csv, updates Elo ratings for each team,
writes current_ratings.csv.

Elo update formula (standard FIFA-style):
  K  = 60 for World Cup matches
  We = 1 / (1 + 10^((Rb - Ra) / 400))
  Ra_new = Ra + K * (W - We)
════════════════════════════════════════════════════════════════════════
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
NEW_RESULTS_PATH  = ROOT / "data/pipeline/new_results.csv"
RATINGS_PATH      = ROOT / "data/pipeline/current_ratings.csv"
RATINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

K_FACTOR = 60   # FIFA World Cup weight

# ── Initial Elo ratings (updated from latest eloratings.net data) ────────────
INITIAL_ELOS = {
    "Mexico":                 1875,
    "South Africa":           1600,
    "South Korea":            1758,
    "Czechia":                1740,
    "Canada":                 1788,
    "Bosnia and Herzegovina": 1591,
    "Qatar":                  1500,
    "Switzerland":            1894,
    "Brazil":                 1988,
    "Morocco":                1820,
    "Haiti":                  1548,
    "Scotland":               1770,
    "United States":          1733,
    "Paraguay":               1833,
    "Australia":              1774,
    "Turkey":                 1906,
    "Germany":                1925,
    "Curaçao":                1433,
    "Ivory Coast":            1695,
    "Ecuador":                1935,
    "Netherlands":            1944,
    "Japan":                  1906,
    "Sweden":                 1712,
    "Tunisia":                1628,
    "Belgium":                1888,
    "Egypt":                  1699,
    "Iran":                   1772,
    "New Zealand":            1563,
    "Spain":                  2155,
    "Cape Verde":             1576,
    "Saudi Arabia":           1569,
    "Uruguay":                1892,
    "France":                 2062,
    "Senegal":                1867,
    "Iraq":                   1618,
    "Norway":                 1917,
    "Argentina":              2113,
    "Algeria":                1760,
    "Austria":                1830,
    "Jordan":                 1685,
    "Portugal":               1984,
    "DR Congo":               1661,
    "Uzbekistan":             1718,
    "Colombia":               1977,
    "England":                2020,
    "Croatia":                1908,
    "Ghana":                  1510,
    "Panama":                 1734,
}


def load_ratings() -> dict:
    """Load current ratings from CSV, or use initial values."""
    if RATINGS_PATH.exists():
        df = pd.read_csv(RATINGS_PATH)
        return dict(zip(df["team"], df["elo"]))
    return INITIAL_ELOS.copy()


def save_ratings(ratings: dict):
    df = pd.DataFrame([
        {"team": t, "elo": round(e, 1), "updated_at": datetime.utcnow().isoformat()}
        for t, e in sorted(ratings.items(), key=lambda x: -x[1])
    ])
    df.to_csv(RATINGS_PATH, index=False)
    print(f"  Saved ratings → {RATINGS_PATH}")


def expected_score(ra: float, rb: float) -> float:
    return 1 / (1 + 10 ** ((rb - ra) / 400))


def update_elo(ra: float, rb: float, score_a: float) -> tuple[float, float]:
    """
    score_a: 1.0 = win, 0.5 = draw, 0.0 = loss
    Returns (new_ra, new_rb)
    """
    we_a = expected_score(ra, rb)
    we_b = 1 - we_a
    score_b = 1 - score_a

    new_ra = ra + K_FACTOR * (score_a - we_a)
    new_rb = rb + K_FACTOR * (score_b - we_b)
    return new_ra, new_rb


def run():
    if not NEW_RESULTS_PATH.exists() or NEW_RESULTS_PATH.stat().st_size == 0:
        print("  No new results to process.")
        return load_ratings()

    results = pd.read_csv(NEW_RESULTS_PATH)
    if results.empty:
        print("  new_results.csv is empty.")
        return load_ratings()

    ratings = load_ratings()
    updated_teams = {}

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Updating Elo ratings...")
    for _, row in results.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        hs   = int(row["home_score"])
        as_  = int(row["away_score"])

        if home not in ratings or away not in ratings:
            print(f"  ⚠ Unknown team: {home} or {away}, skipping")
            continue

        ra = ratings[home]
        rb = ratings[away]

        if hs > as_:   score = 1.0
        elif hs < as_: score = 0.0
        else:          score = 0.5

        new_ra, new_rb = update_elo(ra, rb, score)

        print(f"  {home} {hs}-{as_} {away}")
        print(f"    {home}: {ra:.0f} → {new_ra:.0f} ({new_ra-ra:+.0f})")
        print(f"    {away}: {rb:.0f} → {new_rb:.0f} ({new_rb-rb:+.0f})")

        ratings[home] = new_ra
        ratings[away] = new_rb
        updated_teams[home] = new_ra
        updated_teams[away] = new_rb

    save_ratings(ratings)

    # Clear new_results.csv so these matches can never be re-applied
    NEW_RESULTS_PATH.unlink()
    print(f"  Cleared {NEW_RESULTS_PATH}")

    return ratings

if __name__ == "__main__":
    run()