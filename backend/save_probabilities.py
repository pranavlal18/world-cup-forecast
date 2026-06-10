from backend.database import get_db
from datetime import datetime

def save_probabilities_to_db(teams):
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("DELETE FROM probabilities")

        for team in teams:
            
            cur.execute("""
                INSERT INTO probabilities (
                    team,
                    group_letter,
                    elo,
                    round_of_32,
                    round_of_16,
                    quarter_final,
                    semi_final,
                    final,
                    champion,
                    generated_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
    str(team["team"]),
    str(team["group"]),
    float(team["elo"]),
    float(team["round_of_32"]),
    float(team["round_of_16"]),
    float(team["quarter_final"]),
    float(team["semi_final"]),
    float(team["final"]),
    float(team["champion"]),
    datetime.utcnow()
))