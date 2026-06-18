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

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO daily_reports (member_id, raw_text, parsed_json) VALUES (?, ?, ?)",
            (1, data.report, json.dumps(report_data))
        )
        conn.commit()
    

    return json.loads(completion.choices[0].message.content)



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
    
    return json.loads(completion.choices[0].message.content)


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