from fastapi import FastAPI
import requests
from openai import OpenAI
import json
from pydantic import BaseModel

app = FastAPI()

with open("./model_asset/json_Schema.json", "r", encoding="utf-8") as f:
    schema = json.load(f)

with open("./model_asset/prompt.txt", "r", encoding="utf-8") as f:
    prompt = f.read()


class ReportRequest(BaseModel):
    report: str

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/model-list")
def read_model_list():
    req = requests.get("http://localhost:1234/v1/models")
    return req.json()


@app.post("/send-report")
def send_report(data: ReportRequest ):
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    replaced_report = " ".join(data.report.split())



    completion = client.chat.completions.create(
        model="google/gemma-4-e2b",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": data.report}
        ],
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "daily_report",
                "strict": True,
                "schema": schema
            }
        }
    )





    return  {completion.choices[0].message.content}

