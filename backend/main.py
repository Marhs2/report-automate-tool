import io
import json
import os
import re
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import quote, urlparse

from auth import PASSWORD_MIN_LENGTH, hash_password, new_session_token, verify_password
from db import get_db
from init_db import ensure_default_admin
from dotenv import load_dotenv
from kr_holidays import kr_holiday_map
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from openai import OpenAI
from pptx_fill import fill_weekly_pptx
from pptx_to_text import extract_all_text_from_pptx
from weekly_deck import (
    from_legacy,
    merge_last_week_next,
    next_sections_of,
    pick_previous_weekly,
    replace_member_week,
)
from pydantic import BaseModel

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=(
        r"https?://((localhost|127\.0\.0\.1)|"
        r"((10|192\.168)\.\d{1,3}\.\d{1,3})|"
        r"(172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}))(:\d+)?"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

with open("./model_asset/json_Schema.json", "r", encoding="utf-8") as f:
    daily_schema = json.load(f)


def split_project_keywords(raw):
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[,，|/]", str(raw)) if part.strip()]


def get_known_project_rows():
    with get_db() as conn:
        return conn.execute(
            "SELECT name, keywords FROM known_projects WHERE TRIM(name) != ''"
        ).fetchall()


def get_project_name_map():
    mapping = {}
    for name, keywords in get_known_project_rows():
        mapping[name] = name
        for keyword in split_project_keywords(keywords):
            mapping[keyword] = name
    return mapping


def get_known_projects_block():
    """prompt.txt 의 {{KNOWN_PROJECTS}} 슬롯용 텍스트."""
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
    with open("./model_asset/prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read()
    return prompt.replace("{{KNOWN_PROJECTS}}", get_known_projects_block())


def load_weekly_prompt():
    with open("./model_asset/weekly_prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read()
    return prompt.replace("{{KNOWN_PROJECTS}}", get_known_projects_block())


def load_keyword_prompt():
    with open("./model_asset/keyword_prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read()
    return prompt.replace("{{KNOWN_PROJECTS}}", get_known_projects_block())


def load_weekly_confirm_prompt():
    with open("./model_asset/weekly_confirm_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()


with open("./model_asset/weekly_json_schema.json", "r", encoding="utf-8") as f:
    weekly_schema = json.load(f)

with open("./model_asset/keyword_json_schema.json", "r", encoding="utf-8") as f:
    keyword_schema = json.load(f)

MODEL_NAME = os.environ.get("REPORT_MODEL_NAME", "unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL")
LM_BASE_URL = os.environ.get("LM_BASE_URL", "http://127.0.0.1")
LM_API_KEY = os.environ.get("LM_API_KEY", "")
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "600"))

DAILY_MAX_TOKENS = int(os.environ.get("DAILY_MAX_TOKENS", "32768"))
WEEKLY_MAX_TOKENS = int(os.environ.get("WEEKLY_MAX_TOKENS", "32768"))
KEYWORD_MAX_TOKENS = int(os.environ.get("KEYWORD_MAX_TOKENS", "32768"))
DAILY_REASONING = os.environ.get("DAILY_REASONING", "none")
WEEKLY_REASONING = os.environ.get("WEEKLY_REASONING", "none")
KEYWORD_REASONING = os.environ.get("KEYWORD_REASONING", "none")
THINKING_EFFORTS = {"xhigh", "medium", "low"}


def apply_reasoning(kwargs, effort):
    """Match qwen3_report_chat_template.jinja: thinking off unless effort is xhigh|medium|low.

    The stock Qwen template treats unset enable_thinking as xhigh thinking, and
    rejects reasoning_effort=none. This app's .env default is none, so we send
    enable_thinking=false instead of passing "none" through.
    """
    value = (effort or "").strip().lower()
    thinking = value in THINKING_EFFORTS
    extra = dict(kwargs.get("extra_body") or {})
    chat_kwargs = dict(extra.get("chat_template_kwargs") or {})
    chat_kwargs["enable_thinking"] = thinking
    if thinking:
        kwargs["reasoning_effort"] = value
        chat_kwargs["reasoning_effort"] = value
    extra["chat_template_kwargs"] = chat_kwargs
    kwargs["extra_body"] = extra
    return kwargs

def _is_allowed_lm_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        parts = [int(p) for p in hostname.split(".")]
    except ValueError:
        return False
    if len(parts) != 4 or any(p < 0 or p > 255 for p in parts):
        return False
    a, b = parts[0], parts[1]
    if a == 10:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 192 and b == 168:
        return True
    return False


if not _is_allowed_lm_host(urlparse(LM_BASE_URL).hostname):
    raise RuntimeError(
        "LM_BASE_URL은 localhost 또는 사설망(10/172.16-31/192.168) 주소만 사용할 수 있습니다."
    )


class ReportRequest(BaseModel):
    report: str
    date: str
    member_id: int


class ReportDraftRequest(BaseModel):
    """AI를 돌리지 않고 원문만 보관한다. 쓰던 글을 잃지 않고 화면을 떠날 수 있게 한다."""

    report: str
    date: str
    member_id: int


class UserRequest(BaseModel):
    name: str
    team_id: int | None = None
    password: str | None = None


class LoginRequest(BaseModel):
    name: str
    password: str


class TeamRequest(BaseModel):
    team_name: str


class SetTeamData(BaseModel):
    team_id: int
    user_id: int


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


class KeywordRecommendRequest(BaseModel):
    report: str


class UpdateWeeklyData(BaseModel):
    report_json: str


class CreateWeeklyData(BaseModel):
    member_id: int
    selects: list[str]
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


def session_token_from_headers(
    authorization: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None),
) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    if x_session_token and str(x_session_token).strip():
        return str(x_session_token).strip()
    raise HTTPException(status_code=401, detail="로그인해 주세요.")


def current_member_id(token: str = Depends(session_token_from_headers)) -> int:
    """로그인한 사용자를 현재 작성자로 본다."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT member_id FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="로그인이 만료되었습니다.")
        validate_member(conn, row["member_id"])
        return int(row["member_id"])


def require_own_member(actor_id: int, member_id: int, message="자신의 것만 수정할 수 있습니다."):
    if int(actor_id) != int(member_id):
        raise HTTPException(status_code=403, detail=message)


def require_own_or_admin(
    actor_id: int,
    member_id: int,
    message="자신의 것만 수정할 수 있습니다.",
    conn=None,
):
    if int(actor_id) == int(member_id):
        return
    if conn is not None:
        if member_is_admin(conn, actor_id):
            return
        raise HTTPException(status_code=403, detail=message)
    with get_db() as db:
        if member_is_admin(db, actor_id):
            return
    raise HTTPException(status_code=403, detail=message)


def member_is_admin(conn, member_id: int) -> bool:
    row = conn.execute(
        "SELECT is_admin FROM members WHERE id = ?",
        (member_id,),
    ).fetchone()
    if not row:
        return False
    keys = row.keys()
    if "is_admin" not in keys:
        return False
    return bool(row["is_admin"])


def require_admin(conn, actor_id: int):
    if not member_is_admin(conn, actor_id):
        raise HTTPException(status_code=403, detail="관리자만 할 수 있습니다.")


def visible_raw_text(actor_id, owner_id, raw_text):
    """타인 원문은 목록·상세 API에서 빼다. 정리된 항목만 보인다."""
    try:
        if int(actor_id) == int(owner_id):
            return raw_text
    except (TypeError, ValueError):
        pass
    return None


_PLAIN_HEADING = re.compile(
    r"^("
    r"프로젝트\s*명\s*:?|"
    r"\[완료\]|\[진행\]|\[이슈\]|\[내일\]|"
    r"어제\s*:?|오늘\s*:?|막힌\s*것\s*:?|"
    r"\d+\.\s*.+|"
    r"전일\s*계획.*|금일\s*:?|내일\s*:?|"
    r"지시/확인.*|건의\s*:?"
    r")\s*$",
    re.IGNORECASE,
)


def plain_parse_daily(raw_text: str) -> dict:
    """AI 없이 제출할 때 쓴 글을 구조화한다. 서식 제목은 빼는다."""
    items = []
    for line in str(raw_text or "").splitlines():
        text = line.strip().lstrip("-*•").strip()
        if not text or _PLAIN_HEADING.match(text):
            continue
        items.append(text)
    if not items:
        text = str(raw_text or "").strip()
        if text:
            items = [text]
    if not items:
        return {"projects": []}
    return {
        "projects": [
            {
                "projectName": "오늘 보고",
                "completedTasks": items,
                "inProgressTasks": [],
                "issues": [],
                "requests": [],
                "nextPlans": [],
            }
        ]
    }


UNASSIGNED_TEAM_NAME = "미지정"


def get_or_create_unassigned_team(conn):
    row = conn.execute(
        "SELECT id FROM teams WHERE team_name = ?",
        (UNASSIGNED_TEAM_NAME,),
    ).fetchone()
    if row:
        return row["id"]
    try:
        cursor = conn.execute(
            "INSERT INTO teams (team_name) VALUES (?)",
            (UNASSIGNED_TEAM_NAME,),
        )
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        row = conn.execute(
            "SELECT id FROM teams WHERE team_name = ?",
            (UNASSIGNED_TEAM_NAME,),
        ).fetchone()
        if row:
            return row["id"]
        raise


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
        conn.execute("DROP TABLE IF EXISTS project_aliases")
        member_columns = conn.execute("PRAGMA table_info(members)").fetchall()
        if member_columns and not any(
            column["name"] == "password_hash" for column in member_columns
        ):
            conn.execute(
                "ALTER TABLE members ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''"
            )
        if member_columns and not any(
            column["name"] == "is_admin" for column in member_columns
        ):
            conn.execute(
                "ALTER TABLE members ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(
            """
            UPDATE members
            SET is_admin = 1
            WHERE id = (
                SELECT id FROM members
                WHERE IFNULL(password_hash, '') != ''
                ORDER BY id ASC
                LIMIT 1
            )
            AND NOT EXISTS (SELECT 1 FROM members WHERE is_admin = 1)
            """
        )
        created_admin = ensure_default_admin(conn)
        if created_admin:
            print(
                f"기본 관리자 계정: {created_admin['name']} / {created_admin['password']}"
                "  (ADMIN_NAME, ADMIN_PASSWORD 환경변수로 바꿀 수 있습니다)"
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                member_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (member_id) REFERENCES members(id)
            )
            """
        )
        conn.commit()


ensure_runtime_schema()


def coerce_report_data(content, *, strict=False):
    """LLM/DB JSON을 dict로 파싱한다. 이중 인코딩도 풀어본다."""

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
    return normalize_issues(data)


def project_has_content(project):
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


_PROJECT_NAME_ALIASES = {
    "여비규정 개정": "경영지원",
    "여비규정": "경영지원",
}


def merge_aliased_projects(report_data):
    """규정·인증 소제목을 행정 프로젝트로 합친다."""
    if not isinstance(report_data, dict):
        return {"projects": []}
    merged = {}
    order = []
    for project in report_data.get("projects") or []:
        if not isinstance(project, dict):
            continue
        raw = str(project.get("projectName") or "").strip()
        name = _PROJECT_NAME_ALIASES.get(raw, raw) or "미분류 프로젝트"
        project = dict(project)
        project["projectName"] = name
        key = name.casefold()
        if key not in merged:
            merged[key] = project
            order.append(key)
            continue
        target = merged[key]
        for field in (
            "completedTasks",
            "inProgressTasks",
            "issues",
            "requests",
            "nextPlans",
            "nextWeekPlans",
        ):
            if field not in project and field not in target:
                continue
            seen = set()
            items = []
            for item in (target.get(field) or []) + (project.get(field) or []):
                text = str(item if not isinstance(item, dict) else item.get("content") or "").strip()
                marker = json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else text
                if not marker or marker in seen:
                    continue
                seen.add(marker)
                items.append(item)
            if items:
                target[field] = items
    report_data["projects"] = [merged[key] for key in order]
    return report_data


def drop_empty_projects(report_data):
    if not isinstance(report_data, dict):
        return {"projects": []}
    report_data = merge_aliased_projects(report_data)
    projects = report_data.get("projects") or []
    report_data["projects"] = [
        p for p in projects if isinstance(p, dict) and project_has_content(p)
    ]
    return report_data


def read_completion(completion, label):
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

    for keyword, target in name_map.items():
        if keyword != target and keyword in text:
            return target

    project_name = project.get("projectName") or "미분류 프로젝트"
    return name_map.get(project_name, project_name)


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
    "개선",
    "추가",
    "삭제",
    "조회",
    "렌더링",
    "작성",
    "등록",
}
_WEEKLY_GENERIC_NOUNS = {
    "목록",
    "화면",
    "기능",
    "보고서",
    "버그",
    "오류",
    "속도",
    "성능",
    "데이터",
    "모듈",
    "페이지",
    "항목",
    "내용",
    "문제",
    "이슈",
    "요청",
    "회의록",
    "메모리",
    "log",
    "api",
    "ui",
}
_WEEKLY_STOP_TOKENS = {
    "및",
    "외",
    "등",
    "관련",
    "따른",
    "대한",
    "통해",
    "위해",
    "이후",
    "이전",
    "이번",
    "다음",
}
_WEEKLY_GENERIC_TOKENS = _WEEKLY_GENERIC_ACTIONS | _WEEKLY_GENERIC_NOUNS | _WEEKLY_STOP_TOKENS


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
    ignored = set(_WEEKLY_TASK_MARKERS) | _WEEKLY_STOP_TOKENS | {
        "진행",
        "중",
        "완료",
        "예정",
        "착수",
        "시작",
        "내일",
        "하겠습니다",
    }
    particles = ("으로", "에서", "에게", "에는", "은", "는", "을", "를", "이", "가", "와", "과", "에")
    tokens = set()
    for token in text.split():
        if not token or token in ignored:
            continue
        for particle in particles:
            if len(token) > len(particle) + 1 and token.endswith(particle):
                token = token[: -len(particle)]
                break
        if token and token not in ignored:
            tokens.add(token)
    return tokens


def _weekly_tasks_match(left, right):
    """같은 업무 대상으로 볼 만큼 구체적인 토큰이 겹칠 때만 True."""
    left_tokens = _weekly_task_tokens(left) - _WEEKLY_GENERIC_TOKENS
    right_tokens = _weekly_task_tokens(right) - _WEEKLY_GENERIC_TOKENS
    specific_common = left_tokens & right_tokens
    if not specific_common:
        return False
    # 양쪽에 서로 다른 고유명(매경미디어 vs 주거래, 급여대장 vs 병역지정)이 있으면 별개 업무.
    extras_left = {token for token in left_tokens - right_tokens if len(token) >= 4}
    extras_right = {token for token in right_tokens - left_tokens if len(token) >= 4}
    if extras_left and extras_right:
        return False
    if len(specific_common) >= 2:
        return True
    token = next(iter(specific_common))
    # '미리보기'처럼 구체적이고 충분히 긴 단어 1개만 겹쳐도 같은 대상으로 본다.
    return len(token) >= 4


def reported_project_name(project):
    if not isinstance(project, dict):
        return "미분류 프로젝트"
    name = str(project.get("projectName") or "").strip()
    return name or "미분류 프로젝트"


def _weekly_project_key(project):
    return reported_project_name(project).casefold()


def promote_weekly_tasks(report_data, source_reports=None):
    completed_by_project = defaultdict(list)

    for daily_report in source_reports or []:
        for project in daily_report.get("projects", []):
            if isinstance(project, dict):
                completed_by_project[_weekly_project_key(project)].extend(
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
        next_plans = []
        seen_plans = set()
        for field in ("nextPlans", "nextWeekPlans"):
            for task in project.get(field) or []:
                text = str(task or "").strip()
                if not text or text in seen_plans:
                    continue
                seen_plans.add(text)
                next_plans.append(text)

        completed_candidates = completed + completed_by_project.get(
            _weekly_project_key(project), []
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
        def _plan_done(plan):
            if any(
                _weekly_tasks_match(plan, completed_task)
                for completed_task in completed_candidates
            ):
                return True
            plan_tokens = _weekly_task_tokens(plan) - _WEEKLY_GENERIC_TOKENS
            for progress_task in in_progress:
                if plan == progress_task:
                    return True
                # 진행 문장이 계획 토큰을 모두 포함하면 같은 일의 중복이다.
                progress_tokens = (
                    _weekly_task_tokens(progress_task) - _WEEKLY_GENERIC_TOKENS
                )
                if plan_tokens and plan_tokens <= progress_tokens:
                    return True
            return False

        cleaned_plans = list(
            dict.fromkeys(task for task in next_plans if not _plan_done(task))
        )
        project[next_field] = cleaned_plans
        if "nextWeekPlans" in project:
            project["nextWeekPlans"] = cleaned_plans
        if "nextPlans" in project:
            project["nextPlans"] = cleaned_plans

    return report_data


def ensure_weekly_projects(report_data, source_reports):
    if not isinstance(report_data, dict):
        report_data = {"projects": []}
    report_data.setdefault("projects", [])
    existing = {}
    for project in report_data.get("projects") or []:
        if isinstance(project, dict):
            existing[_weekly_project_key(project)] = project
    for daily in source_reports or []:
        for project in daily.get("projects") or []:
            if not isinstance(project, dict) or not project_has_content(project):
                continue
            key = _weekly_project_key(project)
            if key in existing:
                continue
            added = {
                "projectName": reported_project_name(project),
                "completedTasks": list(project.get("completedTasks") or []),
                "inProgressTasks": list(project.get("inProgressTasks") or []),
                "issues": list(project.get("issues") or []),
                "nextWeekPlans": list(project.get("requests") or [])
                + list(project.get("nextPlans") or []),
            }
            report_data["projects"].append(added)
            existing[key] = added
    return report_data


def _item_covered(item, candidates):
    return any(_weekly_tasks_match(item, candidate) for candidate in candidates)


def ensure_weekly_plans(report_data, source_reports):
    by_key = {}
    for project in report_data.get("projects") or []:
        if isinstance(project, dict):
            by_key[_weekly_project_key(project)] = project
    for daily in source_reports or []:
        for project in daily.get("projects") or []:
            if not isinstance(project, dict):
                continue
            target = by_key.get(_weekly_project_key(project))
            if not target:
                continue
            field = "nextWeekPlans" if "nextWeekPlans" in target else "nextPlans"
            current = list(target.get(field) or [])
            covered = current + list(target.get("completedTasks") or [])
            incoming = list(project.get("requests") or []) + list(
                project.get("nextPlans") or []
            )
            for item in incoming:
                text = str(item or "").strip()
                if not text or _item_covered(text, covered):
                    continue
                current.append(text)
                covered.append(text)
            target[field] = current
            if "nextWeekPlans" in target:
                target["nextPlans"] = list(current)
    return report_data


def _clip_question_item(text, limit=42):
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _missing_weekdays(selects):
    selected = []
    for raw in selects or []:
        try:
            selected.append(date.fromisoformat(str(raw)[:10]).isoformat())
        except ValueError:
            continue
    if not selected:
        return []
    selected_set = set(selected)
    first = date.fromisoformat(min(selected))
    monday = first - timedelta(days=first.weekday())
    friday = monday + timedelta(days=4)
    holiday_names = kr_holiday_map(monday.year, friday.year)
    missing = []
    for offset in range(5):
        day = (monday + timedelta(days=offset)).isoformat()
        if day not in selected_set and day not in holiday_names:
            missing.append(day)
    return missing


def _confirm_item_text(value):
    if isinstance(value, dict):
        return str(value.get("content") or "").strip()
    return str(value or "").strip()


def _issue_looks_resolved(content):
    text = str(content or "")
    if any(
        marker in text
        for marker in (
            "해결되지",
            "미해결",
            "해결 안",
            "안 됐",
            "않음",
            "재현",
            "아직",
            "남아",
            "미결정",
            "보류",
        )
    ):
        return False
    return any(
        marker in text
        for marker in ("완료", "해결됨", "해결했", "수정됨", "반영됨", "고침")
    )


def build_weekly_confirm_questions(report_data, source_reports, selects):
    questions = []
    seen = set()

    def add(qid, text, if_no=""):
        if len(questions) >= 3 or qid in seen or not text:
            return
        seen.add(qid)
        item = {"id": qid, "text": text}
        if if_no:
            item["ifNo"] = if_no
        questions.append(item)

    projects = [
        project
        for project in (report_data.get("projects") or [])
        if isinstance(project, dict)
    ]

    for project in projects:
        name = reported_project_name(project)
        completed = [
            str(task).strip()
            for task in project.get("completedTasks") or []
            if str(task or "").strip()
        ]
        progress = [
            str(task).strip()
            for task in project.get("inProgressTasks") or []
            if str(task or "").strip()
        ]
        next_plans = [
            str(item).strip()
            for item in (project.get("nextPlans") or project.get("nextWeekPlans") or [])
            if str(item or "").strip()
        ]
        for done in completed:
            for prog in progress:
                if not _weekly_tasks_match(done, prog):
                    continue
                add(
                    f"dual:{name}:{done}",
                    (
                        f"{name}의 완료 '{_clip_question_item(done)}'와 "
                        f"진행 '{_clip_question_item(prog)}'가 같은 대상으로 보입니다. "
                        f"이번 주 완료가 맞나요?"
                    ),
                    "진행에서 그 문장을 빼 주세요.",
                )
                break
            for plan in next_plans:
                if not _weekly_tasks_match(done, plan):
                    continue
                add(
                    f"done-plan:{name}:{done}",
                    (
                        f"{name}의 '{_clip_question_item(done)}'이 완료인데 "
                        f"향후일정에도 '{_clip_question_item(plan)}'이 있습니다. "
                        f"향후일정에서 빼도 될까요?"
                    ),
                    "향후일정에서 그 문장을 빼 주세요.",
                )
                break

    by_project = defaultdict(
        lambda: {"completed": [], "progress": [], "issues": []}
    )
    for daily in source_reports or []:
        day = str(daily.get("_reportDate") or "")
        for project in daily.get("projects") or []:
            if not isinstance(project, dict):
                continue
            name = reported_project_name(project)
            for task in project.get("completedTasks") or []:
                text = str(task or "").strip()
                if text:
                    by_project[name]["completed"].append((day, text))
            for task in project.get("inProgressTasks") or []:
                text = str(task or "").strip()
                if text:
                    by_project[name]["progress"].append((day, text))
            for issue in project.get("issues") or []:
                text = _confirm_item_text(issue)
                if text:
                    by_project[name]["issues"].append((day, text))

    for name, bucket in by_project.items():
        found = False
        for _day_c, done in bucket["completed"]:
            for _day_p, prog in bucket["progress"]:
                if not _weekly_tasks_match(done, prog):
                    continue
                add(
                    f"conflict:{name}:{done}",
                    (
                        f"{name}의 '{_clip_question_item(done)}'은 어떤 날엔 완료, "
                        f"어떤 날엔 진행 중이었습니다. 이번 주 완료가 맞나요?"
                    ),
                    "진행·이슈에 남은 같은 대상 문장을 정리해 주세요.",
                )
                found = True
                break
            if found:
                break

    for project in projects:
        name = reported_project_name(project)
        completed = [
            str(task).strip()
            for task in project.get("completedTasks") or []
            if str(task or "").strip()
        ]
        for issue in project.get("issues") or []:
            content = _confirm_item_text(issue)
            if not content:
                continue
            looks_done = _issue_looks_resolved(content)
            overlaps_done = any(
                _weekly_tasks_match(content, done) for done in completed
            )
            if not looks_done and not overlaps_done:
                continue
            add(
                f"issue-done:{name}:{content}",
                (
                    f"{name} 이슈 '{_clip_question_item(content)}'가 "
                    f"{'완료된 업무와 겹칩니다' if overlaps_done else '이미 끝난 것처럼 읽힙니다'}. "
                    f"아직 열린 이슈가 맞나요?"
                ),
                "이슈에서 빼고 필요하면 완료로 옮기세요.",
            )

    for project in projects:
        name = reported_project_name(project)
        if "미분류" in name:
            add(
                "unclassified",
                f"'{name}'로 묶인 항목이 있습니다. 미분류로 두어도 되나요?",
                "올바른 프로젝트명으로 바꿔 주세요.",
            )
            break

    for name, bucket in by_project.items():
        counts = defaultdict(int)
        for _day, text in bucket["progress"]:
            counts[text] += 1
        for text, count in counts.items():
            if count < 3:
                continue
            add(
                f"stale:{name}:{text}",
                (
                    f"{name}의 '{_clip_question_item(text)}'이 여러 날 진행 중이었습니다. "
                    f"아직 진행 중이 맞나요?"
                ),
                "끝났으면 완료로 옮기고 진행에서 빼 주세요.",
            )
            break

    empty_next = [
        reported_project_name(project)
        for project in projects
        if not any(
            str(item or "").strip()
            for item in (project.get("nextPlans") or project.get("nextWeekPlans") or [])
        )
        and any(
            str(item or "").strip()
            for key in ("completedTasks", "inProgressTasks", "issues")
            for item in (project.get(key) or [])
        )
    ]
    if empty_next:
        label = empty_next[0] if len(empty_next) == 1 else f"{empty_next[0]} 외 {len(empty_next) - 1}개"
        add(
            "empty-next",
            f"{label}의 향후일정이 비어 있습니다. 다음 일이 없는 게 맞나요?",
            "다음 주 할 일이 있으면 향후일정에 적어 주세요.",
        )

    return questions[:3]


def _quoted_snippets(text):
    found = []
    for match in re.finditer(
        r"'([^']+)'|\"([^\"]+)\"|‘([^’]+)’|“([^”]+)”", str(text or "")
    ):
        snippet = next((group for group in match.groups() if group), "").strip()
        if snippet:
            found.append(snippet)
    return found


def _weekly_field_texts(report_data, fields):
    values = []
    for project in report_data.get("projects") or []:
        if not isinstance(project, dict):
            continue
        for field in fields:
            for item in project.get(field) or []:
                text = _confirm_item_text(item)
                if text:
                    values.append(text)
        name = reported_project_name(project)
        if name:
            values.append(name)
    return values


def _snippet_in(snippet, texts):
    return any(snippet in text or text in snippet for text in texts if text)


def _question_claims_merge_of_distinct_tasks(text, if_no=""):
    """관련·원인·같은 이슈를 추측해 묶거나 가르는 질문인지."""
    blob = f"{text}\n{if_no}"
    return any(
        marker in blob
        for marker in (
            "통합",
            "합치",
            "같은 작업이면",
            "같은 일이면",
            "같은 이슈",
            "같은 문제",
            "별개 작업으로 봐도",
            "별개로 봐도",
            "별개 문제",
            "별개라면",
            "원인이라면",
            "원인이면",
            "두 칸 배치",
            "관련인데",
            "관련이라",
        )
    )


def _quoted_pair_matches(quotes):
    for index, left in enumerate(quotes):
        for right in quotes[index + 1 :]:
            if _weekly_tasks_match(left, right):
                return True
    return False


def _question_is_grounded(text, report_data, if_no=""):
    quotes = _quoted_snippets(text)
    if not quotes:
        return False
    forbidden = (
        "이대로 저장",
        "이대로 확정",
        "이대로 두어도",
        "별개 작업으로 봐도",
        "별개로 봐도",
        "별개 문제",
        "별개라면",
        "같은 이슈",
        "같은 문제",
        "원인이라면",
        "원인이면",
        "두 칸 배치",
    )
    if any(marker in text for marker in forbidden):
        return False
    all_texts = _weekly_field_texts(
        report_data,
        (
            "completedTasks",
            "inProgressTasks",
            "issues",
            "nextPlans",
            "nextWeekPlans",
        ),
    )
    for project in report_data.get("projects") or []:
        if isinstance(project, dict):
            name = reported_project_name(project)
            if name:
                all_texts.append(name)
    nexts = _weekly_field_texts(report_data, ("nextPlans", "nextWeekPlans"))
    issues = _weekly_field_texts(report_data, ("issues",))
    completed = _weekly_field_texts(report_data, ("completedTasks",))
    progress = _weekly_field_texts(report_data, ("inProgressTasks",))
    in_weekly = all(_snippet_in(quote, all_texts) for quote in quotes)
    says_missing = "빠졌" in text
    if says_missing:
        return False
    if not in_weekly:
        return False
    if "다음 주 계획에" in text or "nextWeekPlans에" in text or "nextWeekPlans에도" in text:
        if not any(_snippet_in(quote, nexts) for quote in quotes):
            return False
    if "이슈에" in text or "이슈 '" in text or "issues에" in text:
        if not any(_snippet_in(quote, issues) for quote in quotes):
            return False
    claims_in_progress = (
        "진행 중에 있습니다" in text
        or "진행 중으로" in text
        or "inProgressTasks에" in text
        or "inProgressTasks '" in text
    )
    if claims_in_progress:
        if not any(_snippet_in(quote, progress) for quote in quotes):
            return False
    if (
        "완료에 있습니다" in text
        or "완료된 업무로 처리" in text
        or "completedTasks에" in text
        or "completedTasks '" in text
    ):
        if not any(_snippet_in(quote, completed) for quote in quotes):
            return False
    # 진행+이슈를 인용하며 같은지/별개인지만 묻는 질문은 버린다(정상 배치).
    quotes_progress = any(_snippet_in(quote, progress) for quote in quotes)
    quotes_issue = any(_snippet_in(quote, issues) for quote in quotes)
    if quotes_progress and quotes_issue and "완료" not in text:
        return False
    if (
        len(quotes) >= 2
        and _question_claims_merge_of_distinct_tasks(text, if_no)
        and not _quoted_pair_matches(quotes)
    ):
        return False
    return True


def ask_weekly_confirm_questions(client, report_data, dated_reports, selects):
    weekly_view = {
        "projects": [
            {
                "projectName": project.get("projectName"),
                "completedTasks": list(project.get("completedTasks") or []),
                "inProgressTasks": list(project.get("inProgressTasks") or []),
                "issues": [
                    _confirm_item_text(issue)
                    for issue in project.get("issues") or []
                    if _confirm_item_text(issue)
                ],
                "nextWeekPlans": list(
                    project.get("nextPlans") or project.get("nextWeekPlans") or []
                ),
            }
            for project in report_data.get("projects") or []
            if isinstance(project, dict)
        ]
    }
    payload = {"weeklyDraft": weekly_view}
    with open("./model_asset/weekly_confirm_json_schema.json", encoding="utf-8") as handle:
        confirm_schema = json.load(handle)
    kwargs = dict(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": load_weekly_confirm_prompt()},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.1,
        max_tokens=min(4096, WEEKLY_MAX_TOKENS),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "weekly_confirm",
                "strict": True,
                "schema": confirm_schema,
            },
        },
    )
    apply_reasoning(kwargs, WEEKLY_REASONING)
    completion = client.chat.completions.create(**kwargs)
    parsed = json.loads(read_completion(completion, "weekly-confirm"))
    return parsed.get("confirmQuestions") or []


def attach_confirm_questions(
    report_data, dated_reports, selects, model_questions=None
):
    if not isinstance(report_data, dict):
        report_data = {"projects": []}
    cleaned = []
    seen = set()

    def take(items, *, trust=False):
        for item in items or []:
            if isinstance(item, str):
                text, if_no = item.strip(), ""
            elif isinstance(item, dict):
                text = str(item.get("text") or "").strip()
                if_no = str(item.get("ifNo") or "").strip()
            else:
                continue
            if not text or text in seen:
                continue
            # 모델 질문만 grounding. 서버 heuristic은 이미 초안 근거로 만든 문장이다.
            if not trust and not _question_is_grounded(text, report_data, if_no=if_no):
                continue
            seen.add(text)
            question = {"text": text}
            if if_no:
                question["ifNo"] = if_no
            cleaned.append(question)
            if len(cleaned) >= 3:
                return

    take(model_questions, trust=False)
    model_kept = len(cleaned)
    if len(cleaned) < 3:
        take(
            build_weekly_confirm_questions(report_data, dated_reports, selects),
            trust=True,
        )
    report_data["confirmQuestions"] = cleaned[:3]
    print(
        f"[weekly-confirm] model={len(model_questions or [])} "
        f"kept={model_kept} final={len(report_data['confirmQuestions'])}"
    )
    return report_data


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/project-timeline")
def get_project_timeline(name: str, member_id: int = None, actor_id: int = Depends(current_member_id)):
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


@app.get("/project-names")
def get_project_names(actor_id: int = Depends(current_member_id)):
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
def get_registered_project_names(actor_id: int = Depends(current_member_id)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name, keywords, created_at FROM known_projects ORDER BY name"
        ).fetchall()
    return [
        {"name": row[0], "keywords": row[1] or "", "created_at": row[2]} for row in rows
    ]


@app.post("/project-names")
def create_project_name(data: ProjectNameRequest, actor_id: int = Depends(current_member_id)):
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
def delete_project_name(project_name: str, actor_id: int = Depends(current_member_id)):
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
def update_project_name_keywords(project_name: str, data: ProjectNameKeywordsRequest, actor_id: int = Depends(current_member_id)):
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


def parse_json_object(content):
    data = content
    for _ in range(3):
        if not isinstance(data, str):
            break
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON 파싱 실패: {str(content)[:200]}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"dict 아님: {type(data)}")
    return data


def _clean_keyword_items(items):
    cleaned = []
    seen_names = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("projectName") or "").strip()
        if not name or name.casefold() in seen_names:
            continue
        keywords = []
        seen_keywords = {name.casefold()}
        for keyword in item.get("suggestedKeywords") or []:
            text = str(keyword or "").strip()
            key = text.casefold()
            if not text or key in seen_keywords:
                continue
            seen_keywords.add(key)
            keywords.append(text)
        cleaned.append(
            {
                "projectName": name,
                "suggestedKeywords": keywords,
                "reason": str(item.get("reason") or "").strip(),
            }
        )
        seen_names.add(name.casefold())
    return cleaned


def normalize_keyword_recommendation(content, registered_rows):
    data = parse_json_object(content)
    registered_by_fold = {}
    existing_keywords = {}
    for name, keywords in registered_rows:
        registered_by_fold[name.casefold()] = name
        existing_keywords[name] = {
            part.casefold() for part in split_project_keywords(keywords)
        } | {name.casefold()}

    additions = []
    new_projects = []
    for item in _clean_keyword_items(data.get("keywordAdditions")):
        canonical = registered_by_fold.get(item["projectName"].casefold())
        if canonical:
            item["projectName"] = canonical
            item["suggestedKeywords"] = [
                keyword
                for keyword in item["suggestedKeywords"]
                if keyword.casefold() not in existing_keywords.get(canonical, set())
            ]
            if item["suggestedKeywords"]:
                additions.append(item)
        else:
            new_projects.append(item)

    for item in _clean_keyword_items(data.get("newProjects")):
        canonical = registered_by_fold.get(item["projectName"].casefold())
        if canonical:
            extra = [
                keyword
                for keyword in item["suggestedKeywords"]
                if keyword.casefold() not in existing_keywords.get(canonical, set())
            ]
            if extra:
                additions.append(
                    {
                        "projectName": canonical,
                        "suggestedKeywords": extra,
                        "reason": item["reason"],
                    }
                )
        else:
            new_projects.append(item)

    merged_additions = []
    addition_index = {}
    for item in additions:
        key = item["projectName"].casefold()
        if key in addition_index:
            current = merged_additions[addition_index[key]]
            seen = {k.casefold() for k in current["suggestedKeywords"]}
            for keyword in item["suggestedKeywords"]:
                if keyword.casefold() not in seen:
                    current["suggestedKeywords"].append(keyword)
                    seen.add(keyword.casefold())
        else:
            addition_index[key] = len(merged_additions)
            merged_additions.append(item)

    return {"keywordAdditions": merged_additions, "newProjects": new_projects}


def call_keyword_model(report):
    client = OpenAI(
        base_url=LM_BASE_URL,
        api_key=LM_API_KEY,
        timeout=LLM_TIMEOUT_SECONDS,
    )
    kwargs = dict(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": load_keyword_prompt()},
            {"role": "user", "content": report},
        ],
        temperature=0.1,
        max_tokens=KEYWORD_MAX_TOKENS,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "keyword_recommendation",
                "strict": True,
                "schema": keyword_schema,
            },
        },
    )
    apply_reasoning(kwargs, KEYWORD_REASONING)
    completion = client.chat.completions.create(**kwargs)
    return read_completion(completion, "recommend-keywords")


@app.post("/project-names/recommend")
def recommend_project_keywords(data: KeywordRecommendRequest, actor_id: int = Depends(current_member_id)):
    report = (data.report or "").strip()
    if not report:
        raise HTTPException(status_code=400, detail="원문을 입력해주세요.")

    registered_rows = get_known_project_rows()
    try:
        content = call_keyword_model(report)
        keywords = normalize_keyword_recommendation(content, registered_rows)
        return {"keywords": keywords}
    except HTTPException:
        raise
    except Exception as e:
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            print(f"[recommend-keywords] upstream status={resp.status_code} body={detail}")
            raise HTTPException(
                status_code=502,
                detail=f"AI 모델 호출 실패 (status={resp.status_code}). 다시 시도해주세요.",
            )
        print(f"[recommend-keywords] error: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"AI 모델 호출 실패: {e}. 다시 시도해주세요.",
        )


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


def generate_weekly_report(member_id, selects, *, persist=True):
    selects = normalize_selected_dates(selects)
    with get_db() as db:
        res = db.execute(
            """
            SELECT report_date, parsed_json FROM daily_reports
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

        reports = []
        dated_reports = []
        for row in res:
            daily = coerce_report_data(row[1])
            reports.append(daily)
            stamped = dict(daily)
            stamped["_reportDate"] = str(row[0] or "")
            dated_reports.append(stamped)

        previous_rows = db.execute(
            "SELECT selected_date, report_json FROM weekly_reports WHERE member_id = ?",
            (member_id,),
        ).fetchall()
        previous_candidates = []
        for row in previous_rows:
            try:
                previous_candidates.append(
                    (
                        json.loads(row[0] or "[]"),
                        json.loads(row[1] or "{}"),
                    )
                )
            except json.JSONDecodeError:
                continue
        last_week = pick_previous_weekly(previous_candidates, selects)
        last_next = next_sections_of(last_week)
        weekly_system = load_weekly_prompt()
        if last_next:
            weekly_system += (
                "\n\n지난주 향후(아래)는 이번 주 초안이다. "
                "이번 일일에서 끝난 것은 completedTasks에 두고, "
                "일일에 안 나온 지난주 향후는 nextWeekPlans에 그대로 남긴다. 버리지 않는다.\n"
                "[지난주 향후]\n"
                + json.dumps(last_next, ensure_ascii=False)
            )
        try:
            client = OpenAI(
                base_url=LM_BASE_URL,
                api_key=LM_API_KEY,
                timeout=LLM_TIMEOUT_SECONDS,
            )
            kwargs = dict(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": weekly_system},
                    {
                        "role": "user",
                        "content": json.dumps(
                            [
                                {
                                    "reportDate": daily.get("_reportDate"),
                                    "projects": daily.get("projects") or [],
                                }
                                for daily in dated_reports
                            ],
                            ensure_ascii=False,
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=WEEKLY_MAX_TOKENS,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "weekly_report",
                        "strict": True,
                        "schema": json.load(
                            open(
                                "./model_asset/weekly_json_schema.json",
                                encoding="utf-8",
                            )
                        ),
                    },
                },
            )
            apply_reasoning(kwargs, WEEKLY_REASONING)
            completion = client.chat.completions.create(**kwargs)

            report_data = drop_empty_projects(
                coerce_report_data(
                    read_completion(completion, "weekly-report"),
                    strict=True,
                )
            )
            for project in report_data.get("projects", []):
                if not isinstance(project, dict):
                    continue
                if "nextWeekPlans" in project and "nextPlans" not in project:
                    project["nextPlans"] = list(project.get("nextWeekPlans") or [])
            report_data = promote_weekly_tasks(report_data, reports)
            report_data = ensure_weekly_projects(report_data, reports)
            report_data = ensure_weekly_plans(report_data, reports)
            report_data = promote_weekly_tasks(report_data, reports)
            carried = 0
            if last_next:
                report_data, carried = merge_last_week_next(report_data, last_next)
            report_data = normalize_issues(report_data)
            report_data = drop_empty_projects(report_data)
            report_data.pop("confirmQuestions", None)
            model_questions = []
            try:
                model_questions = ask_weekly_confirm_questions(
                    client, report_data, dated_reports, selects
                )
            except Exception as confirm_exc:
                print(f"[weekly-confirm] {confirm_exc}")
            report_data = attach_confirm_questions(
                report_data, dated_reports, selects, model_questions
            )
            member_row = db.execute(
                """
                SELECT m.name, t.team_name
                FROM members m
                LEFT JOIN teams t ON m.team_id = t.id
                WHERE m.id = ?
                """,
                (member_id,),
            ).fetchone()
            report_data = from_legacy(
                report_data,
                selected_dates=selects,
                member_name=(member_row["name"] if member_row else ""),
                team_name=(member_row["team_name"] if member_row else "") or "",
            )
            if carried:
                report_data["carriedFromLastWeek"] = True
                report_data["carriedCount"] = carried
        except HTTPException:
            raise
        except Exception as exc:
            resp = getattr(exc, "response", None)
            if resp is not None:
                try:
                    detail = resp.json()
                except Exception:
                    detail = resp.text
                print(
                    f"[weekly-report] upstream status={resp.status_code} body={detail}"
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"주간 보고서 AI 호출 실패 (status={resp.status_code}).",
                )
            print(f"[weekly-report] error: {exc}")
            raise HTTPException(
                status_code=502,
                detail=f"주간 보고서 AI 호출 실패: {exc}",
            )

        if persist:
            replace_member_week(
                db,
                member_id,
                selects,
                json.dumps(report_data, ensure_ascii=False),
            )
            db.commit()
        return report_data


@app.post("/weekly-report")
def weekly_report(data: WeeklyReportRequest, actor_id: int = Depends(current_member_id)):
    require_own_or_admin(actor_id, data.userId)
    selects = normalize_selected_dates(data.selects)
    report_data = generate_weekly_report(data.userId, selects, persist=False)
    if report_data is None:
        raise HTTPException(
            status_code=404, detail="선택한 기간에 저장된 일일보고가 없습니다."
        )
    return {"report": report_data, "selects": selects, "memberId": data.userId}


@app.post("/weekly")
def create_weekly(data: CreateWeeklyData, actor_id: int = Depends(current_member_id)):
    require_own_or_admin(actor_id, data.member_id)
    selects = normalize_selected_dates(data.selects)
    if not selects:
        raise HTTPException(status_code=400, detail="기간(날짜)을 최소 1개 선택해주세요.")
    try:
        report_data = json.loads(data.report_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="유효한 JSON이 아닙니다.")
    if not isinstance(report_data, dict):
        raise HTTPException(
            status_code=400, detail="주간 보고서 데이터가 유효하지 않습니다."
        )
    report_data = normalize_issues(report_data)
    with get_db() as db:
        new_id = replace_member_week(
            db,
            data.member_id,
            selects,
            json.dumps(report_data, ensure_ascii=False),
        )
    return {"id": new_id}


def process_daily_report(report: str, report_date: str, member_id: int):
    if not report.strip():
        raise HTTPException(status_code=400, detail="보고서 내용을 입력해주세요.")
    report_date = validate_report_date(report_date)

    with get_db() as conn:
        validate_member(conn, member_id)
        member_name = conn.execute(
            "SELECT name FROM members WHERE id = ?",
            (member_id,),
        ).fetchone()["name"]
        conn.execute(
            """
            INSERT INTO report_drafts (member_id, report_date, raw_text, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(member_id, report_date)
            DO UPDATE SET raw_text = excluded.raw_text,
                          updated_at = CURRENT_TIMESTAMP
            """,
            (member_id, report_date, report),
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
                {
                    "role": "user",
                    "content": (
                        f"작성자: {member_name}\n"
                        f"보고일: {report_date}\n\n"
                        f"{report}"
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "daily_report",
                    "strict": True,
                    "schema": json.load(
                        open("./model_asset/json_Schema.json", encoding="utf-8")
                    ),
                },
            },
        )
        apply_reasoning(kwargs, DAILY_REASONING)
        completion = client.chat.completions.create(**kwargs)

        content = read_completion(completion, "send-report")
        return drop_empty_projects(coerce_report_data(content, strict=True))
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


@app.post("/send-report")
async def send_report(data: ReportRequest, actor_id: int = Depends(current_member_id)):
    require_own_or_admin(actor_id, data.member_id)
    return process_daily_report(data.report, data.date, data.member_id)


@app.post("/send-report-pptx")
async def send_report_pptx(
    file: UploadFile = File(...),
    date: str = Form(...),
    member_id: int = Form(...),
    actor_id: int = Depends(current_member_id),
):
    require_own_or_admin(actor_id, member_id)
    filename = (file.filename or "").lower()
    if not filename.endswith(".pptx"):
        raise HTTPException(
            status_code=400,
            detail="PPTX 파일만 업로드할 수 있습니다.",
        )
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="빈 파일입니다.")
        raw_text = extract_all_text_from_pptx(io.BytesIO(content))
    except HTTPException:
        raise
    except Exception as e:
        print(f"[send-report-pptx] extract error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"PPTX 텍스트 추출에 실패했습니다: {e}",
        )

    if not raw_text.strip():
        raise HTTPException(
            status_code=400,
            detail="PPTX에서 추출된 텍스트가 없습니다.",
        )

    parsed = process_daily_report(raw_text, date, member_id)
    return {"parsed": parsed, "raw_text": raw_text}


@app.post("/report-drafts")
def save_report_draft(
    data: ReportDraftRequest, actor_id: int = Depends(current_member_id)
):
    """초안만 저장한다. 고치려고 AI를 다시 돌릴 필요가 없어야 한다."""
    require_own_or_admin(actor_id, data.member_id)
    report_date = validate_report_date(data.date)
    raw_text = data.report
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="저장할 내용이 없습니다.")
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
            (data.member_id, report_date, raw_text),
        )
        conn.commit()
    return {
        "message": "초안을 저장했습니다.",
        "member_id": data.member_id,
        "report_date": report_date,
    }


@app.get("/report-drafts/{member_id}/{report_date}")
def get_report_draft(member_id: int, report_date: str, actor_id: int = Depends(current_member_id)):
    require_own_or_admin(actor_id, member_id)
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


@app.get("/holidays")
def get_holidays(year: int):
    items = kr_holiday_map(year - 1, year, year + 1)
    return [{"date": day, "name": name} for day, name in items.items()]


@app.get("/user-activities")
def get_user_activities(
    year: int,
    month: int,
    start_date: str | None = None,
    end_date: str | None = None,
    actor_id: int = Depends(current_member_id),
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
            SELECT id, name, team_id
            FROM members
            ORDER BY id
        """)
        members = cursor.fetchall()

        cursor.execute(
            """
            SELECT report_date, member_id, COUNT(report_date), MAX(id)
            FROM daily_reports
            WHERE report_date BETWEEN ? AND ?
            GROUP BY report_date, member_id
            """,
            (start_date, end_date),
        )

        counts = defaultdict(dict)
        report_ids = defaultdict(dict)
        for report_date, member_id, count, report_id in cursor.fetchall():
            counts[member_id][report_date] = count
            report_ids[member_id][report_date] = report_id

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

    for member_id, name, team_id in members:
        activities = []

        current = first_day
        while current <= last_day:
            report_date = current.isoformat()

            activities.append(
                {
                    "report_date": report_date,
                    "count": counts[member_id].get(report_date, 0),
                    "report_id": report_ids[member_id].get(report_date),
                }
            )

            current += timedelta(days=1)

        result.append(
            {
                "member_id": member_id,
                "name": name,
                "team_id": team_id,
                "total_count": total_counts.get(member_id, 0),
                "activities": activities,
            }
        )
    return result


@app.delete("/reports/{report_id}")
def delete_report(report_id: int, actor_id: int = Depends(current_member_id)):
    with get_db() as db:
        row = db.execute(
            "SELECT member_id FROM daily_reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="보고서를 찾을 수 없습니다.")
        require_own_or_admin(actor_id, row["member_id"], conn=db)
        db.execute("DELETE FROM daily_reports WHERE id = ?", (report_id,))
    return {"message": "Report deleted successfully"}


@app.delete("/weekly/{report_id}")
def delete_weekly_report(report_id: int, actor_id: int = Depends(current_member_id)):
    with get_db() as db:
        row = db.execute(
            "SELECT member_id FROM weekly_reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Weekly report not found")
        require_own_or_admin(actor_id, row["member_id"], conn=db)
        db.execute("DELETE FROM weekly_reports WHERE id = ?", (report_id,))
    return {"message": "Report deleted successfully"}


@app.get("/weekly/{user_id}")
def get_weekly(user_id: int, actor_id: int = Depends(current_member_id)):
    with get_db() as db:
        rows = db.execute(
            """
            SELECT w.id, w.member_id, m.name, t.team_name,
                   w.selected_date, w.report_json, w.created_at
            FROM weekly_reports w
            LEFT JOIN members m ON w.member_id = m.id
            LEFT JOIN teams t ON m.team_id = t.id
            WHERE w.member_id = ?
        """,
            (user_id,),
        ).fetchall()

    return [
        {
            "id": row[0],
            "memberId": row[1],
            "memberName": row[2],
            "selectedDate": json.loads(row[4]),
            "report": from_legacy(
                normalize_issues(json.loads(row[5])),
                selected_dates=json.loads(row[4]),
                member_name=row[2] or "",
                team_name=row[3] or "",
            ),
            "createdAt": row[6],
        }
        for row in rows
    ]


@app.get("/weeklyById/{weekly_id}")
def get_weekly_by_id(weekly_id: int, actor_id: int = Depends(current_member_id)):
    with get_db() as db:
        row = db.execute(
            """
            SELECT w.id, w.member_id, m.name, t.team_name,
                   w.selected_date, w.report_json, w.created_at
            FROM weekly_reports w
            LEFT JOIN members m ON w.member_id = m.id
            LEFT JOIN teams t ON m.team_id = t.id
            WHERE w.id = ?
        """,
            (weekly_id,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Weekly report not found")

    selected = json.loads(row[4])
    return {
        "id": row[0],
        "memberId": row[1],
        "memberName": row[2],
        "selectedDate": selected,
        "report": from_legacy(
            normalize_issues(json.loads(row[5])),
            selected_dates=selected,
            member_name=row[2] or "",
            team_name=row[3] or "",
        ),
        "createdAt": row[6],
    }


@app.get("/weeklyById/{weekly_id}/pptx")
def export_weekly_pptx(weekly_id: int, actor_id: int = Depends(current_member_id)):
    with get_db() as db:
        row = db.execute(
            """
            SELECT w.id, w.member_id, m.name, t.team_name,
                   w.selected_date, w.report_json, w.created_at
            FROM weekly_reports w
            LEFT JOIN members m ON w.member_id = m.id
            LEFT JOIN teams t ON m.team_id = t.id
            WHERE w.id = ?
            """,
            (weekly_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Weekly report not found")
    selected = json.loads(row[4])
    payload = fill_weekly_pptx(
        {
            "memberName": row[2] or f"사용자_{row[1]}",
            "teamName": row[3] or "",
            "selectedDate": selected,
            "report": from_legacy(
                normalize_issues(json.loads(row[5])),
                selected_dates=selected,
                member_name=row[2] or "",
                team_name=row[3] or "",
            ),
        }
    )
    days = sorted(str(d)[:10] for d in selected or [])
    period = days[-1] if days else "week"
    member_name = row[2] or f"사용자_{row[1]}"
    filename = f"주간_보고서_{member_name}_{period}.pptx"
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@app.put("/weekly/{weekly_id}")
def update_weekly(
    weekly_id: int,
    data: UpdateWeeklyData,
    actor_id: int = Depends(current_member_id),
):
    try:
        report_data = json.loads(data.report_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="유효한 JSON이 아닙니다.")
    if not isinstance(report_data, dict):
        raise HTTPException(
            status_code=400, detail="주간 보고서 데이터가 유효하지 않습니다."
        )
    report_data = normalize_issues(report_data)

    with get_db() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT member_id FROM weekly_reports WHERE id = ?",
            (weekly_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Weekly report not found")
        require_own_or_admin(actor_id, row["member_id"], conn=conn)
        cursor.execute(
            "UPDATE weekly_reports SET report_json = ? WHERE id = ?",
            (json.dumps(report_data), weekly_id),
        )
        conn.commit()

    return {"message": "주간 보고서가 수정되었습니다."}


@app.get("/reports")
def get_reports(actor_id: int = Depends(current_member_id)):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                d.id,
                d.member_id,
                m.name AS member_name,
                m.team_id AS member_team_id,
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
            parsed = json.loads(row[6]) if row[6] else None
            if parsed:
                parsed = normalize_issues(parsed)
            reports.append(
                {
                    "id": row[0],
                    "member_id": row[1],
                    "member_name": row[2],
                    "member_team_id": row[3],
                    "report_date": row[4],
                    "raw_text": row[5],
                    "parsed_json": parsed,
                    "created_at": row[7],
                }
            )
    return reports


@app.get("/reports/{report_id}")
def get_report_by_id(report_id: int, actor_id: int = Depends(current_member_id)):
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


def _member_public(row) -> dict:
    keys = row.keys()
    has_password = False
    if "password_hash" in keys:
        has_password = bool(row["password_hash"])
    return {
        "id": row["id"],
        "name": row["name"],
        "team_id": row["team_id"],
        "created_at": row["created_at"] if "created_at" in keys else None,
        "has_password": has_password,
        "is_admin": bool(row["is_admin"]) if "is_admin" in keys else False,
    }


def _create_session(conn, member_id: int) -> str:
    token = new_session_token()
    conn.execute(
        "INSERT INTO sessions (token, member_id) VALUES (?, ?)",
        (token, member_id),
    )
    return token


@app.post("/login")
def login(data: LoginRequest):
    name = data.name.strip()
    password = data.password
    if not name or not password:
        raise HTTPException(status_code=400, detail="이름과 비밀번호를 입력해주세요.")
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id, name, team_id, password_hash, is_admin
            FROM members
            WHERE name = ?
            """,
            (name,),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=401, detail="이름 또는 비밀번호가 올바르지 않습니다."
            )
        stored = row["password_hash"] or ""
        if not stored:
            raise HTTPException(
                status_code=403,
                detail="비밀번호가 아직 없습니다. 관리자에게 임시 비밀번호를 받아 주세요.",
            )
        if not verify_password(password, stored):
            raise HTTPException(
                status_code=401, detail="이름 또는 비밀번호가 올바르지 않습니다."
            )
        token = _create_session(conn, row["id"])
        conn.commit()
    return {
        "token": token,
        "member_id": row["id"],
        "name": row["name"],
        "team_id": row["team_id"],
        "is_admin": bool(row["is_admin"]) if "is_admin" in row.keys() else False,
    }


@app.post("/logout")
def logout(token: str = Depends(session_token_from_headers)):
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
    return {"message": "로그아웃했습니다."}


@app.get("/me")
def me(actor_id: int = Depends(current_member_id)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, team_id, created_at, is_admin FROM members WHERE id = ?",
            (actor_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="로그인해 주세요.")
    return {
        "member_id": row["id"],
        "name": row["name"],
        "team_id": row["team_id"],
        "created_at": row["created_at"],
        "is_admin": bool(row["is_admin"]) if "is_admin" in row.keys() else False,
    }


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordSetRequest(BaseModel):
    password: str


@app.post("/me/password")
def change_my_password(
    data: PasswordChangeRequest, actor_id: int = Depends(current_member_id)
):
    try:
        hashed = hash_password(data.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    with get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM members WHERE id = ?",
            (actor_id,),
        ).fetchone()
        if not row or not row["password_hash"]:
            raise HTTPException(status_code=400, detail="비밀번호가 아직 없습니다.")
        if not verify_password(data.current_password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")
        conn.execute(
            "UPDATE members SET password_hash = ? WHERE id = ?",
            (hashed, actor_id),
        )
        conn.commit()
    return {"message": "비밀번호를 바꿨습니다."}


@app.post("/users/{member_id}/password")
def set_member_password(
    member_id: int,
    data: PasswordSetRequest,
    actor_id: int = Depends(current_member_id),
):
    try:
        hashed = hash_password(data.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    with get_db() as conn:
        require_admin(conn, actor_id)
        validate_member(conn, member_id)
        row = conn.execute(
            "SELECT password_hash FROM members WHERE id = ?",
            (member_id,),
        ).fetchone()
        stored = (row["password_hash"] if row else "") or ""
        if stored:
            raise HTTPException(
                status_code=403,
                detail="이미 비밀번호가 있는 계정은 본인만 바꿀 수 있습니다.",
            )
        conn.execute(
            "UPDATE members SET password_hash = ? WHERE id = ?",
            (hashed, member_id),
        )
        conn.commit()
    return {"message": "임시 비밀번호를 넣었습니다."}


@app.post("/users")
def save_user(
    data: UserRequest,
    authorization: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None),
):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="이름을 입력해주세요.")
    password = data.password or ""
    try:
        hashed = hash_password(password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    with get_db() as conn:
        member_count = conn.execute("SELECT COUNT(*) AS n FROM members").fetchone()["n"]
        make_admin = member_count == 0
        if member_count:
            try:
                token = session_token_from_headers(authorization, x_session_token)
            except HTTPException:
                raise HTTPException(status_code=401, detail="로그인해 주세요.")
            session = conn.execute(
                "SELECT member_id FROM sessions WHERE token = ?",
                (token,),
            ).fetchone()
            if not session:
                raise HTTPException(status_code=401, detail="로그인이 만료되었습니다.")
            require_admin(conn, session["member_id"])
        cursor = conn.cursor()
        team_id = data.team_id
        if team_id is None:
            team_id = get_or_create_unassigned_team(conn)
        elif not conn.execute(
            "SELECT 1 FROM teams WHERE id = ?", (team_id,)
        ).fetchone():
            raise HTTPException(status_code=400, detail="유효하지 않은 팀입니다.")
        try:
            cursor.execute(
                "INSERT INTO members (name, team_id, password_hash, is_admin) VALUES (?, ?, ?, ?)",
                (name, team_id, hashed, 1 if make_admin else 0),
            )
        except sqlite3.IntegrityError as exc:
            err = str(exc).lower()
            if "unique" in err:
                raise HTTPException(
                    status_code=409, detail=f"'{name}' 사용자가 이미 존재합니다."
                )
            raise HTTPException(
                status_code=400, detail="사용자를 저장하지 못했습니다."
            )
        user_id = cursor.lastrowid
        conn.commit()
    return {
        "id": user_id,
        "name": name,
        "team_id": team_id,
        "message": "User saved successfully.",
    }


@app.get("/users")
def get_users(actor_id: int = Depends(current_member_id)):
    with get_db() as db:
        users = db.execute(
            "SELECT id, name, team_id, created_at, password_hash, is_admin FROM members"
        ).fetchall()

    return [_member_public(user) for user in users]

@app.post("/teams/set")
def set_team(data: SetTeamData, actor_id: int = Depends(current_member_id)):
    team_id = data.team_id
    user_id = data.user_id
    with get_db() as conn:
        if int(actor_id) != int(user_id) and not member_is_admin(conn, actor_id):
            raise HTTPException(status_code=403, detail="자신의 부서만 변경할 수 있습니다.")
        validate_member(conn, user_id)
        if not conn.execute("SELECT 1 FROM teams WHERE id = ?", (team_id,)).fetchone():
            raise HTTPException(status_code=400, detail="유효하지 않은 팀입니다.")
        cursor = conn.cursor()
        cursor.execute("UPDATE members SET team_id = ? WHERE id = ?", (team_id, user_id))
        conn.commit()
    return {"message": "Team set successfully."}

@app.post("/teams")
def save_team(data: TeamRequest, actor_id: int = Depends(current_member_id)):
    team_name = data.team_name.strip()
    if not team_name:
        raise HTTPException(status_code=400, detail="팀 이름을 입력해주세요.")
    with get_db() as conn:
        require_admin(conn, actor_id)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO teams (team_name) VALUES (?)", (team_name,)
            )
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=409, detail=f"'{team_name}' 팀이 이미 존재합니다."
            )
        conn.commit()
    return {"message": "Team saved successfully."}

@app.get("/teams/{member_id}")
def get_team_by_member_id(member_id: int, actor_id: int = Depends(current_member_id)):
    with get_db() as db:
        row = db.execute(
            """
            SELECT m.team_id AS id, t.team_name, t.created_at
            FROM members m
            LEFT JOIN teams t ON t.id = m.team_id
            WHERE m.id = ?
            """,
            (member_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    data = dict(row)
    if data["id"] is None:
        raise HTTPException(
            status_code=404, detail="팀에 소속되지 않은 사용자입니다."
        )
    return data


@app.get("/teams")
def get_teams(actor_id: int = Depends(current_member_id)):
    with get_db() as db:
        teams = db.execute("SELECT * FROM teams").fetchall()

    return [dict(team) for team in teams]


def _issue_text(issue):
    if isinstance(issue, dict):
        return str(issue.get("content") or "").strip()
    return str(issue or "").strip()


def normalize_issues(report_data):
    if isinstance(report_data, str):
        try:
            report_data = json.loads(report_data)
        except json.JSONDecodeError:
            return report_data
    if not isinstance(report_data, dict):
        return report_data
    for project in report_data.get("projects", []):
        if not isinstance(project, dict):
            continue
        completed = [
            str(task).strip()
            for task in (project.get("completedTasks") or [])
            if str(task or "").strip()
        ]
        remaining = []
        seen = set()
        for issue in project.get("issues") or []:
            content = _issue_text(issue)
            if not content:
                continue
            status = (
                str(issue.get("status") or "").strip()
                if isinstance(issue, dict)
                else ""
            )
            if status == "해결":
                if content not in completed:
                    completed.append(content)
                continue
            if content in completed:
                continue
            if content not in seen:
                remaining.append(content)
                seen.add(content)
        project["completedTasks"] = completed
        project["issues"] = remaining
    return report_data


@app.post("/reports/plain")
def save_plain_report(
    data: ReportDraftRequest, actor_id: int = Depends(current_member_id)
):
    """AI를 돌리지 않고 원문을 오늘 보고로 제출한다."""
    require_own_or_admin(actor_id, data.member_id)
    if not str(data.report or "").strip():
        raise HTTPException(status_code=400, detail="보고서 내용을 입력해주세요.")
    return save_report(
        SaveReportData(
            report=data.report,
            parsed_json=json.dumps(plain_parse_daily(data.report), ensure_ascii=False),
            member_id=data.member_id,
            report_date=data.date,
        ),
        actor_id,
    )


@app.post("/reports")
def save_report(data: SaveReportData, actor_id: int = Depends(current_member_id)):
    require_own_or_admin(actor_id, data.member_id)
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
