import os
import sqlite3
from pathlib import Path

from auth import hash_password

BASE_DIR = Path(__file__).parent

DB_DIR = BASE_DIR / "data"
DB_DIR.mkdir(exist_ok=True)

DB_PATH = DB_DIR / "daily_reports.db"

DEFAULT_ADMIN_NAME = os.environ.get("ADMIN_NAME", "관리자").strip() or "관리자"
DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin1234")
DEFAULT_TEAM_NAME = "미지정"


def create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_name TEXT NOT NULL UNIQUE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(team_name)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        team_id INTEGER NOT NULL,
        password_hash TEXT NOT NULL DEFAULT '',
        is_admin INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (team_id) REFERENCES teams(id)
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
        FOREIGN KEY (member_id) REFERENCES members(id),
        UNIQUE(member_id, report_date)
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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        report_date DATE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weekly_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        selected_date TEXT NOT NULL,
        report_json TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (member_id) REFERENCES members(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_report_drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        report_date DATE NOT NULL,
        raw_text TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (member_id) REFERENCES members(id),
        UNIQUE(member_id, report_date)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS report_drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER NOT NULL,
        report_date DATE NOT NULL,
        raw_text TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (member_id) REFERENCES members(id),
        UNIQUE(member_id, report_date)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        member_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (member_id) REFERENCES members(id)
    )
    """)


def _team_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT id FROM teams WHERE team_name = ?",
        (DEFAULT_TEAM_NAME,),
    ).fetchone()
    if row:
        return row[0]
    cursor = conn.execute(
        "INSERT INTO teams (team_name) VALUES (?)",
        (DEFAULT_TEAM_NAME,),
    )
    return cursor.lastrowid


def ensure_default_admin(conn: sqlite3.Connection) -> dict | None:
    """빈 사용자 테이블에만 기본 관리자를 넣는다. 이미 사람이 있으면 건드리지 않는다."""
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "members" not in tables:
        return None
    count = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    if count:
        return None

    name = DEFAULT_ADMIN_NAME
    password = DEFAULT_ADMIN_PASSWORD
    hashed = hash_password(password)
    team_id = _team_id(conn)
    cursor = conn.execute(
        """
        INSERT INTO members (name, team_id, password_hash, is_admin)
        VALUES (?, ?, ?, 1)
        """,
        (name, team_id, hashed),
    )
    return {
        "id": cursor.lastrowid,
        "name": name,
        "password": password,
        "team_id": team_id,
    }


def init_database(db_path: Path | str = DB_PATH) -> dict | None:
    conn = sqlite3.connect(db_path)
    try:
        create_tables(conn)
        created = ensure_default_admin(conn)
        conn.commit()
        return created
    finally:
        conn.close()


if __name__ == "__main__":
    created = init_database()
    print(f"DB 생성 완료: {DB_PATH}")
    if created:
        print(
            f"기본 관리자 계정: {created['name']} / {created['password']}"
            "  (ADMIN_NAME, ADMIN_PASSWORD 환경변수로 바꿀 수 있습니다)"
        )
    else:
        print("기존 사용자가 있어 기본 관리자는 만들지 않았습니다.")
