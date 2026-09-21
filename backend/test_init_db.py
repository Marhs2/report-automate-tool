import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auth import verify_password
from init_db import create_tables, ensure_default_admin, init_database


class DefaultAdminSeedTests(unittest.TestCase):
    def _fresh(self):
        conn = sqlite3.connect(":memory:")
        create_tables(conn)
        return conn

    def test_empty_db_creates_admin(self):
        conn = self._fresh()
        created = ensure_default_admin(conn)
        self.assertIsNotNone(created)
        self.assertEqual(created["name"], "관리자")
        self.assertEqual(created["password"], "admin1234")
        row = conn.execute(
            "SELECT name, is_admin, password_hash FROM members"
        ).fetchone()
        self.assertEqual(row[0], "관리자")
        self.assertEqual(row[1], 1)
        self.assertTrue(verify_password("admin1234", row[2]))
        conn.close()

    def test_existing_members_are_not_touched(self):
        conn = self._fresh()
        team_id = conn.execute(
            "INSERT INTO teams (team_name) VALUES ('개발')"
        ).lastrowid
        conn.execute(
            "INSERT INTO members (name, team_id, password_hash, is_admin) VALUES (?, ?, '', 0)",
            ("이미있음", team_id),
        )
        created = ensure_default_admin(conn)
        self.assertIsNone(created)
        names = [r[0] for r in conn.execute("SELECT name FROM members").fetchall()]
        self.assertEqual(names, ["이미있음"])
        conn.close()

    def test_second_call_is_noop(self):
        conn = self._fresh()
        first = ensure_default_admin(conn)
        second = ensure_default_admin(conn)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        count = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        self.assertEqual(count, 1)
        conn.close()

    def test_missing_members_table_is_noop(self):
        conn = sqlite3.connect(":memory:")
        self.assertIsNone(ensure_default_admin(conn))
        conn.close()

    def test_init_database_creates_admin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fresh.db"
            created = init_database(path)
            self.assertEqual(created["name"], "관리자")
            conn = sqlite3.connect(path)
            row = conn.execute("SELECT name, is_admin FROM members").fetchone()
            self.assertEqual(row, ("관리자", 1))
            conn.close()

    def test_env_overrides_name_and_password(self):
        conn = self._fresh()
        with patch("init_db.DEFAULT_ADMIN_NAME", "운영관리"), patch(
            "init_db.DEFAULT_ADMIN_PASSWORD", "secret99"
        ):
            created = ensure_default_admin(conn)
        self.assertEqual(created["name"], "운영관리")
        self.assertEqual(created["password"], "secret99")
        row = conn.execute("SELECT name, password_hash FROM members").fetchone()
        self.assertTrue(verify_password("secret99", row[1]))
        conn.close()


if __name__ == "__main__":
    unittest.main()
