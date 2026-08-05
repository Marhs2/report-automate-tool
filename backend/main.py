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


def get_known_projects_block():
    """DB의 known_projects/aliases로 {{KNOWN_PROJECTS}} 슬롯을 채운다.

    prompt.txt 의 [C0] 등록된 프로젝트 목록 형식과 맞춘다.
    등록된 프로젝트가 없으면 빈 문장을 돌려주고, 사용자는 원문에서 직접 판단한다.
    """
    with get_db() as conn:
        registered = conn.execute(
            "SELECT name FROM known_projects WHERE TRIM(name) != ''"
        ).fetchall()
        rows = conn.execute(
            "SELECT DISTINCT name FROM projects WHERE name IS NOT NULL AND TRIM(name) != ''"
        ).fetchall()
        aliases = conn.execute(
            "SELECT alias_name, canonical_name FROM project_aliases"
        ).fetchall()
    names = sorted({r[0] for r in registered} | {r[0] for r in rows})
    if not names:
        return "(등록된 프로젝트가 없다. 원문에서 직접 판단한다.)"
    alias_by = {}
    for alias, canon in aliases:
        alias_by.setdefault(canon, []).append(alias)
    lines = []
    for name in names:
        lines.append(f"- {name}")
        if name in alias_by:
            lines.append(f"  · 표기 변형: {', '.join(alias_by[name])}")
    return "\n".join(lines)


def load_daily_prompt():
    """daily_prompt 을 읽되 {{KNOWN_PROJECTS}} 슬롯을 DB에서 채워 반환한다."""
    with open("./model_asset/prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read()
    return prompt.replace("{{KNOWN_PROJECTS}}", get_known_projects_block())


def load_weekly_prompt():
    """weekly_prompt 를 읽되 {{KNOWN_PROJECTS}} 슬롯을 DB에서 채워 반환한다.

    주간 프롬프트는 [B. projectName 표기 변형 통일] 에서 [등록 프로젝트] 목록을
    참조하므로 daily 와 동일한 방식으로 주입한다. 등록된 프로젝트가 없으면
    "원문 그대로 사용" 규칙(B3)만 적용된다.
    """
    with open("./model_asset/weekly_prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read()
    return prompt.replace("{{KNOWN_PROJECTS}}", get_known_projects_block())


with open("./model_asset/weekly_json_schema.json", "r", encoding="utf-8") as f:
    weekly_schema = json.load(f)

MODEL_NAME = os.environ.get("REPORT_MODEL_NAME", "qwen3.5-4b-mtp@q4_k_m")
LM_BASE_URL = os.environ.get("LM_BASE_URL", "http://127.0.0.1:1234/v1")
LM_API_KEY = os.environ.get("LM_API_KEY", "lm-studio")
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "600"))

DAILY_MAX_TOKENS = int(os.environ.get("DAILY_MAX_TOKENS", "16384"))
WEEKLY_MAX_TOKENS = int(os.environ.get("WEEKLY_MAX_TOKENS", "16384"))
_daily_reasoning = (os.environ.get("DAILY_REASONING") or "none").lower()
DAILY_REASONING = (
    _daily_reasoning if _daily_reasoning in {"low", "medium", "high", "none"} else None
)
_weekly_reasoning = (os.environ.get("WEEKLY_REASONING") or "none").lower()
WEEKLY_REASONING = (
    _weekly_reasoning
    if _weekly_reasoning in {"low", "medium", "high", "none"}
    else None
)

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


class AliasRequest(BaseModel):
    alias_name: str
    canonical_name: str


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


def read_completion(completion, label):
    """LLM 응답 본문을 꺼내면서 상한 초과로 잘렸는지 확인한다."""
    choice = completion.choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    usage = getattr(completion, "usage", None)
    out_tokens = getattr(usage, "completion_tokens", None) if usage else None
    print(f"[{label}] finish_reason={finish_reason} completion_tokens={out_tokens}")

    if finish_reason == "length":
        raise HTTPException(
            status_code=502,
            detail=(
                "AI 모델이 출력 상한까지 생성해 결과가 잘렸습니다. "
                "원문이 길면 나눠서 추출하거나, 같은 내용이 반복 생성되는지 확인해주세요. "
                "원문은 보존되어 있습니다."
            ),
        )

    return choice.message.content


def get_alias_map():
    """DB의 project_aliases 테이블에서 별칭→대표이름 매핑을 가져온다."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT alias_name, canonical_name FROM project_aliases"
        ).fetchall()
    return {row[0]: row[1] for row in rows}


def guess_project(project, alias_map=None):
    """프로젝트명을 정규화한다. alias_map이 없으면 DB에서 가져온다."""
    if alias_map is None:
        alias_map = get_alias_map()

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

    # 2. 원래 프로젝트명
    project_name = project.get("projectName") or "미분류 프로젝트"

    # 3. PROJECT_FIX (코드 내 이름 매핑)
    project_name = PROJECT_FIX.get(project_name, project_name)

    # 4. DB 별칭 매핑 (사용자 등록)
    project_name = alias_map.get(project_name, project_name)

    return project_name


def normalize_projects(report_data):
    alias_map = get_alias_map()

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

        project_name = guess_project(project, alias_map)
        project_name = PROJECT_FIX.get(project_name, project_name)
        project_name = alias_map.get(project_name, project_name)

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


def _weekly_project_key(project, alias_map):
    return str(guess_project(project, alias_map)).strip().casefold()


def promote_weekly_tasks(report_data, source_reports=None, alias_map=None):
    """Remove stale weekly statuses using the daily completed-task history."""
    alias_map = alias_map or {}
    completed_by_project = defaultdict(list)

    for daily_report in source_reports or []:
        for project in daily_report.get("projects", []):
            if isinstance(project, dict):
                completed_by_project[_weekly_project_key(project, alias_map)].extend(
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
            _weekly_project_key(project, alias_map), []
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
    alias_map = get_alias_map()
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
            project_canonical = guess_project(project, alias_map)
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


# ─── 프로젝트 별칭 관리 ─────────────────────────────────────────────


@app.get("/project-aliases")
def get_project_aliases():
    """등록된 모든 별칭 조회."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, alias_name, canonical_name, created_at FROM project_aliases ORDER BY canonical_name, alias_name"
        ).fetchall()
    return [
        {
            "id": row[0],
            "alias_name": row[1],
            "canonical_name": row[2],
            "created_at": row[3],
        }
        for row in rows
    ]


@app.post("/project-aliases")
def create_project_alias(data: AliasRequest):
    """새 별칭 등록. 같은 alias_name이 이미 있으면 409."""
    alias = data.alias_name.strip()
    canonical = data.canonical_name.strip()
    if not alias or not canonical:
        raise HTTPException(
            status_code=400, detail="별칭과 대표 이름을 모두 입력해주세요."
        )
    if alias == canonical:
        raise HTTPException(status_code=400, detail="별칭과 대표 이름이 같습니다.")
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO project_aliases (alias_name, canonical_name) VALUES (?, ?)",
                (alias, canonical),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=409, detail=f"'{alias}' 별칭이 이미 등록되어 있습니다."
            )
    return {"message": f"'{alias}' → '{canonical}' 별칭이 등록되었습니다."}


@app.delete("/project-aliases/{alias_id}")
def delete_project_alias(alias_id: int):
    """별칭 삭제."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_aliases WHERE id = ?", (alias_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="해당 별칭을 찾을 수 없습니다.")
        conn.commit()
    return {"message": "별칭이 삭제되었습니다."}


# ─── 프로젝트 명 관리 ──────────────────────────────────────────────


@app.get("/project-names")
def get_project_names():
    """모든 보고서에서 등장한 고유 프로젝트명 목록 (정규화 적용).

    등록된 프로젝트 명(known_projects)도 함께 포함한다.
    """
    alias_map = get_alias_map()
    with get_db() as conn:
        rows = conn.execute("SELECT parsed_json FROM daily_reports").fetchall()
        registered = conn.execute(
            "SELECT name FROM known_projects WHERE TRIM(name) != ''"
        ).fetchall()

    names = set()
    for row in rows:
        parsed = coerce_report_data(row[0])
        for project in parsed.get("projects", []):
            canonical = guess_project(project, alias_map)
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
        try:
            client = OpenAI(
                base_url=LM_BASE_URL,
                api_key=LM_API_KEY,
                timeout=LLM_TIMEOUT_SECONDS,
            )
            kwargs = dict(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": load_weekly_prompt()},
                    {"role": "user", "content": json.dumps(reports)},
                ],
                temperature=0.1,
                max_tokens=WEEKLY_MAX_TOKENS,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "weekly_report",
                        "strict": True,
                        "schema": weekly_schema,
                    },
                },
            )
            if WEEKLY_REASONING:
                kwargs["reasoning_effort"] = WEEKLY_REASONING
            completion = client.chat.completions.create(**kwargs)

            report_data = normalize_projects(
                coerce_report_data(
                    read_completion(completion, "weekly-report"),
                    strict=True,
                )
            )
            report_data = promote_weekly_tasks(
                report_data,
                reports,
                get_alias_map(),
            )
        except HTTPException:
            raise
        except Exception as exc:
            print(f"[weekly-report] error: {exc}")
            raise HTTPException(
                status_code=502,
                detail=f"로컬 AI 모델 호출 실패: {exc}",
            )
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
        # DAILY_REASONING: "none"이면 명시적으로 reasoning_effort=none 을 보내 추론을 끈다.
        # (LM Studio/qwen3.5-4b 는 필드를 생략하면 기본으로 추론을 켠다)
        if DAILY_REASONING:
            kwargs["reasoning_effort"] = DAILY_REASONING
        completion = client.chat.completions.create(**kwargs)

        content = read_completion(completion, "send-report")
        report_data = coerce_report_data(content, strict=True)

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
            SELECT report_date, member_id, COUNT(DISTINCT report_date)
            FROM daily_reports
            WHERE report_date BETWEEN ? AND ?
            GROUP BY report_date, member_id
        """,
            (start_date, end_date),
        )

        counts = defaultdict(dict)
        for report_date, member_id, count in cursor.fetchall():
            counts[member_id][report_date] = count

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

        result.append({"member_id": member_id, "name": name, "activities": activities})
    return result


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
