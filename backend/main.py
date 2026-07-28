import json
import os
from collections import defaultdict
from datetime import date, timedelta

from db import get_db
from fastapi import FastAPI, Request
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

with open("./model_asset/prompt.txt", "r", encoding="utf-8") as f:
    daily_prompt = f.read()

with open("./model_asset/weekly_json_schema.json", "r", encoding="utf-8") as f:
    weekly_schema = json.load(f)

with open("./model_asset/weekly_prompt.txt", "r", encoding="utf-8") as f:
    weekly_prompt = f.read()

MODEL_NAME = os.environ.get("REPORT_MODEL_NAME", "nuextract3")
LM_BASE_URL = os.environ.get("LM_BASE_URL", "http://127.0.0.1:1234/v1")
LM_API_KEY = os.environ.get("LM_API_KEY", "lm-studio")


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


def guess_project(project):
    issues = [
        issue["content"] if isinstance(issue, dict) else issue
        for issue in project.get("issues", [])
    ]

    text = " ".join(
        project.get("completedTasks", [])
        + project.get("inProgressTasks", [])
        + issues
        + project.get("requests", [])
        + project.get("nextPlans", project.get("nextWeekPlans", []))
    )

    for keyword, target in KEYWORD_FIX.items():
        if keyword in text:
            return target

    # 키워드가 없으면 원래 프로젝트명 유지
    return project["projectName"]


def normalize_projects(report_data):
    merged = defaultdict(
        lambda: {
            "completedTasks": [],
            "inProgressTasks": [],
            "issues": [],
            "requests": [],
            "nextPlans": [],
        }
    )

    for project in report_data["projects"]:
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

        project_name = guess_project(project)
        project_name = PROJECT_FIX.get(project_name, project_name)

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


@app.post("/weekly-report")
def weekly_report(data: WeeklyReportRequest):
    with get_db() as db:
        res = db.execute(
            "SELECT parsed_json FROM daily_reports WHERE member_id = ? AND report_date IN ({})".format(
                ",".join(["?"] * len(data.selects))
            ),
            (data.userId, *data.selects),
        ).fetchall()

        reports = [json.loads(row[0]) for row in res]

        client = OpenAI(base_url=LM_BASE_URL, api_key=LM_API_KEY)

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": weekly_prompt},
                {"role": "user", "content": json.dumps(reports)},
            ],
            temperature=0.1,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "weekly_report",
                    "strict": True,
                    "schema": weekly_schema,
                },
            },
        )

        content = completion.choices[0].message.content
        print(len(content))
        print(content[-1000:])
        if content is None:
            content = "{}"
        report_data = json.loads(content)

        report_data = normalize_projects(report_data)

        db.execute(
            "INSERT INTO weekly_reports (member_id, selected_date, report_json) VALUES (?, ?, ?)",
            (data.userId, json.dumps(data.selects), json.dumps(report_data)),
        )

        return report_data


@app.post("/send-report")
async def send_report(request: Request, data: ReportRequest):
    body = await request.json()
    print(f"[send-report] raw body: {body}")
    print(f"[send-report] validated data.report: {repr(data.report)}")
    client = OpenAI(base_url=LM_BASE_URL, api_key=LM_API_KEY)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": daily_prompt},
                {"role": "user", "content": data.report},
            ],
            temperature=0.1,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "daily_report",
                    "strict": True,
                    "schema": daily_schema,
                },
            },
        )

        content = completion.choices[0].message.content
        if content is None:
            content = "{}"
        report_data = json.loads(content)

        save_projects(report_data, data.member_id)

        return report_data
    except Exception as e:
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            print(f"[send-report] upstream status={resp.status_code} body={body}")
        else:
            print(f"[send-report] error: {e}")
        raise


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
            SELECT report_date, member_id, COUNT(id)
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


@app.get("/reports")
def get_reports():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, member_id, report_date, raw_text, parsed_json, created_at FROM daily_reports"
        )
        rows = cursor.fetchall()
        reports = []
        for row in rows:
            parsed = json.loads(row[4]) if row[4] else None
            if parsed:
                parsed = normalize_issues(parsed)
            reports.append(
                {
                    "id": row[0],
                    "member_id": row[1],
                    "report_date": row[2],
                    "raw_text": row[3],
                    "parsed_json": parsed,
                    "created_at": row[5],
                }
            )
    return reports


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


@app.post("/users")
def save_user(data: UserRequest):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO members (name) VALUES (?)",
            (data.name,),
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
            "SELECT id FROM daily_reports WHERE member_id = ? AND report_date = ?",
            (member_id, report_date),
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "UPDATE daily_reports SET raw_text = ?, parsed_json = ? WHERE id = ?",
                (raw_text, json.dumps(parsed), existing["id"]),
            )
            cursor.execute("DELETE FROM projects WHERE member_id = ?", (member_id,))
        else:
            cursor.execute(
                "INSERT INTO daily_reports (member_id, report_date, raw_text, parsed_json) VALUES (?, ?, ?, ?)",
                (member_id, report_date, raw_text, json.dumps(parsed)),
            )

        conn.commit()
        save_projects(parsed, member_id)
    return {"message": "Report saved successfully.", "report_date": report_date}


def save_projects(report_data, member_id):
    with get_db() as conn:
        cursor = conn.cursor()

        print(report_data["projects"])

        for project in report_data["projects"]:
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
                    project["projectName"],
                    json.dumps(project["completedTasks"]),
                    json.dumps(project["inProgressTasks"]),
                    json.dumps(project["issues"]),
                    json.dumps(project["requests"]),
                    json.dumps(project["nextPlans"]),
                ),
            )

        conn.commit()
