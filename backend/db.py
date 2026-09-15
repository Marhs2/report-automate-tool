import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).parent

DB_DIR = BASE_DIR / "data"
DB_DIR.mkdir(exist_ok=True)

DB_PATH = DB_DIR / "daily_reports.db"


@contextmanager
def get_db():
    """Open SQLite with DELETE journal so GUI viewers see committed data.

    WAL keeps recent writes in ``*.db-wal`` until checkpoint. Many VS Code /
    Cursor SQLite extensions only refresh the main ``.db`` file, so updates
    look missing. DELETE mode writes commits into the main database file.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    # Flush any leftover WAL into the main file, then stay on DELETE.
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    mode = conn.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
    if str(mode).lower() != "delete":
        # Another connection may still hold WAL; force a second checkpoint try.
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA journal_mode = DELETE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
