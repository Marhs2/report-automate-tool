"""전 팀 주간보고 취합: 한 주에 누가 냈는지 보고, 낸 보고를 팀 → 사람 순으로 모은다.

주간보고는 사람마다 한 주에 하나다(replace_member_week). 같은 주에 여러 행이 남아 있으면 가장 늦게 만든 것을 쓴다.
관리자 계정은 보고 대상이 아니므로, 그 주에 낸 경우에만 목록에 넣는다.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from weekly_deck import format_dot_date, week_start_of


class CollectionError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def monday_of(value) -> date:
    """YYYY-MM-DD(그 주 아무 날) → 그 주 월요일. 비어 있으면 이번 주."""
    text = str(value or "").strip()
    if not text:
        day = date.today()
    else:
        try:
            day = date.fromisoformat(text[:10])
        except ValueError:
            raise CollectionError("주는 YYYY-MM-DD 형식이어야 합니다.")
    return day - timedelta(days=day.weekday())


def _latest_by_member(conn, monday: date) -> dict:
    key = monday.isoformat()
    latest = {}
    rows = conn.execute(
        "SELECT id, member_id, selected_date, report_json, created_at FROM weekly_reports ORDER BY created_at, id"
    ).fetchall()
    for row in rows:
        try:
            dates = json.loads(row["selected_date"] or "[]")
        except json.JSONDecodeError:
            continue
        if week_start_of(dates) == key:
            latest[int(row["member_id"])] = row
    return latest


def led_team_id(conn, member_id: int):
    """이 사람이 팀장인 부서 id. 다른 부서로 옮기면 팀장이 아니다."""
    row = conn.execute(
        """
        SELECT t.id FROM teams t
        JOIN members m ON m.team_id = t.id
        WHERE t.leader_id = ? AND m.id = ?
        """,
        (member_id, member_id),
    ).fetchone()
    return int(row["id"]) if row else None


def collection_status(conn, monday: date, team_id: int | None = None) -> dict:
    """team_id가 있으면 그 부서만(팀장 취합), 없으면 전 부서(관리자 취합)."""
    latest = _latest_by_member(conn, monday)
    members = conn.execute(
        """
        SELECT m.id, m.name, m.is_admin, t.id AS team_id, t.team_name
        FROM members m
        LEFT JOIN teams t ON m.team_id = t.id
        WHERE ? IS NULL OR m.team_id = ?
        ORDER BY t.id, m.name
        """,
        (team_id, team_id),
    ).fetchall()
    teams, by_team = [], {}
    for member in members:
        row = latest.get(int(member["id"]))
        if member["is_admin"] and row is None:
            continue
        team_key = member["team_id"]
        if team_key not in by_team:
            by_team[team_key] = {"id": team_key, "name": member["team_name"] or "부서 없음", "members": []}
            teams.append(by_team[team_key])
        by_team[team_key]["members"].append(
            {
                "id": int(member["id"]),
                "name": member["name"],
                "submitted": row is not None,
                "weeklyId": int(row["id"]) if row is not None else None,
                "createdAt": row["created_at"] if row is not None else None,
            }
        )
    for team in teams:
        team["submitted"] = sum(1 for m in team["members"] if m["submitted"])
        team["total"] = len(team["members"])
    submitted = sum(team["submitted"] for team in teams)
    total = sum(team["total"] for team in teams)
    friday = monday + timedelta(days=4)
    return {
        "week": {
            "start": monday.isoformat(),
            "end": friday.isoformat(),
            "label": f"{monday.month}.{monday.day} ~ {friday.month}.{friday.day}",
        },
        "teams": teams,
        "submitted": submitted,
        "total": total,
        "complete": total > 0 and submitted == total,
    }


def collected_rows(
    conn, monday: date, *, partial: bool, team_id: int | None = None
) -> tuple[dict, list[tuple[dict, dict]]]:
    """(현황, [(팀 · 사람 정보, weekly_reports 행)]) 를 팀 → 사람 순으로. 다 내지 않았으면 partial일 때만 넘어간다."""
    status = collection_status(conn, monday, team_id)
    if status["submitted"] == 0:
        raise CollectionError("이 주에 낸 주간보고가 없습니다.", 404)
    if not status["complete"] and not partial:
        missing = status["total"] - status["submitted"]
        raise CollectionError(f"아직 {missing}명이 주간보고를 내지 않았습니다.", 409)
    latest = _latest_by_member(conn, monday)
    out = []
    for team in status["teams"]:
        for member in team["members"]:
            if member["submitted"]:
                out.append(({"teamName": team["name"], "memberName": member["name"]}, latest[member["id"]]))
    return status, out


def cover_date(monday: date) -> str:
    return format_dot_date(monday + timedelta(days=4))
