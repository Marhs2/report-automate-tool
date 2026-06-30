import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent

DB_DIR = BASE_DIR / "data"
DB_DIR.mkdir(exist_ok=True)

DB_PATH = DB_DIR / "daily_reports.db"


def get_db():
    return sqlite3.connect(DB_PATH)
