import json
from collections import defaultdict
from datetime import date, timedelta

from db import get_db
from fastapi import FastAPI
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


class ReportRequest(BaseModel):
    report: str


class WeeklyReportRequest(BaseModel):
    userId: int
    selects: list[str]


class SaveReportData(BaseModel):
    report: str
    parsed_json: str
    member_id: int


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

        # 모든 항목이 비어있는 프로젝트는 병합 전에 배제
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
                # issue가 딕셔너리인 경우와 일반 문자열인 경우 모두 처리
                if isinstance(issue, dict):
                    if any(issue.values()):
                        unique_issues.append(issue)
                elif str(issue).strip():
                    unique_issues.append(issue)

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

        # 모든 리스트가 비어있으면 결과에 추가하지 않고 제외 (이름만 있는 경우 삭제)
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

        client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

        completion = client.chat.completions.create(
            model="models--lmstudio-community--gemma-4-12b-it-qat",
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
def send_report(data: ReportRequest):
    client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

    completion = client.chat.completions.create(
        model="models--lmstudio-community--gemma-4-12b-it-qat",
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

    return report_data


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
            reports.append(
                {
                    "id": row[0],
                    "member_id": row[1],
                    "report_date": row[2],
                    "raw_text": row[3],
                    "parsed_json": json.loads(row[4]) if row[4] else None,
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


@app.post("/reports")
def save_report(data: SaveReportData):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO daily_reports (raw_text, parsed_json , member_id) VALUES (?, ?, ?)",
            (data.report, json.dumps(data.parsed_json), data.member_id),
        )
        conn.commit()
        save_projects(json.loads(data.parsed_json), data.member_id)
    return {"message": "Report saved successfully."}


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
