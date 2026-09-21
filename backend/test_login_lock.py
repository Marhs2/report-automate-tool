import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import HTTPException

from auth import hash_password
from main import (
    LoginRequest,
    PasswordChangeRequest,
    PasswordSetRequest,
    SetTeamData,
    TeamRequest,
    UserRequest,
    change_my_password,
    login,
    save_team,
    save_user,
    set_member_password,
    set_team,
)


def _memory_db(*seed_sql):
    @contextmanager
    def fake_db():
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE members (
                id INTEGER PRIMARY KEY,
                name TEXT,
                team_id INTEGER,
                password_hash TEXT,
                is_admin INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute("CREATE TABLE sessions (token TEXT, member_id INTEGER)")
        conn.execute("CREATE TABLE teams (id INTEGER PRIMARY KEY, team_name TEXT)")
        conn.execute("INSERT INTO teams VALUES (1, '개발')")
        for sql, params in seed_sql:
            conn.execute(sql, params)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    return fake_db


class LoginClaimTests(unittest.TestCase):
    def test_empty_password_cannot_be_claimed(self):
        fake = _memory_db(("INSERT INTO members VALUES (8, '김재휘', 1, '', 0)", ()))
        with patch("main.get_db", fake):
            with self.assertRaises(HTTPException) as ctx:
                login(LoginRequest(name="김재휘", password="abcd"))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("아직 없습니다", ctx.exception.detail)

    def test_wrong_password_stays_401(self):
        fake = _memory_db(
            ("INSERT INTO members VALUES (1, '정동일', 1, ?, 1)", (hash_password("right-one"),)),
        )
        with patch("main.get_db", fake):
            with self.assertRaises(HTTPException) as ctx:
                login(LoginRequest(name="정동일", password="wrong"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_valid_login_issues_token(self):
        fake = _memory_db(
            ("INSERT INTO members VALUES (1, '정동일', 1, ?, 1)", (hash_password("right-one"),)),
        )
        with patch("main.get_db", fake):
            result = login(LoginRequest(name="정동일", password="right-one"))
        self.assertEqual(result["member_id"], 1)
        self.assertTrue(result["token"])
        self.assertTrue(result["is_admin"])


class TeamOwnTests(unittest.TestCase):
    def test_cannot_change_other_member_team(self):
        fake = _memory_db(
            ("INSERT INTO members VALUES (1, '정동일', 1, '', 0)", ()),
            ("INSERT INTO members VALUES (2, '다른이', 1, '', 0)", ()),
        )
        with patch("main.get_db", fake):
            with self.assertRaises(HTTPException) as ctx:
                set_team(SetTeamData(team_id=1, user_id=2), actor_id=1)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "자신의 부서만 변경할 수 있습니다.")

    def test_admin_can_change_other_member_team(self):
        fake = _memory_db(
            ("INSERT INTO members VALUES (1, '정동일', 1, '', 1)", ()),
            ("INSERT INTO members VALUES (2, '다른이', 1, '', 0)", ()),
        )
        with patch("main.get_db", fake):
            result = set_team(SetTeamData(team_id=1, user_id=2), actor_id=1)
        self.assertIn("successfully", result["message"])


class PasswordRouteTests(unittest.TestCase):
    def test_set_password_only_when_empty(self):
        fake = _memory_db(
            ("INSERT INTO members VALUES (1, '정동일', 1, ?, 1)", (hash_password("old-pass"),)),
            ("INSERT INTO members VALUES (2, '빈계정', 1, '', 0)", ()),
        )
        with patch("main.get_db", fake):
            with self.assertRaises(HTTPException) as ctx:
                set_member_password(1, PasswordSetRequest(password="new-pass"), actor_id=2)
            self.assertEqual(ctx.exception.status_code, 403)
            result = set_member_password(2, PasswordSetRequest(password="temp12"), actor_id=1)
        self.assertIn("임시", result["message"])

    def test_non_admin_cannot_set_empty_password(self):
        fake = _memory_db(
            ("INSERT INTO members VALUES (1, '정동일', 1, ?, 0)", (hash_password("old-pass"),)),
            ("INSERT INTO members VALUES (2, '빈계정', 1, '', 0)", ()),
        )
        with patch("main.get_db", fake):
            with self.assertRaises(HTTPException) as ctx:
                set_member_password(2, PasswordSetRequest(password="temp12"), actor_id=1)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("관리자", ctx.exception.detail)

    def test_change_own_password_rejects_wrong_current(self):
        fake = _memory_db(
            ("INSERT INTO members VALUES (1, '정동일', 1, ?, 1)", (hash_password("old-pass"),)),
        )
        with patch("main.get_db", fake):
            with self.assertRaises(HTTPException) as ctx:
                change_my_password(
                    PasswordChangeRequest(current_password="nope", new_password="new-pass"),
                    actor_id=1,
                )
            self.assertEqual(ctx.exception.status_code, 401)

    def test_change_own_password_accepts_current(self):
        fake = _memory_db(
            ("INSERT INTO members VALUES (1, '정동일', 1, ?, 1)", (hash_password("old-pass"),)),
        )
        with patch("main.get_db", fake):
            result = change_my_password(
                PasswordChangeRequest(current_password="old-pass", new_password="new-pass"),
                actor_id=1,
            )
        self.assertIn("바꿨습니다", result["message"])


class AdminGateTests(unittest.TestCase):
    def test_non_admin_cannot_create_team(self):
        fake = _memory_db(("INSERT INTO members VALUES (2, '일반', 1, '', 0)", ()))
        with patch("main.get_db", fake):
            with self.assertRaises(HTTPException) as ctx:
                save_team(TeamRequest(team_name="새부서"), actor_id=2)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_can_create_team(self):
        fake = _memory_db(("INSERT INTO members VALUES (1, '관리', 1, '', 1)", ()))
        with patch("main.get_db", fake):
            result = save_team(TeamRequest(team_name="새부서"), actor_id=1)
        self.assertIn("successfully", result["message"])

    def test_non_admin_cannot_create_user(self):
        fake = _memory_db(
            ("INSERT INTO members VALUES (2, '일반', 1, '', 0)", ()),
            ("INSERT INTO sessions VALUES ('tok', 2)", ()),
        )
        with patch("main.get_db", fake):
            with self.assertRaises(HTTPException) as ctx:
                save_user(
                    UserRequest(name="신규", password="pass12"),
                    authorization="Bearer tok",
                )
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
