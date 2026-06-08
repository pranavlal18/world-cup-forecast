"""
pipeline/02_update_elo.py
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
NEW_RESULTS_PATH  = Path("data/pipeline/new_results.csv")
RATINGS_PATH      = Path("data/pipeline/current_ratings.csv")
RATINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

K_FACTOR = 60   # FIFA World Cup weight

# ── Initial Elo ratings (from your simulation) ────────────────────────────────
INITIAL_ELOS = {
    "Mexico":                 1890,
    "South Africa":           1600,
    "South Korea":            1755,
    "Czechia":                1740,
    "Canada":                 1750,
    "Bosnia and Herzegovina": 1591,
    "Qatar":                  1500,
    "Switzerland":            1850,
    "Brazil":                 2100,
    "Morocco":                1820,
    "Haiti":                  1400,
    "Scotland":               1705,
    "United States":          1880,
    "Paraguay":               1680,
    "Australia":              1720,
    "Turkey":                 1906,
    "Germany":                2040,
    "Curaçao":                1550,
    "Ivory Coast":            1676,
    "Ecuador":                1780,
    "Netherlands":            1970,
    "Japan":                  1860,
    "Sweden":                 1712,
    "Tunisia":                1670,
    "Belgium":                1885,
    "Egypt":                  1700,
    "Iran":                   1650,
    "New Zealand":            1580,
    "Spain":                  2000,
    "Cape Verde":             1520,
    "Saudi Arabia":           1700,
    "Uruguay":                1870,
    "France":                 2045,
    "Senegal":                1830,
    "Iraq":                   1618,
    "Norway":                 1715,
    "Argentina":              2060,
    "Algeria":                1655,
    "Austria":                1800,
    "Jordan":                 1480,
    "Portugal":               1975,
    "DR Congo":               1661,
    "Uzbekistan":             1505,
    "Colombia":               1790,
    "England":                2005,
    "Croatia":                1855,
    "Ghana":                  1600,
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
        return {}

    results = pd.read_csv(NEW_RESULTS_PATH)
    if results.empty:
        print("  new_results.csv is empty.")
        return {}

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

        # Determine outcome
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
    return ratings


if __name__ == "__main__":
    run()