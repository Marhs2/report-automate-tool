from __future__ import annotations

import re
from datetime import date, timedelta

SCHEMA = "weekly-deck-v1"


def _as_date(value) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _md(day: date) -> str:
    return f"{day.month}/{day.day}"


def week_labels(selected_dates) -> tuple[str, str]:
    days = sorted({d for d in (_as_date(raw) for raw in selected_dates or []) if d})
    if not days:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        days = [monday, monday + timedelta(days=4)]
    start, end = days[0], days[-1]
    done = _md(start) if start == end else f"{_md(start)}~{_md(end)}"
    return done, next_week_span(end)


def _year_of(value) -> int:
    text = str(value or "").replace(".", "-")
    if len(text) >= 4 and text[:4].isdigit():
        year = int(text[:4])
        if 1900 <= year <= 2100:
            return year
    return date.today().year


def _parse_md_dates(label: str, year: int) -> list[date]:
    days = []
    for month, day in re.findall(r"(\d{1,2})[/.](\d{1,2})", str(label or "")):
        try:
            days.append(date(year, int(month), int(day)))
        except ValueError:
            continue
    return days


def next_week_span(end: date) -> str:
    week_monday = end - timedelta(days=end.weekday())
    next_monday = week_monday + timedelta(days=7)
    return f"{_md(next_monday)}~{_md(next_monday + timedelta(days=4))}"


def week_start_of(selected_dates) -> str:
    """선택한 날짜들이 속한 주의 월요일.

    주간보고는 한 주에 하나다. 월~수로 만들었다가 월~금으로 다시 만들어도 같은 주이므로
    같은 키가 나와야 한다. 날짜가 여러 주에 걸치면 가장 늦은 날짜의 주를 쓴다.
    """
    days = sorted({d for d in (_as_date(raw) for raw in selected_dates or []) if d})
    if not days:
        return ""
    end = days[-1]
    return (end - timedelta(days=end.weekday())).isoformat()


def next_week_label(done_label: str, report_date: str = "") -> str:
    year = _year_of(report_date)
    days = _parse_md_dates(done_label, year)
    if not days:
        parsed = _as_date(str(report_date or "").replace(".", "-")[:10])
        days = [parsed] if parsed else []
    if not days:
        return ""
    return next_week_span(days[-1])


def format_dot_date(value) -> str:
    day = _as_date(value)
    if not day:
        return ""
    return f"{day.year}.{day.month:02d}.{day.day:02d}"


def _item_text(value) -> str:
    if isinstance(value, dict):
        return str(value.get("content") or "").strip()
    return str(value or "").strip()


def _texts(values) -> list[str]:
    out = []
    seen = set()
    for raw in values or []:
        text = _item_text(raw)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def empty_section(title=""):
    return {"title": title, "items": [""]}


def empty_event():
    return {"when": "", "title": ""}


def empty_notice():
    return {"title": "", "body": [""]}


COLLAB_CENTERS = ("AC", "BC", "DC", "TC", "CSC")


def empty_collab():
    return {"supports": [], "done": [""], "next": [""]}


def _as_notices(raw) -> list[dict]:
    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        body = [str(line).strip() for line in item.get("body") or [] if str(line).strip()]
        if title or body:
            out.append({"title": title, "body": body})
    return out


def _as_events(raw) -> list[dict]:
    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        when = str(item.get("when") or "").strip()
        title = str(item.get("title") or "").strip()
        if when or title:
            out.append({"when": when, "title": title})
    return out


def _as_collab(raw) -> dict:
    data = raw if isinstance(raw, dict) else {}
    seen = set()
    supports = []
    for item in data.get("supports") or []:
        code = str(item or "").strip().upper()
        if code in COLLAB_CENTERS and code not in seen:
            seen.add(code)
            supports.append(code)
    return {
        "supports": supports,
        "done": _texts(data.get("done")),
        "next": _texts(data.get("next")),
    }


def section_lines(sections) -> list[str]:
    lines = []
    index = 0
    for section in sections or []:
        title = str(section.get("title") or "").strip()
        items = [str(item).strip() for item in section.get("items") or [] if str(item).strip()]
        if not title and not items:
            continue
        index += 1
        lines.append(f"{index}. {title}" if title else f"{index}.")
        for item in items:
            lines.append(f"   - {item}")
    return lines or ["없음"]


def from_legacy(
    report,
    *,
    selected_dates=None,
    member_name="",
    team_name="",
) -> dict:
    data = dict(report or {})
    if data.get("schema") == SCHEMA and isinstance(data.get("done"), list):
        data["notices"] = _as_notices(data.get("notices"))
        data["month_events"] = _as_events(data.get("month_events"))
        data["next_month_events"] = _as_events(data.get("next_month_events"))
        data["collab"] = _as_collab(data.get("collab"))
        data["director"] = str(data.get("director") or "").strip()
        data.setdefault("next", [])
        if selected_dates:
            done, nxt = week_labels(selected_dates)
            if not data.get("week_label_done"):
                data["week_label_done"] = done
            data["week_label_next"] = nxt
        else:
            nxt = next_week_label(
                str(data.get("week_label_done") or ""),
                str(data.get("report_date") or ""),
            )
            if nxt:
                data["week_label_next"] = nxt
        if member_name and not data.get("author"):
            data["author"] = member_name
        if team_name and not data.get("center"):
            data["center"] = team_name
        return data

    days = sorted({d for d in (_as_date(raw) for raw in selected_dates or []) if d})
    done_label, next_label = week_labels(selected_dates)
    done = []
    nxt = []
    for project in data.get("projects") or []:
        if not isinstance(project, dict):
            continue
        title = str(project.get("projectName") or "").strip()
        done_items = _texts(
            list(project.get("completedTasks") or [])
            + list(project.get("inProgressTasks") or [])
            + list(project.get("issues") or [])
        )
        next_items = _texts(
            project.get("nextWeekPlans") or project.get("nextPlans") or []
        )
        if done_items:
            done.append({"title": title, "items": done_items})
        if next_items:
            nxt.append({"title": title, "items": next_items})
    return {
        "schema": SCHEMA,
        "report_date": format_dot_date(days[-1] if days else date.today()),
        "author": member_name or str(data.get("author") or ""),
        "center": team_name or str(data.get("center") or ""),
        "week_label_done": done_label,
        "week_label_next": next_label,
        "director": str(data.get("director") or "").strip(),
        "notices": _as_notices(data.get("notices")),
        "month_events": _as_events(data.get("month_events")),
        "next_month_events": _as_events(data.get("next_month_events")),
        "collab": _as_collab(data.get("collab")),
        "done": done,
        "next": nxt,
        "projects": data.get("projects") or [],
        "confirmQuestions": data.get("confirmQuestions") or [],
    }


_GENERIC_WORK_TOKENS = {
    "진행",
    "완료",
    "검토",
    "개발",
    "테스트",
    "확인",
    "적용",
    "작업",
    "지원",
    "협의",
    "수정",
}


def _norm_work(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).casefold()


def _work_tokens(text: str) -> set[str]:
    return set(re.findall(r"[0-9a-zA-Z가-힣]{2,}", str(text or "").lower()))


def same_work(left, right) -> bool:
    a, b = _norm_work(left), _norm_work(right)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) >= 10 and shorter in longer:
        return True
    specific = (_work_tokens(left) & _work_tokens(right)) - _GENERIC_WORK_TOKENS
    return len(specific) >= 2


def _title_key(title: str) -> str:
    return (title or "").strip().casefold() or "미분류 프로젝트"


def next_sections_of(report) -> list[dict]:
    if not isinstance(report, dict):
        return []
    if report.get("schema") == SCHEMA and isinstance(report.get("next"), list):
        return [
            {
                "title": str(section.get("title") or "").strip() or "미분류 프로젝트",
                "items": _texts(section.get("items") or []),
            }
            for section in report.get("next") or []
            if _texts(section.get("items") or [])
        ]
    sections = []
    for project in report.get("projects") or []:
        if not isinstance(project, dict):
            continue
        items = _texts(
            project.get("nextWeekPlans") or project.get("nextPlans") or []
        )
        if not items:
            continue
        sections.append(
            {
                "title": str(project.get("projectName") or "").strip()
                or "미분류 프로젝트",
                "items": items,
            }
        )
    return sections


def pick_previous_weekly(candidates, current_dates):
    current_days = [day for day in (_as_date(raw) for raw in current_dates or []) if day]
    if not current_days:
        return None
    current_min = min(current_days)
    best = None
    best_end = None
    for selected, report in candidates or []:
        days = [day for day in (_as_date(raw) for raw in (selected or [])) if day]
        if not days:
            continue
        end = max(days)
        if end >= current_min:
            continue
        if best_end is None or end > best_end:
            best_end = end
            best = report
    return best


def merge_last_week_next(report_data, last_next):
    """Keep last week's 향후 that this week did not close. Unfinished promises stay in nextWeekPlans."""
    report_data = dict(report_data or {})
    projects = [
        project
        for project in (report_data.get("projects") or [])
        if isinstance(project, dict)
    ]
    by_key = {_title_key(project.get("projectName")): project for project in projects}
    carried = 0
    for section in last_next or []:
        title = (
            str(section.get("title") or section.get("projectName") or "").strip()
            or "미분류 프로젝트"
        )
        items = _texts(section.get("items") or [])
        if not items:
            continue
        key = _title_key(title)
        project = by_key.get(key)
        if not project:
            project = {
                "projectName": title,
                "completedTasks": [],
                "inProgressTasks": [],
                "issues": [],
                "nextWeekPlans": [],
            }
            projects.append(project)
            by_key[key] = project
        covered = _texts(
            list(project.get("completedTasks") or [])
            + list(project.get("inProgressTasks") or [])
            + list(project.get("issues") or [])
            + list(project.get("nextWeekPlans") or [])
            + list(project.get("nextPlans") or [])
        )
        current = list(
            dict.fromkeys(
                _texts(
                    project.get("nextWeekPlans")
                    or project.get("nextPlans")
                    or []
                )
            )
        )
        for item in items:
            if any(same_work(item, other) for other in covered):
                continue
            current.append(item)
            covered.append(item)
            carried += 1
        project["nextWeekPlans"] = current
        if "nextPlans" in project:
            project["nextPlans"] = list(current)
    report_data["projects"] = projects
    return report_data, carried


def to_legacy_projects(deck) -> list[dict]:
    by_title = {}
    for section in deck.get("done") or []:
        title = str(section.get("title") or "").strip() or "미분류 프로젝트"
        by_title[title] = {
            "projectName": title,
            "completedTasks": list(section.get("items") or []),
            "inProgressTasks": [],
            "issues": [],
            "nextPlans": [],
            "nextWeekPlans": [],
        }
    for section in deck.get("next") or []:
        title = str(section.get("title") or "").strip() or "미분류 프로젝트"
        row = by_title.get(title) or {
            "projectName": title,
            "completedTasks": [],
            "inProgressTasks": [],
            "issues": [],
            "nextPlans": [],
            "nextWeekPlans": [],
        }
        items = list(section.get("items") or [])
        row["nextPlans"] = items
        row["nextWeekPlans"] = items
        by_title[title] = row
    return list(by_title.values())
