import json
import os
import sqlite3
from collections import defaultdict
from datetime import date, timedelta

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

with open("./model_asset/json_Schema.json", "r", encoding="utf-8") as f:
    daily_schema = json.load(f)

def get_known_projects_block():
    """DB의 projects/aliases로 {{KNOWN_PROJECTS}} 슬롯을 채운다.

    prompt.txt 의 [C0] 등록된 프로젝트 목록 형식과 맞춘다.
    등록된 프로젝트가 없으면 빈 문장을 돌려주고, 사용자는 원문에서 직접 판단한다.
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT name FROM projects WHERE name IS NOT NULL AND TRIM(name) != ''"
        ).fetchall()
        aliases = conn.execute(
            "SELECT alias_name, canonical_name FROM project_aliases"
        ).fetchall()
    names = sorted({r[0] for r in rows})
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


with open("./model_asset/prompt.txt", "r", encoding="utf-8") as f:
    daily_prompt = f.read()

with open("./model_asset/weekly_json_schema.json", "r", encoding="utf-8") as f:
    weekly_schema = json.load(f)

with open("./model_asset/weekly_prompt.txt", "r", encoding="utf-8") as f:
    weekly_prompt = f.read()

MODEL_NAME = os.environ.get("REPORT_MODEL_NAME", "nuextract3")
LM_BASE_URL = os.environ.get("LM_BASE_URL", "http://127.0.0.1:1234/v1")
LM_API_KEY = os.environ.get("LM_API_KEY", "lm-studio")

# 출력 토큰 상한. 지정하지 않으면 LM Studio가 컨텍스트가 찰 때까지 계속 생성한다.
DAILY_MAX_TOKENS = int(os.environ.get("DAILY_MAX_TOKENS", "1024"))
WEEKLY_MAX_TOKENS = int(os.environ.get("WEEKLY_MAX_TOKENS", "2048"))
# reasoning_effort: none|low|medium|high. 기본은 none(끔).
# 벤치마크상 기존 32건은 high가 +2.7pp, 신규 데이터셋은 -3.7pp라 기본값은 none이 안전하다.
DAILY_REASONING = os.environ.get("DAILY_REASONING", "none") or None


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


def coerce_report_data(content):
    """LLM 응답을 안전하게 파싱한다. 실패하거나 형식이 어긋나면 빈 결과를 돌려준다."""
    if not content or not str(content).strip():
        return {"projects": []}
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        print(f"[coerce_report_data] JSON 파싱 실패: {content[:200]}")
        return {"projects": []}
    if not isinstance(data, dict):
        print(f"[coerce_report_data] dict 아님: {type(data)}")
        return {"projects": []}
    projects = data.get("projects")
    if not isinstance(projects, list):
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


@app.get("/")
def read_root():
    return {"Hello": "World"}


# ─── 프로젝트별 타임라인 조회 ────────────────────────────────────────


@app.get("/project-names")
def get_project_names():
    """모든 보고서에서 등장한 고유 프로젝트명 목록 (정규화 적용)."""
    alias_map = get_alias_map()
    with get_db() as conn:
        rows = conn.execute("SELECT parsed_json FROM daily_reports").fetchall()

    names = set()
    for row in rows:
        parsed = coerce_report_data(row[0])
        for project in parsed.get("projects", []):
            canonical = guess_project(project, alias_map)
            if canonical:
                names.add(canonical)

    return sorted(names)


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


@app.post("/weekly-report")
def weekly_report(data: WeeklyReportRequest):
    if not data.selects:
        raise HTTPException(
            status_code=400, detail="기간(날짜)을 최소 1개 선택해주세요."
        )

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
            """.format(",".join(["?"] * len(data.selects))),
            (data.userId, *data.selects),
        ).fetchall()

        if not res:
            raise HTTPException(
                status_code=404,
                detail="선택한 기간에 저장된 일일보고가 없습니다.",
            )

        reports = [coerce_report_data(row[0]) for row in res]

        client = OpenAI(base_url=LM_BASE_URL, api_key=LM_API_KEY)

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": weekly_prompt},
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

        content = read_completion(completion, "weekly-report")
        report_data = coerce_report_data(content)

        report_data = normalize_projects(report_data)

        db.execute(
            "INSERT INTO weekly_reports (member_id, selected_date, report_json) VALUES (?, ?, ?)",
            (data.userId, json.dumps(data.selects), json.dumps(report_data)),
        )
        db.commit()

        return report_data


@app.post("/send-report")
async def send_report(data: ReportRequest):
    client = OpenAI(base_url=LM_BASE_URL, api_key=LM_API_KEY)
    try:
        max_tokens = 16384 if DAILY_REASONING else DAILY_MAX_TOKENS
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
        report_data = coerce_report_data(content)

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


@app.get("/user-activities")
def get_user_activities(year: int, month: int):
    first_day = date(year, month, 1)
    last_day_of_month = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(
        days=1
    )

    start_date = first_day.isoformat()
    end_date = last_day_of_month.isoformat()

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
        while current <= last_day_of_month:  # 수정
            report_date = current.isoformat()

            activities.append(
                {
                    "report_date": report_date,
                    "count": counts[member_id].get(report_date, 0),
                }
            )

            current += timedelta(days=1)

        activities.reverse()

        result.append({"member_id": member_id, "name": name, "activities": activities})
    return result


@app.get("/weekly")
def get_weekly():
    with get_db() as db:
        rows = db.execute("""
            SELECT w.id, w.member_id, m.name, w.selected_date, w.report_json, w.created_at
            FROM weekly_reports w
            LEFT JOIN members m ON w.member_id = m.id
        """).fetchall()

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

    report_date = data.report_date or date.today().isoformat()
    raw_text = data.report
    member_id = data.member_id

    with get_db() as conn:
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

        cursor.execute("DELETE FROM projects WHERE member_id = ?", (member_id,))
        conn.commit()
        save_projects(parsed, member_id)
    return {"message": "Report saved successfully.", "report_date": report_date}


def save_projects(report_data, member_id):
    with get_db() as conn:
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
                    next_plans
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member_id,
                    project.get("projectName") or "미분류 프로젝트",
                    json.dumps(project.get("completedTasks", [])),
                    json.dumps(project.get("inProgressTasks", [])),
                    json.dumps(project.get("issues", [])),
                    json.dumps(project.get("requests", [])),
                    json.dumps(project.get("nextPlans", [])),
                ),
            )

        conn.commit()
