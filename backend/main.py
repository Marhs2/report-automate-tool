from fastapi import FastAPI
import requests
from openai import OpenAI
import json
from pydantic import BaseModel

app = FastAPI()

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
    req = requests.get("http://localhost:1234/v1/models")
    return req.json()   


@app.post("/send-report")
def send_report(data: ReportRequest ):
    client = OpenAI(base_url="http://localhost:9000", api_key="llamaCpp")


    completion = client.chat.completions.create(
        model="local-model",
        messages=[
            {"role": "system", "content": daily_prompt},
            {"role": "user", "content": data.report}
        ],
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "daily_report",
                "strict": True,
                "schema": daily_schema
            }
        }
    )

    return  {completion.choices[0].message.content}



@app.post("/gen_weekly_report")
def gen_weekly_report(data: WeeklyReportRequest ):
    client = OpenAI(base_url="http://localhost:9000", api_key="llamaCpp")

    completion = client.chat.completions.create(
        model="local-model",
        messages=[
            {"role": "system", "content": weekly_prompt},
            {"role": "user", "content": "\n".join(data.reports)}
        ],
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "weekly_report",
                "strict": True,
                "schema": weekly_schema
            }
        }
    )
    
    return  {completion.choices[0].message.content}

