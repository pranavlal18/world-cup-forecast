"""
backend/state.py  —  Central in-memory state for the application.
Holds the loaded model, team stats, match results, standings, and latest sim output.
"""

import pickle
import asyncio
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional
from .models import MatchResult, GroupStanding, SimulationStatus
from .config import (
    MODEL_PATH, FEATURES_PATH, PROBS_PATH,
    GROUPS, NAME_MAP, PLAYOFF_MAP, ACTUAL_ELO_OVERRIDES,
    WORLD_CUP_AVG_ELO,
)
import json
from pathlib import Path

CACHE_FILE = Path("data/processed/sim_cache.json")


class AppState:
    def __init__(self):
        self.model = None
        self.features: list = []
        self.team_stats: dict = {}
        self.match_probs: dict = {}
        self.all_teams: list = []
        

        # Live results recorded via POST /result
        self.recorded_results: list[MatchResult] = []

        # Current group standings (updated after each result)
        self.standings: dict[str, dict[str, GroupStanding]] = {}

        
        
        
        

    # ── Initialisation ────────────────────────────────────────────────────────

    async def initialize(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_sync)

    def _load_sync(self):
        # Load model
        with open(MODEL_PATH, "rb") as f:
            saved = pickle.load(f)
        self.model = saved["model"]
        self.features = saved["features"]
        self.model.n_jobs = -1

        # Load features CSV
        df = pd.read_csv(FEATURES_PATH)
        df["date"] = pd.to_datetime(df["date"])

        # Collect all WC teams
        self.all_teams = [t for g in GROUPS.values() for t in g]

        # Get team stats
        for team in self.all_teams:
            self.team_stats[team] = self._get_team_stats(df, team)

        # Load baseline Elo from probs CSV
        baseline_df = pd.read_csv(PROBS_PATH)
        baseline_elo = {}
        for _, row in baseline_df.iterrows():
            home = PLAYOFF_MAP.get(row["home_team"], row["home_team"])
            away = PLAYOFF_MAP.get(row["away_team"], row["away_team"])
            baseline_elo[home] = row["home_elo"]
            baseline_elo[away] = row["away_elo"]

        
        # Override Elos
        for team in self.all_teams:
            if team in baseline_elo:
                self.team_stats[team]["elo"] = baseline_elo[team]
        for team, elo in ACTUAL_ELO_OVERRIDES.items():
            self.team_stats[team]["elo"] = elo

        # Adjust stats for WC opponent quality
        for team in self.all_teams:
            self.team_stats[team] = self._adjust_stats_for_wc(self.team_stats[team])

        # Init blank standings
        for gname, teams in GROUPS.items():
            self.standings[gname] = {
                t: GroupStanding(
                    team=t, played=0, won=0, drawn=0, lost=0,
                    gf=0, ga=0, gd=0, points=0
                )
                for t in teams
            }
        self.load_cache()


    # ── Team stat helpers ─────────────────────────────────────────────────────

    def _get_team_stats(self, df: pd.DataFrame, team: str) -> dict:
        csv_name = NAME_MAP.get(team, team)
        home_rows = df[df["home_team"] == csv_name].copy()
        away_rows = df[df["away_team"] == csv_name].copy()
        home_rows["_side"] = "home"
        away_rows["_side"] = "away"
        all_rows = pd.concat([home_rows, away_rows]).sort_values("date")

        stats = {
            "elo": 1500.0, "form5": 0.35, "weighted_form5": 0.35,
            "goals_scored5": 0.9, "goals_conceded5": 1.4,
            "avg_opp_elo5": 1500.0, "elo_momentum": 0.0,
        }
        if all_rows.empty:
            return stats

        last = all_rows.iloc[-1]
        p = last["_side"]
        stats["elo"]             = last[f"{p}_elo"]
        stats["form5"]           = last[f"{p}_form5"]
        stats["weighted_form5"]  = last[f"{p}_weighted_form5"]
        stats["goals_scored5"]   = last[f"{p}_goals_scored5"]
        stats["goals_conceded5"] = last[f"{p}_goals_conceded5"]
        stats["avg_opp_elo5"]    = last[f"{p}_avg_opp_elo5"]
        stats["elo_momentum"]    = last[f"{p}_elo_momentum"]
        return stats

    def _adjust_stats_for_wc(self, stats: dict) -> dict:
        opp_elo = stats["avg_opp_elo5"]
        if opp_elo >= WORLD_CUP_AVG_ELO:
            stats["elo_momentum"] = max(-3.0, min(3.0, stats["elo_momentum"]))
            return stats
        ratio = opp_elo / WORLD_CUP_AVG_ELO
        adjusted = stats.copy()
        adjusted["goals_scored5"]   = stats["goals_scored5"]   * ratio
        adjusted["goals_conceded5"] = stats["goals_conceded5"] / ratio
        adjusted["form5"]           = stats["form5"]           * ratio
        adjusted["weighted_form5"]  = stats["weighted_form5"]  * ratio
        adjusted["elo_momentum"]    = max(-3.0, min(3.0, stats["elo_momentum"]))
        return adjusted

    # ── Result recording ──────────────────────────────────────────────────────

    def is_valid_match(self, home: str, away: str) -> bool:
        return home in self.all_teams and away in self.all_teams

    def record_result(self, result: MatchResult):
        self.recorded_results.append(result)
        if result.stage == "Group Stage":
            self._update_group_standings(result)

    def _update_group_standings(self, result: MatchResult):
        home, away = result.home_team, result.away_team
        hs = result.home_score
        as_ = result.away_score

        group = next(
            (g for g, teams in GROUPS.items() if home in teams), None
        )
        if not group:
            return

        sh = self.standings[group][home]
        sa = self.standings[group][away]

        sh.played += 1; sa.played += 1
        sh.gf += hs;    sh.ga += as_;   sh.gd = sh.gf - sh.ga
        sa.gf += as_;   sa.ga += hs;    sa.gd = sa.gf - sa.ga

        if hs > as_:
            sh.won += 1;  sh.points += 3
            sa.lost += 1
        elif hs < as_:
            sa.won += 1;  sa.points += 3
            sh.lost += 1
        else:
            sh.drawn += 1; sh.points += 1
            sa.drawn += 1; sa.points += 1

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> SimulationStatus:
        return SimulationStatus(
            last_run=None,
            simulations=0,
            is_running=False,
            results_available=True,  # pipeline handles this
        )


    def save_cache(self):
        """Save simulation results to disk."""
        if not self.probabilities:
            return
        cache = {
            "probabilities": self.probabilities,
            "last_run": self.last_sim_run.isoformat() if self.last_sim_run else None,
            "n_simulations_run": self.n_simulations_run,
        }
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)

    def load_cache(self) -> bool:
        """Load cached results on startup. Returns True if cache found."""
        if not CACHE_FILE.exists():
            return False
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        self.probabilities = cache["probabilities"]
        self.n_simulations_run = cache["n_simulations_run"]
        from datetime import datetime
        self.last_sim_run = datetime.fromisoformat(cache["last_run"]) if cache["last_run"] else None
        print(f"  Loaded cached simulation from {self.last_sim_run}")
        return True


app_state = AppState()