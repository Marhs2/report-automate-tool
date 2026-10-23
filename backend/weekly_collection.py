"""주간보고 취합: 부서마다 한 주에 하나인 부서 주간보고를 누가 냈는지 보고, 낸 것을 부서 순으로 모은다.

부서 주간보고는 팀장(또는 관리자)이 만든다(replace_team_week). 같은 주에 여러 행이 남아 있으면 가장 늦게 만든 것을 쓴다.
일반 사용자 없이 관리자만 있는 부서는 보고 대상이 아니므로, 그 주에 낸 경우에만 목록에 넣는다.
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


def _latest_by_team(conn, monday: date) -> dict:
    key = monday.isoformat()
    latest = {}
    rows = conn.execute(
        """
        SELECT w.id, w.team_id, w.member_id, w.selected_date, w.report_json, w.created_at, m.name AS author_name
        FROM weekly_reports w
        LEFT JOIN members m ON m.id = w.member_id
        WHERE w.team_id IS NOT NULL
        ORDER BY w.created_at, w.id
        """
    ).fetchall()
    for row in rows:
        try:
            dates = json.loads(row["selected_date"] or "[]")
        except json.JSONDecodeError:
            continue
        if week_start_of(dates) == key:
            latest[int(row["team_id"])] = row
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
    """team_id가 있으면 그 부서만(팀장), 없으면 전 부서(관리자). 부서마다 냈는지 · 누가 만들었는지."""
    latest = _latest_by_team(conn, monday)
    rows = conn.execute(
        """
        SELECT t.id, t.team_name, t.leader_id, l.name AS leader_name,
               SUM(CASE WHEN m.id IS NOT NULL AND IFNULL(m.is_admin, 0) = 0 THEN 1 ELSE 0 END) AS people
        FROM teams t
        LEFT JOIN members m ON m.team_id = t.id
        LEFT JOIN members l ON l.id = t.leader_id
        WHERE ? IS NULL OR t.id = ?
        GROUP BY t.id
        ORDER BY t.id
        """,
        (team_id, team_id),
    ).fetchall()
    teams = []
    for team in rows:
        row = latest.get(int(team["id"]))
        if not team["people"] and row is None:
            continue
        teams.append(
            {
                "id": int(team["id"]),
                "name": team["team_name"],
                "people": int(team["people"] or 0),
                "leaderName": team["leader_name"] or "",
                "submitted": row is not None,
                "weeklyId": int(row["id"]) if row is not None else None,
                "authorName": (row["author_name"] or "") if row is not None else "",
                "createdAt": row["created_at"] if row is not None else None,
            }
        )
    submitted = sum(1 for team in teams if team["submitted"])
    total = len(teams)
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
    """(현황, [(부서 · 만든 사람, weekly_reports 행)]) 를 부서 순으로. 다 내지 않았으면 partial일 때만 넘어간다."""
    status = collection_status(conn, monday, team_id)
    if status["submitted"] == 0:
        raise CollectionError("이 주에 낸 부서 주간보고가 없습니다.", 404)
    if not status["complete"] and not partial:
        missing = status["total"] - status["submitted"]
        raise CollectionError(f"아직 {missing}개 부서가 주간보고를 내지 않았습니다.", 409)
    latest = _latest_by_team(conn, monday)
    out = []
    for team in status["teams"]:
        if team["submitted"]:
            row = latest[team["id"]]
            out.append(({"teamName": team["name"], "memberName": row["author_name"] or ""}, row))
    return status, out


def cover_date(monday: date) -> str:
    return format_dot_date(monday + timedelta(days=4))
