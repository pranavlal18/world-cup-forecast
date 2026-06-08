import os
import psycopg2
from contextlib import contextmanager
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Create tables if they don't exist."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS probabilities (
                team VARCHAR(100) PRIMARY KEY,
                group_letter CHAR(1),
                elo FLOAT,
                round_of_32 FLOAT,
                round_of_16 FLOAT,
                quarter_final FLOAT,
                semi_final FLOAT,
                final FLOAT,
                champion FLOAT,
                generated_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS processed_matches (
                match_id INTEGER PRIMARY KEY,
                processed_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS group_standings (
                team VARCHAR(100) PRIMARY KEY,
                group_letter CHAR(1),
                played INT DEFAULT 0,
                won INT DEFAULT 0,
                drawn INT DEFAULT 0,
                lost INT DEFAULT 0,
                gf INT DEFAULT 0,
                ga INT DEFAULT 0,
                gd INT DEFAULT 0,
                points INT DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS fixtures (
                match_id INTEGER PRIMARY KEY,
                date DATE,
                time_utc TIME,
                stage VARCHAR(50),
                group_letter CHAR(1),
                team1 VARCHAR(100),
                team2 VARCHAR(100),
                status VARCHAR(20)
            );
        """)