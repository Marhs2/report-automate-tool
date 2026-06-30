import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent

DB_DIR = BASE_DIR / "data"
DB_DIR.mkdir(exist_ok=True)

DB_PATH = DB_DIR / "daily_reports.db"

conn = sqlite3.connect(DB_PATH)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL ,
    report_date DATE NOT NULL DEFAULT CURRENT_DATE,
    raw_text TEXT NOT NULL,
    parsed_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    completed_tasks TEXT,
    in_progress_tasks TEXT,
    issues TEXT,
    requests TEXT,
    next_plans TEXT,
    important_summary TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")


conn.commit()
conn.close()

print(f"DB 생성 완료: {DB_PATH}")
