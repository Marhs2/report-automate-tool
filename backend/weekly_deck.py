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
        data["notices"] = []
        data["month_events"] = []
        data["next_month_events"] = []
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
        "notices": [],
        "month_events": [],
        "next_month_events": [],
        "done": done,
        "next": nxt,
        "projects": data.get("projects") or [],
        "confirmQuestions": data.get("confirmQuestions") or [],
    }


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
