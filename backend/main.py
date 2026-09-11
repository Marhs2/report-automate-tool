import io
import json
import re
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import urlparse

from db import get_db
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pptx_to_text import extract_all_text_from_pptx
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


with open("./model_asset/weekly_json_schema.json", "r", encoding="utf-8") as f:
    weekly_schema = json.load(f)

with open("./model_asset/keyword_json_schema.json", "r", encoding="utf-8") as f:
    keyword_schema = json.load(f)

MODEL_NAME = "unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_M"
LM_BASE_URL = "http://192.168.210.10:8888/v1"
LM_API_KEY = "lm-studio"
LLM_TIMEOUT_SECONDS = 600.0

DAILY_MAX_TOKENS = 262144
WEEKLY_MAX_TOKENS = 262144
KEYWORD_MAX_TOKENS = 4096
DAILY_REASONING = "none"
WEEKLY_REASONING = "none"
KEYWORD_REASONING = "none"

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


class KeywordRecommendRequest(BaseModel):
    report: str


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
        conn.execute("DROP TABLE IF EXISTS project_aliases")
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
    return data


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


def drop_empty_projects(report_data):
    if not isinstance(report_data, dict):
        return {"projects": []}
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
            plan_tokens = _weekly_task_tokens(plan) - _WEEKLY_GENERIC_ACTIONS
            if not plan_tokens:
                return False
            for completed_task in completed_candidates:
                if _weekly_tasks_match(plan, completed_task):
                    return True
                done_tokens = _weekly_task_tokens(completed_task) - _WEEKLY_GENERIC_ACTIONS
                if plan_tokens & done_tokens:
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
    item_tokens = _weekly_task_tokens(item) - _WEEKLY_GENERIC_ACTIONS
    for candidate in candidates:
        if _weekly_tasks_match(item, candidate):
            return True
        cand_tokens = _weekly_task_tokens(candidate) - _WEEKLY_GENERIC_ACTIONS
        if item_tokens and item_tokens & cand_tokens:
            return True
    return False


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


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/project-timeline")
def get_project_timeline(name: str, member_id: int = None):
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
def get_project_names():
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
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name, keywords, created_at FROM known_projects ORDER BY name"
        ).fetchall()
    return [
        {"name": row[0], "keywords": row[1] or "", "created_at": row[2]} for row in rows
    ]


@app.post("/project-names")
def create_project_name(data: ProjectNameRequest):
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
    if KEYWORD_REASONING:
        kwargs["reasoning_effort"] = KEYWORD_REASONING
    completion = client.chat.completions.create(**kwargs)
    return read_completion(completion, "recommend-keywords")


@app.post("/project-names/recommend")
def recommend_project_keywords(data: KeywordRecommendRequest):
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
                    {"role": "user", "content": json.dumps(reports, ensure_ascii=False)},
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
            if WEEKLY_REASONING:
                kwargs["reasoning_effort"] = WEEKLY_REASONING
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
            report_data = drop_empty_projects(report_data)
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

        db.execute(
            "DELETE FROM weekly_reports WHERE member_id = ? AND selected_date = ?",
            (member_id, json.dumps(selects)),
        )
        db.execute(
            "INSERT INTO weekly_reports (member_id, selected_date, report_json) VALUES (?, ?, ?)",
            (member_id, json.dumps(selects), json.dumps(report_data, ensure_ascii=False)),
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


def process_daily_report(report: str, report_date: str, member_id: int):
    if not report.strip():
        raise HTTPException(status_code=400, detail="보고서 내용을 입력해주세요.")
    report_date = validate_report_date(report_date)

    with get_db() as conn:
        validate_member(conn, member_id)
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
                {"role": "user", "content": report},
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
        if DAILY_REASONING:
            kwargs["reasoning_effort"] = DAILY_REASONING
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
async def send_report(data: ReportRequest):
    return process_daily_report(data.report, data.date, data.member_id)


@app.post("/send-report-pptx")
async def send_report_pptx(
    file: UploadFile = File(...),
    date: str = Form(...),
    member_id: int = Form(...),
):
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

    for member_id, name in members:
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
