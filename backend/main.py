import json
from collections import defaultdict

import requests
from db import get_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI()

origins = ["http://localhost:5173"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
    reports: list[str]


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
    text = " ".join(
        project["completedTasks"]
        + project["inProgressTasks"]
        + project["issues"]
        + project["requests"]
        + project["nextPlans"]
    )
    for keyword, target in KEYWORD_FIX.items():
        if keyword in text:
            return target
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
        project_name = guess_project(project)

        project_name = PROJECT_FIX.get(project_name, project_name)

        merged[project_name]["completedTasks"].extend(project["completedTasks"])

        merged[project_name]["inProgressTasks"].extend(project["inProgressTasks"])

        merged[project_name]["issues"].extend(project["issues"])

        merged[project_name]["requests"].extend(project["requests"])

        merged[project_name]["nextPlans"].extend(project["nextPlans"])

    result = []

    for name, data in merged.items():
        result.append(
            {
                "projectName": name,
                "completedTasks": list(dict.fromkeys(data["completedTasks"])),
                "inProgressTasks": list(dict.fromkeys(data["inProgressTasks"])),
                "issues": list(dict.fromkeys(data["issues"])),
                "requests": list(dict.fromkeys(data["requests"])),
                "nextPlans": list(dict.fromkeys(data["nextPlans"])),
            }
        )

    report_data["projects"] = result

    return report_data


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/model-list")
def read_model_list():
    req = requests.get("http://127.0.0.1:1234/v1/models")
    return req.json()


@app.post("/send-report")
def send_report(data: ReportRequest):
    client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")

    completion = client.chat.completions.create(
        model="nuextract3",
        messages=[
            {"role": "system", "content": daily_prompt},
            {"role": "user", "content": data.report},
        ],
        temperature=0.1,
        response_format={
            "type": "json_schema",
            "reasoning_effort": "max",
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

    report_data = normalize_projects(report_data)

    return report_data


@app.get("/reports/status")
def get_report_status(report_date: str):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT m.id, m.name,
                   CASE WHEN dr.id IS NULL THEN 0 ELSE 1 END AS submitted
            FROM members m
            LEFT JOIN daily_reports dr
                ON dr.member_id = m.id AND dr.report_date = ?
            """,
            (report_date,),
        )
        rows = cursor.fetchall()
        return [
            {"member_id": r[0], "name": r[1], "submitted": bool(r[2])} for r in rows
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
                    "important_summary": row[8],
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
                    next_plans,
                    important_summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member_id,
                    project["projectName"],
                    json.dumps(project["completedTasks"]),
                    json.dumps(project["inProgressTasks"]),
                    json.dumps(project["issues"]),
                    json.dumps(project["requests"]),
                    json.dumps(project["nextPlans"]),
                    report_data["importantSummary"],
                ),
            )

        conn.commit()
