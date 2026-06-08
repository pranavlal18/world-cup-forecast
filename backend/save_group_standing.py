from backend.database import get_db
from backend.config import GROUPS

def initialize_group_standings():
    with get_db() as conn:
        cur = conn.cursor()

        for group_letter, teams in GROUPS.items():
            for team in teams:

                cur.execute("""
                    INSERT INTO group_standings (
                        team,
                        group_letter,
                        played,
                        won,
                        drawn,
                        lost,
                        gf,
                        ga,
                        gd,
                        points
                    )
                    VALUES (%s,%s,0,0,0,0,0,0,0,0)
                    ON CONFLICT (team)
                    DO NOTHING
                """, (
                    team,
                    group_letter
                ))