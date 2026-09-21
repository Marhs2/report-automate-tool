import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import HTTPException

from main import (
    plain_parse_daily,
    require_own_member,
    require_own_or_admin,
    visible_raw_text,
)


class RequireOwnMemberTests(unittest.TestCase):
    def test_same_member_passes(self):
        require_own_member(3, 3)

    def test_other_member_is_forbidden(self):
        with self.assertRaises(HTTPException) as ctx:
            require_own_member(1, 2)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "자신의 것만 수정할 수 있습니다.")

    def test_custom_message(self):
        with self.assertRaises(HTTPException) as ctx:
            require_own_member(1, 9, "자신의 부서만 변경할 수 있습니다.")
        self.assertEqual(ctx.exception.detail, "자신의 부서만 변경할 수 있습니다.")


class RequireOwnOrAdminTests(unittest.TestCase):
    def _db(self, is_admin):
        @contextmanager
        def fake_db():
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            conn.execute("CREATE TABLE members (id INTEGER, is_admin INTEGER)")
            conn.execute("INSERT INTO members VALUES (1, ?)", (1 if is_admin else 0,))
            try:
                yield conn
            finally:
                conn.close()

        return fake_db

    def test_owner_passes(self):
        require_own_or_admin(4, 4)

    def test_admin_can_edit_other(self):
        with patch("main.get_db", self._db(True)):
            require_own_or_admin(1, 9)

    def test_non_admin_cannot_edit_other(self):
        with patch("main.get_db", self._db(False)):
            with self.assertRaises(HTTPException) as ctx:
                require_own_or_admin(1, 9)
        self.assertEqual(ctx.exception.status_code, 403)


class VisibleRawTextTests(unittest.TestCase):
    def test_owner_keeps_raw(self):
        self.assertEqual(visible_raw_text(4, 4, "비밀"), "비밀")

    def test_other_member_gets_none(self):
        self.assertIsNone(visible_raw_text(1, 2, "비밀"))


class PlainParseDailyTests(unittest.TestCase):
    def test_drops_template_headings(self):
        parsed = plain_parse_daily(
            "프로젝트 명:\n[완료]\n- 배포 점검\n[진행]\n- 로그 확인\n"
        )
        self.assertEqual(parsed["projects"][0]["projectName"], "오늘 보고")
        self.assertEqual(
            parsed["projects"][0]["completedTasks"],
            ["배포 점검", "로그 확인"],
        )

    def test_empty_is_empty_projects(self):
        self.assertEqual(plain_parse_daily("   "), {"projects": []})


if __name__ == "__main__":
    unittest.main()
