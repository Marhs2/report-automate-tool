# 일일보고 취합 · 주간보고 자동화 도구

## 요구 사양

모델 **Qwen3.8 27B** Unsloth `UD-Q4_K_XL`, context 32768, 추론 medium 기준:


| 항목   | 최소                     | 권장                  |
| ---- | ---------------------- | ------------------- |
| CPU  | 6코어                    | 8코어 이상              |
| GPU  | NVIDIA 18GB VRAM       | NVIDIA 24GB VRAM 이상 |
| RAM  | 32GB                   | 64GB                |
| OS   | Windows 10/11 , Ubuntu |                     |
| 저장공간 | 25GB 여유                | 40GB 여유             |


(UD-Q4_K_XL 참고: 파일 ≈ 16.67GB, 가중치 VRAM ≈ 17.4GB, 여유 포함 권장 24+GB — [llmrun.dev](https://llmrun.dev/model/qwen-qwen3-8-27b). 운영 퀀트는 `UD-Q4_K_XL`.)

---

## 구성

```
backend/   FastAPI + SQLite (LLM 호출, 구조화·주간보고 생성 API)
frontend/  Vue 3 + Vite (웹 화면)
docs/      모델·도구 선정 근거, 채점 방법
```

- **백엔드**: FastAPI (`backend/main.py`), SQLite (`backend/data/daily_reports.db`)
- **프론트엔드**: Vue 3 + Vite, docx 다운로드는 docxtemplater
- **LLM 런타임**: [Unsloth Desktop](https://unsloth.ai/) (OpenAI 호환 API, `http://127.0.0.1:8888/v1`)
- **채택 모델**: Qwen3.8 27B (`unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`, 추론 medium, context 32768) — [선정 근거](docs/모델-도구-선정-근거.md), [자체 32건](docs/정확도-평가.md)

---



## 설치·실행



### 1) Unsloth (LLM 로컬 서버) 준비

1. [Unsloth Desktop](https://unsloth.ai/) 설치 후 모델을 다운로드.
  - **권장: Qwen3.8 27B** (`unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`, 추론 medium).
  - 선정 근거: [자체 32건](docs/정확도-평가.md), 하드웨어: [llmrun.dev](https://llmrun.dev/model/qwen-qwen3-8-27b), 모델 가이드: [Unsloth Qwen3.8](https://unsloth.ai/docs/models/qwen3.8)
  - **로드**: `unsloth run --model unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL --reasoning medium -c 32768 -p 8888`
  - **추론**: 백엔드는 요청마다 `reasoning_effort: "medium"`을 명시적으로 전송.
  Qwen3.8 27B는 이 필드를 생략하면 기본적으로 추론을 켜므로, 필드 생략 대신 값을 반드시 넣는다.



### 2) 백엔드

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python init_db.py               
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```


| 환경 변수명                | 예시 값                                  | 설명                                       |
| --------------------- | ------------------------------------- | ---------------------------------------- |
| `REPORT_MODEL_NAME`   | `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL` | 사용할 LLM 모델 이름                            |
| `LM_BASE_URL`         | `http://127.0.0.1`                    | LLM API 서버의 기본 URL                       |
| `LM_API_KEY`          | `sk-unsloth-xxxxxxx...`               | LLM API 인증 키                             |
| `DAILY_MAX_TOKENS`    | `32768`                               | 일일보고 구조화/생성 시 사용할 최대 토큰 수                |
| `WEEKLY_MAX_TOKENS`   | `32768`                               | 주간보고 생성 시 사용할 최대 토큰 수                    |
| `DAILY_REASONING`     | `medium`                              | LLM에 전달하는 추론 강도 설정값 (`reasoning_effort`) |
| `WEEKLY_REASONING`    | `medium`                              | 주간보고 구조화/생성 시 사용할 추론 강도 설정값              |
| `KEYWORD_REASONING`   | `medium`                              | 키워드 추출/분류 시 사용할 추론 강도 설정값                |
| `LLM_TIMEOUT_SECONDS` | `600`                                 | LLM 요청 타임아웃 시간 (초)                       |




### 3) 프론트엔드

```bash
cd frontend
bun install
bun run dev        # http://localhost:5173
```



## 기능


| 기능         | 설명                                                                     |
| ---------- | ---------------------------------------------------------------------- |
| 일일보고 작성    | 텍스트 붙여넣기 또는 PPTX 업로드, 작성자·날짜 지정, 원문 초안 복원, 같은 날 덮어쓰기                   |
| 자동 구조화     | 프로젝트별 완료·진행·이슈·협조 요청·다음 계획 추출. 일일 업무가 아니면 빈 결과. 재추출·항목 편집 후 저장, 원문 대조  |
| 일일보고 목록    | 날짜·사람·팀·프로젝트 필터, 삭제                                                    |
| 프로젝트 흐름    | 프로젝트별 타임라인 조회, 등록 이름·키워드로 표기 통일                                        |
| 사용자 활동     | 달력으로 사람별 제출 현황, 주말·공휴일 표시                                              |
| 주간보고       | 주 이동·요일 선택·팀 필터, 프로젝트별 초안 생성(반복 병합, 남은 이슈만 이슈), 같은 기간 덮어쓰기, 요일별 미제출 표시 |
| 주간 편집·내보내기 | 초안 수정·저장, 확인 질문, 화면 복사, 워드(.docx) 다운로드                                 |
| 프로젝트명 관리   | 정식명·키워드 등록, 원문에서 키워드·신규 프로젝트 추천                                        |
| 사용자·팀      | 사용자·팀 생성과 소속 지정                                                                   |


---



## 테스트 데이터

- `test-data/daily-reports.md`(2주치, 인물 4명, 프로젝트 3개)
- 작성 스타일 혼합: 줄글 11, 개조식 9, 메신저체 4, 표 2, 한 줄 2, 영문 혼합 2, 혼합 1, 업무 없음 1

---



## 벤치마크 · 정확도

자체 32건 (`UD-Q4_K_XL`, context 32768, 추론 medium):


| 모델                   | micro F1  | 평균 지연     |
| -------------------- | --------- | --------- |
| **Qwen3.8 27B (채택)** | **89.4%** | **4.82s** |
| Gemma 4 31B-it       | 89.3%     | 5.33s     |
| Muse Glimmer-30B     | 85.0%     | 7.98s     |


채택 이유: Qwen3.8이 micro F1 1위이고 세 모델 중 가장 빠르다. Gemma는 0.1%p 차이고 더 느리다.

- 채점 방법·항목별 표: [정확도 평가](docs/정확도-평가.md)
- 요구사항·도구·운영 조건: [모델·도구 선정 근거](docs/모델-도구-선정-근거.md)

