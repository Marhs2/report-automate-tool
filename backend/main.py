import json
import os
import re
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import urlparse

from db import get_db
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

with open("./model_asset/json_Schema.json", "r", encoding="utf-8") as f:
    daily_schema = json.load(f)


def split_project_keywords(raw):
    """known_projects.keywords 문자열을 표기 변형 목록으로 나눈다."""
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[,，|/]", str(raw)) if part.strip()]


def get_known_project_rows():
    """등록된 프로젝트 (name, keywords) 목록."""
    with get_db() as conn:
        return conn.execute(
            "SELECT name, keywords FROM known_projects WHERE TRIM(name) != ''"
        ).fetchall()


def get_project_name_map():
    """known_projects의 이름·키워드 → 대표 프로젝트명 매핑."""
    mapping = {}
    for name, keywords in get_known_project_rows():
        mapping[name] = name
        for keyword in split_project_keywords(keywords):
            mapping[keyword] = name
    return mapping


def get_known_projects_block():
    """DB의 known_projects로 {{KNOWN_PROJECTS}} 슬롯을 채운다.

    prompt.txt 의 [C0] 등록된 프로젝트 목록 형식과 맞춘다.
    등록된 프로젝트가 없으면 빈 문장을 돌려주고, 사용자는 원문에서 직접 판단한다.
    """
    registered = get_known_project_rows()
    keywords_by_name = {
        name: split_project_keywords(keywords) for name, keywords in registered
    }
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT name FROM projects WHERE name IS NOT NULL AND TRIM(name) != ''"
        ).fetchall()
    names = sorted({name for name, _ in registered} | {r[0] for r in rows})
    if not names:
        return "(없음. 이 목록은 선택 사항이다. 원문·입력 JSON의 프로젝트명을 그대로 쓴다.)"
    lines = []
    for name in names:
        lines.append(f"- {name}")
        variants = keywords_by_name.get(name) or []
        if variants:
            lines.append(f"  · 표기 변형: {', '.join(variants)}")
    return "\n".join(lines)


def load_daily_prompt():
    """daily_prompt 을 읽되 {{KNOWN_PROJECTS}} 슬롯을 DB에서 채워 반환한다."""
    with open("./model_asset/prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read()
    return prompt.replace("{{KNOWN_PROJECTS}}", get_known_projects_block())


def load_weekly_prompt():
    """weekly_prompt 를 읽는다. known_projects 목록은 주입하지 않는다."""
    with open("./model_asset/weekly_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()


with open("./model_asset/weekly_json_schema.json", "r", encoding="utf-8") as f:
    weekly_schema = json.load(f)

# LM Studio MLX structured output은 uniqueItems·길이 제한 키를 지원하지 않는다.
_LLM_SCHEMA_DROP_KEYS = frozenset(
    {
        "$schema",
        "title",
        "description",
        "uniqueItems",
        "minItems",
        "maxItems",
        "minLength",
        "maxLength",
    }
)


def sanitize_llm_schema(node):
    """로컬 모델 structured output용으로 스키마를 단순화한다."""
    if isinstance(node, dict):
        return {
            key: sanitize_llm_schema(value)
            for key, value in node.items()
            if key not in _LLM_SCHEMA_DROP_KEYS
        }
    if isinstance(node, list):
        return [sanitize_llm_schema(item) for item in node]
    return node


daily_llm_schema = sanitize_llm_schema(daily_schema)
weekly_llm_schema = sanitize_llm_schema(weekly_schema)

MODEL_NAME = "qwen/qwen3.5-9b"
LM_BASE_URL = "http://127.0.0.1:1234/v1"
LM_API_KEY = "lm-studio"
LLM_TIMEOUT_SECONDS = 600.0

DAILY_MAX_TOKENS = 16384
WEEKLY_MAX_TOKENS = 16384
DAILY_REASONING = "none"
WEEKLY_REASONING = "none"

if urlparse(LM_BASE_URL).hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise RuntimeError(
        "LM_BASE_URL은 인터넷 차단 환경을 위해 로컬 주소만 사용할 수 있습니다."
    )


class ReportRequest(BaseModel):
    report: str
    date: str
    member_id: int


class UserRequest(BaseModel):
    name: str


class WeeklyReportRequest(BaseModel):
    userId: int
    selects: list[str]


class SaveReportData(BaseModel):
    report: str
    parsed_json: str
    member_id: int
    report_date: str | None = None


class ProjectNameRequest(BaseModel):
    name: str
    keywords: str = ""


class ProjectNameKeywordsRequest(BaseModel):
    keywords: str = ""


class UpdateWeeklyData(BaseModel):
    report_json: str


def validate_report_date(report_date):
    try:
        return date.fromisoformat(report_date).isoformat()
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400, detail="날짜는 YYYY-MM-DD 형식이어야 합니다."
        )


def validate_member(conn, member_id):
    if conn.execute("SELECT 1 FROM members WHERE id = ?", (member_id,)).fetchone():
        return
    raise HTTPException(
        status_code=400,
        detail="유효하지 않은 사용자입니다. 사용자 선택 화면에서 다시 선택해주세요.",
    )


def ensure_runtime_schema():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS report_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL,
                report_date DATE NOT NULL,
                raw_text TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id),
                UNIQUE(member_id, report_date)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS known_projects (
                name TEXT PRIMARY KEY,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                keywords TEXT NOT NULL DEFAULT ''
            )
            """
        )
        known_columns = conn.execute("PRAGMA table_info(known_projects)").fetchall()
        if known_columns and not any(
            column["name"] == "keywords" for column in known_columns
        ):
            conn.execute(
                "ALTER TABLE known_projects ADD COLUMN keywords TEXT NOT NULL DEFAULT ''"
            )
        project_columns = conn.execute("PRAGMA table_info(projects)").fetchall()
        if project_columns and not any(
            column["name"] == "report_date" for column in project_columns
        ):
            conn.execute("ALTER TABLE projects ADD COLUMN report_date DATE")
        # 별칭은 known_projects.keywords 로 통합됨
        conn.execute("DROP TABLE IF EXISTS project_aliases")
        conn.commit()


ensure_runtime_schema()


PROJECT_FIX = {
    "기술보증기금": "이노비즈 인증",
    "대한전선": "경영지원",
    "우리은행": "경영지원",
    "세방전지": "경영지원",
    "홈페이지": "경영지원",
    "BC": "경영지원",
    "DC": "경영지원",
    "TC": "경영지원",
}

KEYWORD_FIX = {
    "기술보증기금": "이노비즈 인증",
    "이노비즈": "이노비즈 인증",
    "대한전선": "경영지원",
    "우리은행": "경영지원",
    "세방전지": "경영지원",
    "서울디지텍고": "서울디지텍고 3자협약",
    "산업체 방문조사카드": "서울디지텍고 3자협약",
    "선도기업신청서": "서울디지텍고 3자협약",
    "직무분석": "서울디지텍고 3자협약",
    "AI자율제조": "AI자율제조",
    "RCMS": "AI자율제조",
    "OCR": "Yak-Map",
    "약품": "Yak-Map",
    "복약": "Yak-Map",
    "여우비": "여우비",
}


def coerce_report_data(content, *, strict=False):
    """LLM/DB 응답을 안전하게 파싱한다.

    DB에 이중 인코딩(JSON 문자열이 다시 JSON 문자열로 감싸진)으로 저장된
    parsed_json 이 있을 수 있어, 문자열이 나오면 dict 가 나올 때까지 한 번 더
    파싱한다.
    """

    def fail(message):
        if strict:
            raise ValueError(message)
        print(f"[coerce_report_data] {message}")
        return {"projects": []}

    if not content or not str(content).strip():
        return fail("응답 내용이 비어 있습니다.")
    data = content
    for _ in range(3):
        if not isinstance(data, str):
            break
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return fail(f"JSON 파싱 실패: {str(content)[:200]}")
    if not isinstance(data, dict):
        return fail(f"dict 아님: {type(data)}")
    projects = data.get("projects")
    if not isinstance(projects, list):
        if strict:
            raise ValueError("projects 배열이 없습니다.")
        print(f"[coerce_report_data] projects 누락 또는 배열 아님: {projects!r}")
        data["projects"] = []
        return data
    data["projects"] = [
        p for p in projects if isinstance(p, dict) and p.get("projectName")
    ]
    return data


def project_has_content(project):
    """완료/진행/이슈/요청/계획 중 하나라도 있으면 True."""
    if not isinstance(project, dict):
        return False
    for key in (
        "completedTasks",
        "inProgressTasks",
        "requests",
        "nextPlans",
        "nextWeekPlans",
    ):
        items = project.get(key) or []
        if isinstance(items, list) and any(
            str(item).strip() for item in items if item is not None
        ):
            return True
    issues = project.get("issues") or []
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict) and str(issue.get("content") or "").strip():
                return True
            if isinstance(issue, str) and issue.strip():
                return True
    return False


def drop_empty_projects(report_data):
    """업무 배열이 모두 비어 있는 프로젝트는 화면/저장에서 제외한다."""
    if not isinstance(report_data, dict):
        return {"projects": []}
    projects = report_data.get("projects") or []
    report_data["projects"] = [
        p for p in projects if isinstance(p, dict) and project_has_content(p)
    ]
    return report_data


def read_completion(completion, label):
    """LLM 응답 본문을 꺼내면서 상한 초과로 잘렸는지 확인한다."""
    choice = completion.choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    usage = getattr(completion, "usage", None)
    out_tokens = getattr(usage, "completion_tokens", None) if usage else None
    content = choice.message.content
    print(
        f"[{label}] finish_reason={finish_reason} "
        f"completion_tokens={out_tokens} content_preview={str(content)[:120]!r}"
    )

    if finish_reason == "length":
        raise HTTPException(
            status_code=502,
            detail=(
                "AI 모델이 출력 상한까지 생성해 결과가 잘렸습니다. "
                "원문이 길면 나눠서 추출하거나, 같은 내용이 반복 생성되는지 확인해주세요. "
                "원문은 보존되어 있습니다."
            ),
        )

    return content


def guess_project(project, name_map=None):
    """프로젝트명을 정규화한다. name_map이 없으면 known_projects에서 가져온다."""
    if name_map is None:
        name_map = get_project_name_map()

    issues = [
        issue.get("content", "") if isinstance(issue, dict) else str(issue)
        for issue in project.get("issues", [])
    ]

    text = " ".join(
        [str(t) for t in project.get("completedTasks", [])]
        + [str(t) for t in project.get("inProgressTasks", [])]
        + issues
        + [str(t) for t in project.get("requests", [])]
        + [str(t) for t in project.get("nextPlans", project.get("nextWeekPlans", []))]
    )

    # 1. KEYWORD_FIX (코드 내 키워드 매핑)
    for keyword, target in KEYWORD_FIX.items():
        if keyword in text:
            return target

    # 2. known_projects 키워드가 본문에 있으면 대표명으로 매핑
    for keyword, target in name_map.items():
        if keyword != target and keyword in text:
            return target

    # 3. 원래 프로젝트명
    project_name = project.get("projectName") or "미분류 프로젝트"

    # 4. PROJECT_FIX (코드 내 이름 매핑)
    project_name = PROJECT_FIX.get(project_name, project_name)

    # 5. known_projects 이름·키워드 매핑 (사용자 등록)
    project_name = name_map.get(project_name, project_name)

    return project_name


def normalize_projects(report_data):
    name_map = get_project_name_map()

    merged = defaultdict(
        lambda: {
            "completedTasks": [],
            "inProgressTasks": [],
            "issues": [],
            "requests": [],
            "nextPlans": [],
        }
    )

    for project in report_data.get("projects", []):
        if not isinstance(project, dict):
            continue
        completed_tasks = [
            task
            for task in project.get("completedTasks", [])
            if task and str(task).strip()
        ]
        in_progress_tasks = [
            task
            for task in project.get("inProgressTasks", [])
            if task and str(task).strip()
        ]
        issues_list = [
            issue
            for issue in project.get("issues", [])
            if issue
            and (
                str(issue).strip()
                if not isinstance(issue, dict)
                else any(issue.values())
            )
        ]
        requests_list = [
            req for req in project.get("requests", []) if req and str(req).strip()
        ]
        next_plans_list = [
            plan
            for plan in project.get("nextPlans", project.get("nextWeekPlans", []))
            if plan and str(plan).strip()
        ]

        if not (
            completed_tasks
            or in_progress_tasks
            or issues_list
            or requests_list
            or next_plans_list
        ):
            continue

        project_name = guess_project(project, name_map)
        project_name = PROJECT_FIX.get(project_name, project_name)
        project_name = name_map.get(project_name, project_name)

        merged[project_name]["completedTasks"].extend(completed_tasks)
        merged[project_name]["inProgressTasks"].extend(in_progress_tasks)
        merged[project_name]["issues"].extend(issues_list)
        merged[project_name]["requests"].extend(requests_list)
        merged[project_name]["nextPlans"].extend(next_plans_list)

    result = []

    for name, data in merged.items():
        unique_issues = []
        for issue in data["issues"]:
            if issue not in unique_issues:
                if isinstance(issue, dict):
                    content = issue.get("content", "")
                    status = issue.get("status", "미해결")
                    if content and str(content).strip():
                        unique_issues.append(
                            {"content": str(content).strip(), "status": status}
                        )
                elif str(issue).strip():
                    unique_issues.append(
                        {"content": str(issue).strip(), "status": "미해결"}
                    )

        completed = [
            x for x in list(dict.fromkeys(data["completedTasks"])) if str(x).strip()
        ]
        in_progress = [
            x for x in list(dict.fromkeys(data["inProgressTasks"])) if str(x).strip()
        ]
        requests = [x for x in list(dict.fromkeys(data["requests"])) if str(x).strip()]
        next_plans = [
            x for x in list(dict.fromkeys(data["nextPlans"])) if str(x).strip()
        ]

        if not (completed or in_progress or unique_issues or requests or next_plans):
            continue

        result.append(
            {
                "projectName": name,
                "completedTasks": completed,
                "inProgressTasks": in_progress,
                "issues": unique_issues,
                "requests": requests,
                "nextPlans": next_plans,
            }
        )

    report_data["projects"] = result
    return report_data


_WEEKLY_TASK_MARKERS = (
    "하였습니다",
    "했습니다",
    "진행중",
    "진행 중",
    "했음",
    "완료",
    "예정",
    "착수",
    "시작",
    "중",
)
_WEEKLY_GENERIC_ACTIONS = {
    "개발",
    "구현",
    "검토",
    "설계",
    "수정",
    "처리",
    "작업",
    "업무",
    "확인",
    "테스트",
    "반영",
}


def _weekly_task_tokens(value):
    text = str(value).lower()
    for marker in _WEEKLY_TASK_MARKERS:
        text = text.replace(marker, f" {marker} ")
    for action in _WEEKLY_GENERIC_ACTIONS:
        text = re.sub(
            rf"({re.escape(action)})(?=(완료|중|진행|예정|$|[\s,.!?]))",
            r" \1 ",
            text,
        )
    text = re.sub(r"[^0-9a-z가-힣]+", " ", text)
    ignored = set(_WEEKLY_TASK_MARKERS) | {
        "진행",
        "중",
        "완료",
        "예정",
        "착수",
        "시작",
    }
    return {token for token in text.split() if token and token not in ignored}


def _weekly_tasks_match(left, right):
    left_tokens = _weekly_task_tokens(left)
    right_tokens = _weekly_task_tokens(right)
    common = left_tokens & right_tokens
    if len(common) >= 2:
        return True
    specific_common = common - _WEEKLY_GENERIC_ACTIONS
    return (
        bool(specific_common)
        and len(left_tokens) == 1
        or (bool(specific_common) and len(right_tokens) == 1)
    )


def reported_project_name(project):
    """입력 JSON의 projectName만 쓴다. known_projects 키워드로 본문을 훑지 않는다."""
    if not isinstance(project, dict):
        return "미분류 프로젝트"
    name = str(project.get("projectName") or "").strip()
    return name or "미분류 프로젝트"


def _unique_keep_order(items):
    result = []
    seen = set()
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def merge_daily_reports_to_weekly(reports, name_map=None):
    """여러 일일보고 JSON을 프로젝트별로 합친다.

    문장은 입력에 있는 그대로 복사한다. known_projects 이름·키워드를
    업무 문구로 넣거나, 목록에 없는 프로젝트를 버리지 않는다.
    """
    merged = defaultdict(
        lambda: {
            "completedTasks": [],
            "inProgressTasks": [],
            "issues": [],
            "nextPlans": [],
        }
    )
    order = []
    latest_issue = {}

    for report in reports or []:
        if not isinstance(report, dict):
            continue
        for project in report.get("projects", []):
            if not isinstance(project, dict):
                continue
            name = reported_project_name(project)
            if name not in merged:
                order.append(name)
            bucket = merged[name]
            bucket["completedTasks"].extend(project.get("completedTasks") or [])
            bucket["inProgressTasks"].extend(project.get("inProgressTasks") or [])
            bucket["nextPlans"].extend(project.get("requests") or [])
            bucket["nextPlans"].extend(
                project.get("nextPlans") or project.get("nextWeekPlans") or []
            )
            for issue in project.get("issues") or []:
                if isinstance(issue, dict):
                    content = str(issue.get("content") or "").strip()
                    status = issue.get("status") or "미해결"
                else:
                    content = str(issue).strip()
                    status = "미해결"
                if not content:
                    continue
                latest_issue[(name, content.casefold())] = {
                    "content": content,
                    "status": status,
                }

    projects = []
    for name in order:
        data = merged[name]
        issues = [
            latest_issue[key]
            for key in latest_issue
            if key[0] == name and latest_issue[key]["status"] != "해결"
        ]
        projects.append(
            {
                "projectName": name,
                "completedTasks": _unique_keep_order(data["completedTasks"]),
                "inProgressTasks": _unique_keep_order(data["inProgressTasks"]),
                "issues": issues,
                "requests": [],
                "nextPlans": _unique_keep_order(data["nextPlans"]),
            }
        )

    report_data = {"projects": projects}
    report_data = promote_weekly_tasks(report_data, reports, name_map)
    for project in report_data.get("projects", []):
        completed = project.get("completedTasks") or []
        project["issues"] = [
            issue
            for issue in project.get("issues") or []
            if isinstance(issue, dict)
            and str(issue.get("content") or "").strip()
            and not any(
                _weekly_tasks_match(issue.get("content"), task) for task in completed
            )
        ]
    return drop_empty_projects(report_data)


def _weekly_project_key(project, name_map=None):
    return reported_project_name(project).casefold()


def promote_weekly_tasks(report_data, source_reports=None, name_map=None):
    """Remove stale weekly statuses using the daily completed-task history."""
    name_map = name_map or {}
    completed_by_project = defaultdict(list)

    for daily_report in source_reports or []:
        for project in daily_report.get("projects", []):
            if isinstance(project, dict):
                completed_by_project[_weekly_project_key(project, name_map)].extend(
                    project.get("completedTasks", [])
                )

    for project in report_data.get("projects", []):
        if not isinstance(project, dict):
            continue
        completed = [
            task
            for task in project.get("completedTasks", [])
            if task and str(task).strip()
        ]
        in_progress = [
            task
            for task in project.get("inProgressTasks", [])
            if task and str(task).strip()
        ]
        next_field = "nextPlans" if "nextPlans" in project else "nextWeekPlans"
        next_plans = [
            task for task in project.get(next_field, []) if task and str(task).strip()
        ]

        completed_candidates = completed + completed_by_project.get(
            _weekly_project_key(project, name_map), []
        )
        project["inProgressTasks"] = list(
            dict.fromkeys(
                task
                for task in in_progress
                if not any(
                    _weekly_tasks_match(task, completed_task)
                    for completed_task in completed_candidates
                )
            )
        )
        active_candidates = completed_candidates + project["inProgressTasks"]
        project[next_field] = list(
            dict.fromkeys(
                task
                for task in next_plans
                if not any(
                    _weekly_tasks_match(task, active_task)
                    for active_task in active_candidates
                )
            )
        )

    return report_data


@app.get("/")
def read_root():
    return {"Hello": "World"}


# ─── 프로젝트별 타임라인 조회 ────────────────────────────────────────


@app.get("/project-timeline")
def get_project_timeline(name: str, member_id: int = None):
    """프로젝트명으로 시간순 보고 이력 조회."""
    name_map = get_project_name_map()
    canonical = name.strip()

    with get_db() as conn:
        if member_id:
            rows = conn.execute(
                """
                SELECT d.id, d.member_id, m.name, d.report_date, d.parsed_json
                FROM daily_reports d
                JOIN members m ON m.id = d.member_id
                WHERE d.member_id = ?
                  AND d.id IN (
                      SELECT MAX(id) FROM daily_reports
                      GROUP BY member_id, report_date
                  )
                ORDER BY d.report_date ASC
                """,
                (member_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT d.id, d.member_id, m.name, d.report_date, d.parsed_json
                FROM daily_reports d
                JOIN members m ON m.id = d.member_id
                WHERE d.id IN (
                    SELECT MAX(id) FROM daily_reports
                    GROUP BY member_id, report_date
                )
                ORDER BY d.report_date ASC
                """
            ).fetchall()

    results = []
    for row in rows:
        parsed = coerce_report_data(row[4])
        for project in parsed.get("projects", []):
            project_canonical = guess_project(project, name_map)
            if project_canonical == canonical:
                results.append(
                    {
                        "report_id": row[0],
                        "member_id": row[1],
                        "member_name": row[2],
                        "date": row[3],
                        "completedTasks": project.get("completedTasks", []),
                        "inProgressTasks": project.get("inProgressTasks", []),
                        "issues": project.get("issues", []),
                        "requests": project.get("requests", []),
                        "nextPlans": project.get(
                            "nextPlans", project.get("nextWeekPlans", [])
                        ),
                    }
                )

    return results


# ─── 프로젝트 명 관리 ──────────────────────────────────────────────


@app.get("/project-names")
def get_project_names():
    """모든 보고서에서 등장한 고유 프로젝트명 목록 (정규화 적용).

    등록된 프로젝트 명(known_projects)도 함께 포함한다.
    """
    name_map = get_project_name_map()
    with get_db() as conn:
        rows = conn.execute("SELECT parsed_json FROM daily_reports").fetchall()
        registered = conn.execute(
            "SELECT name FROM known_projects WHERE TRIM(name) != ''"
        ).fetchall()

    names = set()
    for row in rows:
        parsed = coerce_report_data(row[0])
        for project in parsed.get("projects", []):
            canonical = guess_project(project, name_map)
            if canonical:
                names.add(canonical)
    names.update(r[0] for r in registered)

    return sorted(names)


@app.get("/project-names/registered")
def get_registered_project_names():
    """등록된 프로젝트 명 전체 조회."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name, keywords, created_at FROM known_projects ORDER BY name"
        ).fetchall()
    return [
        {"name": row[0], "keywords": row[1] or "", "created_at": row[2]} for row in rows
    ]


@app.post("/project-names")
def create_project_name(data: ProjectNameRequest):
    """새 프로젝트 명 등록. 같은 이름이 이미 있으면 409."""
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="프로젝트 명을 입력해주세요.")
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO known_projects (name, keywords) VALUES (?, ?)",
                (name, data.keywords.strip()),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=409,
                detail=f"'{name}' 프로젝트 명이 이미 등록되어 있습니다.",
            )
    return {"message": f"'{name}' 프로젝트 명이 등록되었습니다."}


@app.delete("/project-names/{project_name}")
def delete_project_name(project_name: str):
    """프로젝트 명 삭제."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM known_projects WHERE name = ?", (project_name,))
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404, detail="해당 프로젝트 명을 찾을 수 없습니다."
            )
        conn.commit()
    return {"message": "프로젝트 명이 삭제되었습니다."}


@app.put("/project-names/{project_name}")
def update_project_name_keywords(project_name: str, data: ProjectNameKeywordsRequest):
    """등록된 프로젝트 명의 키워드 갱신. 없으면 404."""
    keywords = data.keywords.strip()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE known_projects SET keywords = ? WHERE name = ?",
            (keywords, project_name),
        )
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404, detail="해당 프로젝트 명을 찾을 수 없습니다."
            )
        conn.commit()
    return {"message": f"'{project_name}' 키워드가 저장되었습니다."}


def normalize_selected_dates(selects):
    normalized = set()
    for value in selects or []:
        try:
            normalized.add(date.fromisoformat(value).isoformat())
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="기간의 날짜는 YYYY-MM-DD 형식이어야 합니다.",
            )
    if not normalized:
        raise HTTPException(
            status_code=400, detail="기간(날짜)을 최소 1개 선택해주세요."
        )
    return sorted(normalized)


def generate_weekly_report(member_id, selects):
    selects = normalize_selected_dates(selects)
    with get_db() as db:
        res = db.execute(
            """
            SELECT parsed_json FROM daily_reports
            WHERE id IN (
                SELECT MAX(id) FROM daily_reports
                WHERE member_id = ? AND report_date IN ({})
                GROUP BY report_date
            )
            ORDER BY report_date
            """.format(",".join(["?"] * len(selects))),
            (member_id, *selects),
        ).fetchall()

        if not res:
            return None

        reports = [coerce_report_data(row[0]) for row in res]
        report_data = merge_daily_reports_to_weekly(reports)
        # 같은 사람이 같은 기간으로 다시 생성하면 이전 초안을 덮어쓴다. (일일보고와 동일한 덮어쓰기 원칙)
        db.execute(
            "DELETE FROM weekly_reports WHERE member_id = ? AND selected_date = ?",
            (member_id, json.dumps(selects)),
        )
        db.execute(
            "INSERT INTO weekly_reports (member_id, selected_date, report_json) VALUES (?, ?, ?)",
            (member_id, json.dumps(selects), json.dumps(report_data)),
        )
        db.commit()
        return report_data


@app.post("/weekly-report")
def weekly_report(data: WeeklyReportRequest):
    selects = normalize_selected_dates(data.selects)
    report_data = generate_weekly_report(data.userId, selects)
    if report_data is None:
        raise HTTPException(
            status_code=404, detail="선택한 기간에 저장된 일일보고가 없습니다."
        )
    return report_data


@app.post("/send-report")
async def send_report(data: ReportRequest):
    if not data.report.strip():
        raise HTTPException(status_code=400, detail="보고서 내용을 입력해주세요.")
    report_date = validate_report_date(data.date)

    with get_db() as conn:
        validate_member(conn, data.member_id)
        conn.execute(
            """
            INSERT INTO report_drafts (member_id, report_date, raw_text, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(member_id, report_date)
            DO UPDATE SET raw_text = excluded.raw_text,
                          updated_at = CURRENT_TIMESTAMP
            """,
            (data.member_id, report_date, data.report),
        )
        conn.commit()

    client = OpenAI(
        base_url=LM_BASE_URL,
        api_key=LM_API_KEY,
        timeout=LLM_TIMEOUT_SECONDS,
    )
    try:
        max_tokens = DAILY_MAX_TOKENS
        kwargs = dict(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": load_daily_prompt()},
                {"role": "user", "content": data.report},
            ],
            temperature=0.1,
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "daily_report",
                    "strict": True,
                    "schema": daily_schema,
                },
            },
        )
        if DAILY_REASONING:
            kwargs["reasoning_effort"] = DAILY_REASONING
        completion = client.chat.completions.create(**kwargs)

        content = read_completion(completion, "send-report")
        report_data = drop_empty_projects(
            coerce_report_data(content, strict=True)
        )

        # 추출 단계에서는 DB에 쓰지 않는다.
        # 사용자가 화면에서 확인·수정한 뒤 POST /reports 에서 저장한다.
        return report_data
    except HTTPException:
        raise
    except Exception as e:
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            print(f"[send-report] upstream status={resp.status_code} body={detail}")
            raise HTTPException(
                status_code=502,
                detail=f"AI 모델 호출 실패 (status={resp.status_code}). 원문은 보존되어 있으니 재시도해주세요.",
            )
        print(f"[send-report] error: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"AI 모델 호출 실패: {e}. 원문은 보존되어 있으니 재시도해주세요.",
        )


@app.get("/report-drafts/{member_id}/{report_date}")
def get_report_draft(member_id: int, report_date: str):
    report_date = validate_report_date(report_date)
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT raw_text, updated_at
            FROM report_drafts
            WHERE member_id = ? AND report_date = ?
            """,
            (member_id, report_date),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="저장된 원문 초안이 없습니다.")
    return {
        "member_id": member_id,
        "report_date": report_date,
        "raw_text": row[0],
        "updated_at": row[1],
    }


@app.get("/user-activities")
def get_user_activities(
    year: int,
    month: int,
    start_date: str | None = None,
    end_date: str | None = None,
):
    if bool(start_date) != bool(end_date):
        raise HTTPException(
            status_code=400,
            detail="start_date와 end_date를 함께 입력해주세요.",
        )

    if start_date and end_date:
        try:
            first_day = date.fromisoformat(start_date)
            last_day = date.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="날짜는 YYYY-MM-DD 형식이어야 합니다."
            )
        if first_day > last_day:
            raise HTTPException(
                status_code=400, detail="시작일은 종료일보다 늦을 수 없습니다."
            )
    else:
        first_day = date(year, month, 1)
        last_day = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)

    start_date = first_day.isoformat()
    end_date = last_day.isoformat()

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name
            FROM members
            ORDER BY id
        """)
        members = cursor.fetchall()

        cursor.execute(
            """
            SELECT report_date, member_id, COUNT(report_date)
            FROM daily_reports
            WHERE report_date BETWEEN ? AND ?
            GROUP BY report_date, member_id
            """,
            (start_date, end_date),
        )

        counts = defaultdict(dict)
        for report_date, member_id, count in cursor.fetchall():
            counts[member_id][report_date] = count

        cursor.execute(
            """
            SELECT member_id, COUNT(DISTINCT report_date)
            FROM daily_reports
            WHERE report_date BETWEEN ? AND ?
            GROUP BY member_id
            """,
            (start_date, end_date),
        )
        total_counts = {
            member_id: count for member_id, count in cursor.fetchall()
        }

    result = []

    for member_id, name in members:
        activities = []

        current = first_day
        while current <= last_day:
            report_date = current.isoformat()

            activities.append(
                {
                    "report_date": report_date,
                    "count": counts[member_id].get(report_date, 0),
                }
            )

            current += timedelta(days=1)

        result.append(
            {
                "member_id": member_id,
                "name": name,
                "total_count": total_counts.get(member_id, 0),
                "activities": activities,
            }
        )
    return result


@app.delete("/reports/{report_id}")
def delete_report(report_id: int):
    with get_db() as db:
        db.execute(
            """
            DELETE FROM daily_reports
            WHERE id = ?
        """,
            (report_id,),
        )
    return {"message": "Report deleted successfully"}


@app.delete("/weekly/{report_id}")
def delete_weekly_report(report_id: int):
    with get_db() as db:
        db.execute(
            """
            DELETE FROM weekly_reports
            WHERE id = ?
        """,
            (report_id,),
        )
    return {"message": "Report deleted successfully"}


@app.get("/weekly/{user_id}")
def get_weekly(user_id: int):
    with get_db() as db:
        rows = db.execute(
            """
            SELECT w.id, w.member_id, m.name, w.selected_date, w.report_json, w.created_at
            FROM weekly_reports w
            LEFT JOIN members m ON w.member_id = m.id
            WHERE w.member_id = ?
        """,
            (user_id,),
        ).fetchall()

    return [
        {
            "id": row[0],
            "memberId": row[1],
            "memberName": row[2],
            "selectedDate": json.loads(row[3]),
            "report": json.loads(row[4]),
            "createdAt": row[5],
        }
        for row in rows
    ]


@app.get("/weeklyById/{weekly_id}")
def get_weekly_by_id(weekly_id: int):
    with get_db() as db:
        row = db.execute(
            """
            SELECT w.id, w.member_id, m.name, w.selected_date, w.report_json, w.created_at
            FROM weekly_reports w
            LEFT JOIN members m ON w.member_id = m.id
            WHERE w.id = ?
        """,
            (weekly_id,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Weekly report not found")

    return {
        "id": row[0],
        "memberId": row[1],
        "memberName": row[2],
        "selectedDate": json.loads(row[3]),
        "report": json.loads(row[4]),
        "createdAt": row[5],
    }


@app.put("/weekly/{weekly_id}")
def update_weekly(weekly_id: int, data: UpdateWeeklyData):
    """주간보고 초안을 사용자가 수정한 내용으로 갱신한다."""
    try:
        report_data = json.loads(data.report_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="유효한 JSON이 아닙니다.")
    if not isinstance(report_data, dict):
        raise HTTPException(
            status_code=400, detail="주간 보고서 데이터가 유효하지 않습니다."
        )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE weekly_reports SET report_json = ? WHERE id = ?",
            (json.dumps(report_data), weekly_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Weekly report not found")
        conn.commit()

    return {"message": "주간 보고서가 수정되었습니다."}


@app.get("/reports")
def get_reports():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                d.id,
                d.member_id,
                m.name AS member_name,
                d.report_date,
                d.raw_text,
                d.parsed_json,
                d.created_at
            FROM daily_reports d
            JOIN members m
                ON m.id = d.member_id
            WHERE d.id IN (
                SELECT MAX(id)
                FROM daily_reports
                GROUP BY member_id, report_date
            )
            ORDER BY d.report_date DESC, d.member_id ASC
            """
        )
        rows = cursor.fetchall()
        reports = []
        for row in rows:
            parsed = json.loads(row[5]) if row[5] else None
            if parsed:
                parsed = normalize_issues(parsed)
            reports.append(
                {
                    "id": row[0],
                    "member_id": row[1],
                    "member_name": row[2],
                    "report_date": row[3],
                    "raw_text": row[4],
                    "parsed_json": parsed,
                    "created_at": row[6],
                }
            )
    return reports


@app.get("/reports/{report_id}")
def get_report_by_id(report_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, member_id, report_date, raw_text, parsed_json, created_at FROM daily_reports WHERE id = ?",
            (report_id,),
        )
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="보고서를 찾을 수 없습니다.")
    parsed = json.loads(row[4]) if row[4] else None
    if parsed:
        parsed = normalize_issues(parsed)
    return {
        "id": row[0],
        "member_id": row[1],
        "report_date": row[2],
        "raw_text": row[3],
        "parsed_json": parsed,
        "created_at": row[5],
    }


@app.get("/projects")
def get_projects():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects")
        rows = cursor.fetchall()
        projects = []
        for row in rows:
            projects.append(
                {
                    "id": row[0],
                    "member_id": row[1],
                    "name": row[2],
                    "completed_tasks": json.loads(row[3]),
                    "in_progress_tasks": json.loads(row[4]),
                    "issues": json.loads(row[5]),
                    "requests": json.loads(row[6]),
                    "next_plans": json.loads(row[7]),
                }
            )
    return projects


@app.get("/projects/{project_id}")
def get_project_by_name(project_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "member_id": row[1],
                "name": row[2],
                "completed_tasks": json.loads(row[3]),
                "in_progress_tasks": json.loads(row[4]),
                "issues": json.loads(row[5]),
                "requests": json.loads(row[6]),
                "next_plans": json.loads(row[7]),
            }
        return None


@app.post("/users")
def save_user(data: UserRequest):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="이름을 입력해주세요.")
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO members (name) VALUES (?)", (name,))
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=409, detail=f"'{name}' 사용자가 이미 존재합니다."
            )
        conn.commit()
    return {"message": "User saved successfully."}


@app.get("/users")
def get_users():
    with get_db() as db:
        users = db.execute("SELECT * FROM members").fetchall()

    return [dict(user) for user in users]


def normalize_issues(report_data):
    if isinstance(report_data, str):
        try:
            report_data = json.loads(report_data)
        except json.JSONDecodeError:
            return report_data
    if not isinstance(report_data, dict):
        return report_data
    for project in report_data.get("projects", []):
        normalized = []
        for issue in project.get("issues", []):
            if isinstance(issue, dict):
                content = issue.get("content", "")
                status = issue.get("status", "미해결")
                if content and str(content).strip():
                    normalized.append(
                        {"content": str(content).strip(), "status": status}
                    )
            elif issue and str(issue).strip():
                normalized.append({"content": str(issue).strip(), "status": "미해결"})
        project["issues"] = normalized
    return report_data


@app.post("/reports")
def save_report(data: SaveReportData):
    parsed = (
        json.loads(data.parsed_json)
        if isinstance(data.parsed_json, str)
        else data.parsed_json
    )
    parsed = normalize_issues(parsed)

    report_date = validate_report_date(data.report_date or date.today().isoformat())
    raw_text = data.report
    member_id = data.member_id

    with get_db() as conn:
        validate_member(conn, member_id)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM daily_reports WHERE member_id = ? AND report_date = ?",
            (member_id, report_date),
        )
        cursor.execute(
            """
            INSERT INTO daily_reports (member_id, report_date, raw_text, parsed_json)
            VALUES (?, ?, ?, ?)
            """,
            (member_id, report_date, raw_text, json.dumps(parsed)),
        )

        cursor.execute(
            "DELETE FROM projects WHERE member_id = ? AND report_date = ?",
            (member_id, report_date),
        )
        save_projects(conn, parsed, member_id, report_date)
        conn.commit()
    return {"message": "Report saved successfully.", "report_date": report_date}


def save_projects(conn, report_data, member_id, report_date):
    cursor = conn.cursor()

    for project in report_data.get("projects", []):
        if not isinstance(project, dict):
            continue
        cursor.execute(
            """
            INSERT INTO projects (
                member_id,
                name,
                completed_tasks,
                in_progress_tasks,
                issues,
                requests,
                next_plans,
                report_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                member_id,
                project.get("projectName") or "미분류 프로젝트",
                json.dumps(project.get("completedTasks", [])),
                json.dumps(project.get("inProgressTasks", [])),
                json.dumps(project.get("issues", [])),
                json.dumps(project.get("requests", [])),
                json.dumps(project.get("nextPlans", [])),
                report_date,
            ),
        )
