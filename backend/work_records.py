"""회의록·일반보고·영업보고와 명함, 내 현황 조회.

일일보고 추출 스키마와 주간 병합에는 넣지 않는다.
영업보고의 명함은 이름과 전화 또는 이메일이 같으면 잇고,
이미 있는 소속·직함·연락처는 덮어쓰지 않는다.
"""

from __future__ import annotations

import json
import re
from datetime import date

from weekly_deck import week_start_of

WORK_KINDS = ("meeting", "general", "sales")
SYNTHETIC_PROJECTS = {"", "미분류 프로젝트", "오늘 보고"}
KIND_LABELS = {
    "daily": "일일보고",
    "weekly": "주간보고",
    "meeting": "회의록",
    "general": "일반보고",
    "sales": "영업보고",
}


class WorkRecordError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def ensure_work_tables(conn) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS business_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            organization TEXT NOT NULL DEFAULT '',
            job_title TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            memo TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (member_id) REFERENCES members(id)
        );

        CREATE TABLE IF NOT EXISTS work_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            report_date DATE NOT NULL,
            project_name TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            details_json TEXT NOT NULL DEFAULT '{}',
            card_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (member_id) REFERENCES members(id)
        );

        CREATE INDEX IF NOT EXISTS idx_work_records_member
            ON work_records(member_id, report_date);
        CREATE INDEX IF NOT EXISTS idx_business_cards_member
            ON business_cards(member_id);
        """
    )


def _limit(value, limit: int, label: str) -> str:
    text = str(value or "").replace("\x00", "").strip()
    if len(text) > limit:
        raise WorkRecordError(f"{label}은(는) {limit}자까지입니다.")
    return text


def _date_text(value, *, required: bool) -> str:
    text = str(value or "").strip()
    if not text:
        if required:
            raise WorkRecordError("날짜는 YYYY-MM-DD 형식이어야 합니다.")
        return ""
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise WorkRecordError("날짜는 YYYY-MM-DD 형식이어야 합니다.")


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _email_ok(value: str) -> bool:
    if any(ch.isspace() for ch in value):
        return False
    local, sep, host = value.partition("@")
    return bool(sep and local and "." in host and not host.startswith("."))


def _followups(raw) -> list[dict]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise WorkRecordError("후속 할 일은 목록이어야 합니다.")
    items = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        task = _limit(row.get("task"), 500, "후속 할 일")
        if not task:
            continue
        items.append(
            {
                "task": task,
                "owner": _limit(row.get("owner"), 80, "후속 담당"),
                "due": _date_text(row.get("due"), required=False),
            }
        )
    if len(items) > 30:
        raise WorkRecordError("후속 할 일은 30개까지입니다.")
    return items


def _card_id(value):
    if value in (None, "", 0, "0"):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise WorkRecordError("명함 선택이 올바르지 않습니다.")
    if number < 1:
        return None
    return number


def normalize_work(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise WorkRecordError("내용이 올바르지 않습니다.")
    kind = str(payload.get("kind") or "").strip()
    if kind not in WORK_KINDS:
        raise WorkRecordError("보고 형식이 올바르지 않습니다.")
    report_date = _date_text(
        payload.get("reportDate", payload.get("report_date")),
        required=True,
    )
    project_name = _limit(
        payload.get("projectName", payload.get("project_name")),
        120,
        "프로젝트명",
    )
    title = _limit(payload.get("title"), 200, "제목")

    if kind == "meeting":
        details = {
            "heldAt": _limit(payload.get("heldAt"), 40, "일시"),
            "place": _limit(payload.get("place"), 120, "장소"),
            "attendees": _limit(payload.get("attendees"), 500, "참석자"),
            "agenda": _limit(payload.get("agenda"), 4000, "안건"),
            "decisions": _limit(payload.get("decisions"), 4000, "결정"),
            "followups": _followups(payload.get("followups")),
        }
        if (
            not details["agenda"]
            and not details["decisions"]
            and not details["followups"]
        ):
            raise WorkRecordError("안건, 결정, 후속 할 일 중 하나는 적어 주세요.")
        if not title:
            source = details["agenda"] or details["decisions"]
            if not source and details["followups"]:
                source = details["followups"][0]["task"]
            title = source[:40]
        body = details["agenda"] or details["decisions"]
    elif kind == "general":
        body = _limit(payload.get("body"), 8000, "본문")
        if not title:
            raise WorkRecordError("제목을 입력해주세요.")
        if not body:
            raise WorkRecordError("본문을 입력해주세요.")
        details = {}
    else:
        contact = _limit(payload.get("contactName"), 80, "담당자명")
        phone = _limit(payload.get("phone"), 40, "전화번호")
        email = _limit(payload.get("email"), 120, "이메일")
        progress = _limit(payload.get("progress"), 4000, "진행사항")
        if not project_name:
            raise WorkRecordError("프로젝트명을 입력해주세요.")
        if not contact:
            raise WorkRecordError("담당자명을 입력해주세요.")
        if not phone and not email:
            raise WorkRecordError("전화번호 또는 이메일을 입력해주세요.")
        if phone and len(_digits(phone)) < 8:
            raise WorkRecordError("전화번호가 너무 짧습니다.")
        if email and not _email_ok(email):
            raise WorkRecordError("이메일 형식이 올바르지 않습니다.")
        if not progress:
            raise WorkRecordError("진행사항을 입력해주세요.")
        if not title:
            title = f"{project_name} · {contact}"[:200]
        details = {
            "contactName": contact,
            "phone": phone,
            "email": email,
            "organization": _limit(payload.get("organization"), 120, "소속"),
            "jobTitle": _limit(payload.get("jobTitle"), 80, "직함"),
            "progress": progress,
            "nextSteps": _limit(payload.get("nextSteps"), 4000, "추후 진행사항"),
            "saveCard": bool(payload.get("saveCard", True)),
            "cardId": _card_id(payload.get("cardId")),
        }
        body = progress

    return {
        "kind": kind,
        "title": title,
        "report_date": report_date,
        "project_name": project_name,
        "body": body,
        "details": details,
    }


def normalize_card(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise WorkRecordError("명함 내용이 올바르지 않습니다.")
    name = _limit(payload.get("name"), 80, "이름")
    phone = _limit(payload.get("phone"), 40, "전화번호")
    email = _limit(payload.get("email"), 120, "이메일")
    if not name:
        raise WorkRecordError("이름을 입력해주세요.")
    if not phone and not email:
        raise WorkRecordError("전화번호 또는 이메일을 입력해주세요.")
    if phone and len(_digits(phone)) < 8:
        raise WorkRecordError("전화번호가 너무 짧습니다.")
    if email and not _email_ok(email):
        raise WorkRecordError("이메일 형식이 올바르지 않습니다.")
    return {
        "name": name,
        "organization": _limit(payload.get("organization"), 120, "소속"),
        "job_title": _limit(
            payload.get("jobTitle", payload.get("job_title")), 80, "직함"
        ),
        "phone": phone,
        "email": email,
        "memo": _limit(payload.get("memo"), 1000, "메모"),
    }


def _details(row) -> dict:
    if row is None:
        return {}
    try:
        data = json.loads(row["details_json"] or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _json_list(raw) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item).strip() for item in data if str(item).strip()]


def record_out(row) -> dict:
    details = _details(row)
    details.pop("cardId", None)
    payload = {
        "id": row["id"],
        "kind": row["kind"],
        "kindLabel": KIND_LABELS.get(row["kind"], row["kind"]),
        "title": row["title"],
        "reportDate": row["report_date"],
        "projectName": row["project_name"],
        "body": row["body"],
        "cardId": row["card_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
    payload.update(details)
    payload["cardId"] = row["card_id"]
    if row["kind"] == "general":
        payload["body"] = row["body"]
    return payload


def card_out(row, sales=None) -> dict:
    payload = {
        "id": row["id"],
        "name": row["name"],
        "organization": row["organization"],
        "jobTitle": row["job_title"],
        "phone": row["phone"],
        "email": row["email"],
        "memo": row["memo"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
    if sales is not None:
        payload["sales"] = sales
    return payload


def _own_record(conn, member_id: int, record_id: int):
    row = conn.execute(
        "SELECT * FROM work_records WHERE id = ?",
        (record_id,),
    ).fetchone()
    if row is None:
        raise WorkRecordError("기록을 찾을 수 없습니다.", 404)
    if int(row["member_id"]) != int(member_id):
        raise WorkRecordError("자신의 것만 수정할 수 있습니다.", 403)
    return row


def _own_card(conn, member_id: int, card_id: int):
    row = conn.execute(
        "SELECT * FROM business_cards WHERE id = ?",
        (card_id,),
    ).fetchone()
    if row is None:
        raise WorkRecordError("명함을 찾을 수 없습니다.", 404)
    if int(row["member_id"]) != int(member_id):
        raise WorkRecordError("자신의 것만 수정할 수 있습니다.", 403)
    return row


def find_card(conn, member_id: int, name: str, phone: str, email: str):
    name_key = name.strip().casefold()
    phone_key = _digits(phone)
    email_key = email.strip().casefold()
    phone_hit = None
    email_hit = None
    rows = conn.execute(
        "SELECT * FROM business_cards WHERE member_id = ? ORDER BY id",
        (member_id,),
    ).fetchall()
    for row in rows:
        if str(row["name"] or "").strip().casefold() != name_key:
            continue
        row_phone = _digits(row["phone"])
        row_email = str(row["email"] or "").strip().casefold()
        if phone_key and row_phone and phone_key == row_phone and phone_hit is None:
            phone_hit = row
        if email_key and row_email and email_key == row_email and email_hit is None:
            email_hit = row
    return phone_hit or email_hit


def _blank_fill(current, incoming) -> str:
    if str(current or "").strip():
        return str(current)
    return str(incoming or "").strip()


def _fill_card(conn, row, details: dict) -> None:
    conn.execute(
        """
        UPDATE business_cards
        SET organization = ?, job_title = ?, phone = ?, email = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            _blank_fill(row["organization"], details.get("organization")),
            _blank_fill(row["job_title"], details.get("jobTitle")),
            _blank_fill(row["phone"], details.get("phone")),
            _blank_fill(row["email"], details.get("email")),
            row["id"],
        ),
    )


def link_card(conn, member_id: int, details: dict):
    requested = details.get("cardId")
    save = bool(details.get("saveCard", True))
    if requested is not None:
        row = _own_card(conn, member_id, int(requested))
        if save:
            _fill_card(conn, row, details)
        return int(row["id"])
    if not save:
        return None
    found = find_card(
        conn,
        member_id,
        details.get("contactName") or "",
        details.get("phone") or "",
        details.get("email") or "",
    )
    if found is not None:
        _fill_card(conn, found, details)
        return int(found["id"])
    cursor = conn.execute(
        """
        INSERT INTO business_cards (
            member_id, name, organization, job_title, phone, email, memo
        ) VALUES (?, ?, ?, ?, ?, ?, '')
        """,
        (
            member_id,
            details.get("contactName") or "",
            details.get("organization") or "",
            details.get("jobTitle") or "",
            details.get("phone") or "",
            details.get("email") or "",
        ),
    )
    return int(cursor.lastrowid)


def remember_project(conn, name: str) -> None:
    name = name.strip()
    if not name:
        return
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "known_projects" not in tables:
        return
    conn.execute(
        """
        INSERT INTO known_projects (name, keywords)
        VALUES (?, '')
        ON CONFLICT(name) DO NOTHING
        """,
        (name,),
    )


def save_work_record(conn, member_id: int, payload: dict, record_id: int | None = None) -> dict:
    data = normalize_work(payload)
    if record_id is not None:
        _own_record(conn, member_id, record_id)
    card_id = None
    if data["kind"] == "sales":
        card_id = link_card(conn, member_id, data["details"])
    if data["project_name"]:
        remember_project(conn, data["project_name"])
    blob = json.dumps(data["details"], ensure_ascii=False)
    columns = (
        data["kind"],
        data["title"],
        data["report_date"],
        data["project_name"],
        data["body"],
        blob,
        card_id,
    )
    if record_id is None:
        cursor = conn.execute(
            """
            INSERT INTO work_records (
                kind, title, report_date, project_name, body, details_json,
                card_id, member_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*columns, member_id),
        )
        record_id = int(cursor.lastrowid)
    else:
        conn.execute(
            """
            UPDATE work_records
            SET kind = ?, title = ?, report_date = ?, project_name = ?, body = ?,
                details_json = ?, card_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND member_id = ?
            """,
            (*columns, record_id, member_id),
        )
    row = conn.execute(
        "SELECT * FROM work_records WHERE id = ?",
        (record_id,),
    ).fetchone()
    return record_out(row)


def list_work_records(conn, member_id: int, kind: str | None = None) -> list[dict]:
    if kind:
        if kind not in WORK_KINDS:
            raise WorkRecordError("보고 형식이 올바르지 않습니다.")
        rows = conn.execute(
            """
            SELECT * FROM work_records
            WHERE member_id = ? AND kind = ?
            ORDER BY report_date DESC, id DESC
            """,
            (member_id, kind),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM work_records
            WHERE member_id = ?
            ORDER BY report_date DESC, id DESC
            """,
            (member_id,),
        ).fetchall()
    return [record_out(row) for row in rows]


def get_work_record(conn, member_id: int, record_id: int) -> dict:
    return record_out(_own_record(conn, member_id, record_id))


def delete_work_record(conn, member_id: int, record_id: int) -> None:
    _own_record(conn, member_id, record_id)
    conn.execute(
        "DELETE FROM work_records WHERE id = ? AND member_id = ?",
        (record_id, member_id),
    )


def _sales_of_card(conn, member_id: int, card_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM work_records
        WHERE member_id = ? AND kind = 'sales' AND card_id = ?
        ORDER BY report_date DESC, id DESC
        """,
        (member_id, card_id),
    ).fetchall()
    items = []
    for row in rows:
        details = _details(row)
        items.append(
            {
                "id": row["id"],
                "reportDate": row["report_date"],
                "projectName": row["project_name"],
                "progress": details.get("progress") or "",
                "nextSteps": details.get("nextSteps") or "",
                "href": f"/compose/{row['id']}",
            }
        )
    return items


def list_cards(conn, member_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM business_cards
        WHERE member_id = ?
        ORDER BY name, id
        """,
        (member_id,),
    ).fetchall()
    return [card_out(row, _sales_of_card(conn, member_id, row["id"])) for row in rows]


def get_card(conn, member_id: int, card_id: int) -> dict:
    row = _own_card(conn, member_id, card_id)
    return card_out(row, _sales_of_card(conn, member_id, card_id))


def save_card(conn, member_id: int, payload: dict, card_id: int | None = None) -> dict:
    data = normalize_card(payload)
    if card_id is None:
        cursor = conn.execute(
            """
            INSERT INTO business_cards (
                member_id, name, organization, job_title, phone, email, memo
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                member_id,
                data["name"],
                data["organization"],
                data["job_title"],
                data["phone"],
                data["email"],
                data["memo"],
            ),
        )
        card_id = int(cursor.lastrowid)
    else:
        _own_card(conn, member_id, card_id)
        conn.execute(
            """
            UPDATE business_cards
            SET name = ?, organization = ?, job_title = ?, phone = ?, email = ?,
                memo = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND member_id = ?
            """,
            (
                data["name"],
                data["organization"],
                data["job_title"],
                data["phone"],
                data["email"],
                data["memo"],
                card_id,
                member_id,
            ),
        )
    return get_card(conn, member_id, card_id)


def delete_card(conn, member_id: int, card_id: int) -> None:
    _own_card(conn, member_id, card_id)
    conn.execute(
        """
        UPDATE work_records
        SET card_id = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE member_id = ? AND card_id = ?
        """,
        (member_id, card_id),
    )
    conn.execute(
        "DELETE FROM business_cards WHERE id = ? AND member_id = ?",
        (card_id, member_id),
    )


def _stamp(at, day) -> str:
    text = str(at or "").strip()
    if text:
        return text
    day_text = str(day or "").strip()
    return f"{day_text} 00:00:00" if day_text else ""


def _clip(text: str, limit: int = 180) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _latest_daily_by_project(conn, member_id: int) -> dict:
    rows = conn.execute(
        """
        SELECT id, name, report_date, completed_tasks, in_progress_tasks, next_plans
        FROM projects
        WHERE member_id = ?
        """,
        (member_id,),
    ).fetchall()
    latest = {}
    for row in rows:
        name = str(row["name"] or "").strip()
        if name in SYNTHETIC_PROJECTS:
            continue
        stamp = (str(row["report_date"] or ""), int(row["id"]))
        prev = latest.get(name)
        if prev is None or stamp > prev[0]:
            latest[name] = (stamp, row)
    return latest


def progress_projects(conn, member_id: int) -> list[dict]:
    latest_daily = _latest_daily_by_project(conn, member_id)
    records = conn.execute(
        """
        SELECT * FROM work_records
        WHERE member_id = ? AND TRIM(project_name) != ''
        """,
        (member_id,),
    ).fetchall()
    grouped = {}
    for row in records:
        name = str(row["project_name"] or "").strip()
        if name in SYNTHETIC_PROJECTS:
            continue
        grouped.setdefault(name, []).append(row)

    items = []
    for name in set(latest_daily) | set(grouped):
        daily_row = latest_daily.get(name, (None, None))[1]
        recs = grouped.get(name, [])
        sales = [row for row in recs if row["kind"] == "sales"]
        meetings = [row for row in recs if row["kind"] == "meeting"]
        latest_sales = max(
            sales,
            key=lambda row: (str(row["report_date"] or ""), int(row["id"])),
            default=None,
        )
        latest_meeting = max(
            meetings,
            key=lambda row: (str(row["report_date"] or ""), int(row["id"])),
            default=None,
        )
        in_progress = _json_list(daily_row["in_progress_tasks"]) if daily_row else []
        next_plans = _json_list(daily_row["next_plans"]) if daily_row else []
        sales_details = _details(latest_sales)
        meeting_details = _details(latest_meeting)
        followups = [
            item
            for item in meeting_details.get("followups") or []
            if isinstance(item, dict) and str(item.get("task") or "").strip()
        ]
        progress = str(sales_details.get("progress") or "").strip()
        sales_next = str(sales_details.get("nextSteps") or "").strip()
        if not (in_progress or next_plans or progress or sales_next or followups):
            continue
        status_candidates = []
        if daily_row is not None and (in_progress or next_plans):
            status_candidates.append(
                (str(daily_row["report_date"] or ""), in_progress[0] if in_progress else next_plans[0])
            )
        if latest_sales is not None and (progress or sales_next):
            status_candidates.append(
                (str(latest_sales["report_date"] or ""), progress or sales_next)
            )
        if latest_meeting is not None and followups:
            status_candidates.append(
                (str(latest_meeting["report_date"] or ""), followups[0]["task"])
            )
        status_candidates.sort(key=lambda item: item[0], reverse=True)
        line = status_candidates[0][1]
        dates = []
        if daily_row is not None and daily_row["report_date"]:
            dates.append(str(daily_row["report_date"]))
        if latest_sales is not None:
            dates.append(str(latest_sales["report_date"]))
        if latest_meeting is not None:
            dates.append(str(latest_meeting["report_date"]))
        items.append(
            {
                "name": name,
                "statusLine": _clip(line),
                "lastActive": max(dates) if dates else "",
            }
        )
    items.sort(key=lambda item: (item["lastActive"], item["name"]), reverse=True)
    return items


def _weekly_title(raw) -> str:
    try:
        days = json.loads(raw or "[]")
    except json.JSONDecodeError:
        days = []
    if not isinstance(days, list):
        days = []
    start = week_start_of([str(day) for day in days])
    if start:
        return f"주간보고 ({start} 주)"
    return "주간보고"


def last_activity(conn, member_id: int):
    candidates = []
    daily = conn.execute(
        """
        SELECT id, report_date, created_at
        FROM daily_reports
        WHERE member_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (member_id,),
    ).fetchone()
    if daily is not None:
        project = conn.execute(
            """
            SELECT name FROM projects
            WHERE member_id = ? AND report_date = ? AND TRIM(name) != ''
            ORDER BY id
            LIMIT 1
            """,
            (member_id, daily["report_date"]),
        ).fetchone()
        project_name = ""
        if project is not None:
            project_name = str(project["name"] or "").strip()
        title = project_name if project_name not in SYNTHETIC_PROJECTS else "일일보고"
        candidates.append(
            (
                _stamp(daily["created_at"], daily["report_date"]),
                {
                    "kind": "daily",
                    "kindLabel": KIND_LABELS["daily"],
                    "title": title,
                    "date": daily["report_date"],
                    "at": daily["created_at"],
                    "href": f"/report-result/{daily['id']}",
                },
            )
        )
    weekly = conn.execute(
        """
        SELECT id, selected_date, created_at
        FROM weekly_reports
        WHERE member_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (member_id,),
    ).fetchone()
    if weekly is not None:
        candidates.append(
            (
                _stamp(weekly["created_at"], ""),
                {
                    "kind": "weekly",
                    "kindLabel": KIND_LABELS["weekly"],
                    "title": _weekly_title(weekly["selected_date"]),
                    "date": "",
                    "at": weekly["created_at"],
                    "href": f"/weekly-detail/{weekly['id']}",
                },
            )
        )
    work = conn.execute(
        """
        SELECT id, kind, title, report_date, updated_at
        FROM work_records
        WHERE member_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (member_id,),
    ).fetchone()
    if work is not None:
        candidates.append(
            (
                _stamp(work["updated_at"], work["report_date"]),
                {
                    "kind": work["kind"],
                    "kindLabel": KIND_LABELS.get(work["kind"], work["kind"]),
                    "title": work["title"],
                    "date": work["report_date"],
                    "at": work["updated_at"],
                    "href": f"/compose/{work['id']}",
                },
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def project_names_for_member(conn, member_id: int) -> list[str]:
    names = set()
    for row in conn.execute(
        "SELECT DISTINCT name FROM projects WHERE member_id = ?",
        (member_id,),
    ):
        name = str(row["name"] or "").strip()
        if name not in SYNTHETIC_PROJECTS:
            names.add(name)
    for row in conn.execute(
        """
        SELECT DISTINCT project_name FROM work_records
        WHERE member_id = ? AND TRIM(project_name) != ''
        """,
        (member_id,),
    ):
        name = str(row["project_name"] or "").strip()
        if name not in SYNTHETIC_PROJECTS:
            names.add(name)
    return sorted(names, key=lambda item: item.casefold())


def _history_lines_daily(row) -> list[str]:
    lines = []
    for label, column in (
        ("완료", "completed_tasks"),
        ("진행", "in_progress_tasks"),
        ("다음", "next_plans"),
    ):
        for text in _json_list(row[column])[:3]:
            lines.append(f"{label}: {text}")
    return lines[:6]


def project_history(conn, member_id: int, project_name: str) -> list[dict]:
    name = project_name.strip()
    if not name:
        return []
    items = []
    rows = conn.execute(
        """
        SELECT p.id, p.report_date, p.completed_tasks, p.in_progress_tasks, p.next_plans,
               d.id AS report_id, d.created_at
        FROM projects p
        LEFT JOIN daily_reports d
          ON d.member_id = p.member_id AND d.report_date = p.report_date
        WHERE p.member_id = ? AND p.name = ?
        ORDER BY p.report_date DESC, p.id DESC
        """,
        (member_id, name),
    ).fetchall()
    seen_days = set()
    for row in rows:
        day = str(row["report_date"] or "")
        if day in seen_days:
            continue
        seen_days.add(day)
        report_id = row["report_id"]
        items.append(
            {
                "key": f"daily-{row['id']}",
                "kind": "daily",
                "kindLabel": KIND_LABELS["daily"],
                "date": day,
                "at": row["created_at"] or "",
                "title": name,
                "lines": _history_lines_daily(row),
                "href": f"/report-result/{report_id}" if report_id else "/reports",
                "id": report_id or row["id"],
            }
        )
    records = conn.execute(
        """
        SELECT * FROM work_records
        WHERE member_id = ? AND project_name = ?
        ORDER BY report_date DESC, id DESC
        """,
        (member_id, name),
    ).fetchall()
    for row in records:
        details = _details(row)
        lines = []
        if row["kind"] == "meeting":
            if details.get("decisions"):
                lines.append(f"결정: {details['decisions']}")
            for follow in details.get("followups") or []:
                if isinstance(follow, dict) and follow.get("task"):
                    who = follow.get("owner") or ""
                    due = follow.get("due") or ""
                    extra = " · ".join(part for part in (who, due) if part)
                    suffix = f" ({extra})" if extra else ""
                    lines.append(f"후속: {follow['task']}{suffix}")
        elif row["kind"] == "sales":
            if details.get("progress"):
                lines.append(f"진행: {details['progress']}")
            if details.get("nextSteps"):
                lines.append(f"추후: {details['nextSteps']}")
            if details.get("contactName"):
                lines.append(f"담당: {details['contactName']}")
        elif row["body"]:
            lines.append(row["body"])
        items.append(
            {
                "key": f"work-{row['id']}",
                "kind": row["kind"],
                "kindLabel": KIND_LABELS.get(row["kind"], row["kind"]),
                "date": row["report_date"],
                "at": row["updated_at"] or "",
                "title": row["title"],
                "lines": [_clip(line, 240) for line in lines[:6]],
                "href": f"/compose/{row['id']}",
                "id": row["id"],
            }
        )
    items.sort(
        key=lambda item: (str(item["date"] or ""), str(item["at"] or ""), item["key"]),
        reverse=True,
    )
    return items


def build_dashboard(conn, member_id: int, project: str = "") -> dict:
    selected = str(project or "").strip()
    return {
        "projects": progress_projects(conn, member_id),
        "lastActivity": last_activity(conn, member_id),
        "projectNames": project_names_for_member(conn, member_id),
        "selectedProject": selected,
        "history": project_history(conn, member_id, selected) if selected else [],
    }
