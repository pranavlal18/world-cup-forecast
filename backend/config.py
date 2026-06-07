"""
backend/config.py  —  All constants, paths, and tournament data.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.parent
MODEL_PATH    = BASE_DIR / "data" / "processed" / "lgbm_model_v2.pkl"
FEATURES_PATH = BASE_DIR / "data" / "processed" / "features_with_form.csv"
PROBS_PATH    = BASE_DIR / "data" / "raw" / "future_match_probabilities_baseline.csv"

# ── Tournament ────────────────────────────────────────────────────────────────
N_SIMULATIONS    = 10_000
TOURNAMENT_WEIGHT = 5
WORLD_CUP_AVG_ELO = 1750

GROUPS = {
    "A": ["Mexico",        "South Africa",          "South Korea",  "Czechia"],
    "B": ["Canada",        "Bosnia and Herzegovina", "Qatar",        "Switzerland"],
    "C": ["Brazil",        "Morocco",               "Haiti",        "Scotland"],
    "D": ["United States", "Paraguay",              "Australia",    "Turkey"],
    "E": ["Germany",       "Curaçao",               "Ivory Coast",  "Ecuador"],
    "F": ["Netherlands",   "Japan",                 "Sweden",       "Tunisia"],
    "G": ["Belgium",       "Egypt",                 "Iran",         "New Zealand"],
    "H": ["Spain",         "Cape Verde",            "Saudi Arabia", "Uruguay"],
    "I": ["France",        "Senegal",               "Iraq",         "Norway"],
    "J": ["Argentina",     "Algeria",               "Austria",      "Jordan"],
    "K": ["Portugal",      "DR Congo",              "Uzbekistan",   "Colombia"],
    "L": ["England",       "Croatia",               "Ghana",        "Panama"],
}

NAME_MAP = {
    "Czechia":               "Czech Republic",
    "Turkey":                "Turkey",
    "Curaçao":               "Curaçao",
    "Ivory Coast":           "Ivory Coast",
    "Cape Verde":            "Cape Verde",
    "DR Congo":              "DR Congo",
    "South Korea":           "South Korea",
    "New Zealand":           "New Zealand",
    "United States":         "United States",
    "Bosnia and Herzegovina":"Bosnia and Herzegovina",
}

PLAYOFF_MAP = {
    "UEFA_Playoff_A":      "Bosnia and Herzegovina",
    "UEFA_Playoff_B":      "Sweden",
    "UEFA_Playoff_C":      "Turkey",
    "UEFA_Playoff_D":      "Czechia",
    "Interconf_Playoff_1": "DR Congo",
    "Interconf_Playoff_2": "Iraq",
    "Cape_Verde":          "Cape Verde",
    "Côte d'Ivoire":       "Ivory Coast",
}

ACTUAL_ELO_OVERRIDES = {
    "Czechia":                1740,
    "Bosnia and Herzegovina": 1591,
    "Turkey":                 1906,
    "Sweden":                 1712,
    "Iraq":                   1618,
    "DR Congo":               1661,
    "Panama":                 1734,
}

ROUND_ORDER = [
    "Group Stage", "Round of 32", "Round of 16",
    "Quarter-Final", "Semi-Final", "Final", "Champion",
]

# Which group pairs face each other in R32
# (group_winner vs other_group_runner_up)
R32_PAIRINGS = [
    ("A", "B"), ("C", "D"), ("E", "F"),
    ("G", "H"), ("I", "J"), ("K", "L"),
]