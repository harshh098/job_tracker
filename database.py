import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("DATABASE", "resume_jobs.db")


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

    with get_db() as conn:
        with open(schema_path, "r") as f:
            conn.executescript(f.read())

        columns = [row[1] for row in conn.execute(
            "PRAGMA table_info(users)"
        ).fetchall()]

        if "display_name" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT")

        if "job_title" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN job_title TEXT")

        if "location" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN location TEXT")

        if "last_login" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_login DATETIME")

        conn.commit()