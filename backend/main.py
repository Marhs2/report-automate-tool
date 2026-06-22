from fastapi import FastAPI
import requests
from openai import OpenAI
import json
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from db import get_db

app = FastAPI()

origins = [
    "http://localhost:5173"
]


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
    parsed_json: dict
    member_id: int


from collections import defaultdict


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
            "nextPlans": []
        }
    )

    for project in report_data["projects"]:

        project_name = guess_project(project)

        project_name = PROJECT_FIX.get(
            project_name,
            project_name
        )

        merged[project_name]["completedTasks"].extend(
            project["completedTasks"]
        )

        merged[project_name]["inProgressTasks"].extend(
            project["inProgressTasks"]
        )

        merged[project_name]["issues"].extend(
            project["issues"]
        )

        merged[project_name]["requests"].extend(
            project["requests"]
        )

        merged[project_name]["nextPlans"].extend(
            project["nextPlans"]
        )

    result = []

    for name, data in merged.items():

        result.append({
            "projectName": name,
            "completedTasks": list(dict.fromkeys(data["completedTasks"])),
            "inProgressTasks": list(dict.fromkeys(data["inProgressTasks"])),
            "issues": list(dict.fromkeys(data["issues"])),
            "requests": list(dict.fromkeys(data["requests"])),
            "nextPlans": list(dict.fromkeys(data["nextPlans"]))
        })

    report_data["projects"] = result

    return report_data

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/model-list")
def read_model_list():
    req = requests.get("http://127.0.0.1:9000/v1/models")
    return req.json()   


@app.post("/send-report")
def send_report(data: ReportRequest ):
    client = OpenAI(base_url="http://127.0.0.1:9000/v1", api_key="llamaCpp")


    completion = client.chat.completions.create(
        model="Qwen3.5-4B-Q4_K_M.gguf",
        messages=[
            {"role": "system", "content": daily_prompt},
            {"role": "user", "content": data.report}
        ],
        temperature=0.1,
        reasoning_effort="medium",
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "daily_report",
                "strict": True,
                "schema": daily_schema
            }
        }
    )
    
    report_data = json.loads(completion.choices[0].message.content)

    report_data = normalize_projects(report_data)

    return report_data


@app.post("/gen_weekly_report")
def gen_weekly_report(data: WeeklyReportRequest ):
    client = OpenAI(base_url="http://127.0.0.1:9000/v1", api_key="llamaCpp")

    completion = client.chat.completions.create(
        model="Qwen3.5-4B-Q4_K_M.gguf",
        messages=[
            {"role": "system", "content": weekly_prompt},
            {"role": "user", "content": "\n".join(data.reports)}
        ],
        temperature=0.1,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "weekly_report",
                "strict": True,
                "schema": weekly_schema
            }
        }
    )
    
    report_data = json.loads(completion.choices[0].message.content)

    report_data = normalize_projects(report_data)

    return report_data


@app.get("/reports")
def get_reports():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, member_id, report_date, raw_text, parsed_json, created_at FROM daily_reports")
        rows = cursor.fetchall()
        reports = []
        for row in rows:
            reports.append({
                "id": row[0],
                "member_id": row[1],
                "report_date": row[2],
                "raw_text": row[3],
                "parsed_json": json.loads(row[4]) if row[4] else None,
                "created_at": row[5]
            })
    return reports


@app.post("/reports")
def save_report(data: SaveReportData):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO daily_reports (raw_text, parsed_json , member_id) VALUES (?, ?, ?)", (data.report, json.dumps(data.parsed_json), data.member_id))
        conn.commit()
    return {"message": "Report saved successfully."}