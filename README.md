# 일일보고 취합 · 주간보고 자동화 도구

일일보고를 붙여넣으면 로컬 LLM이 프로젝트별로 정리하고, 한 주치를 모아 주간보고 초안과 PPT를 만든다. 회의 녹음 받아쓰기·요약도 된다. LLM과 음성 인식은 사내 PC에서만 돌린다.

## 요구 사양

| 항목   | 최소              | 권장          |
| ---- | --------------- | ----------- |
| GPU  | NVIDIA 18GB VRAM | 24GB 이상     |
| RAM  | 32GB            | 64GB        |
| 저장공간 | 25GB            | 40GB        |
| OS   | Windows 10/11, Ubuntu |       |

모델: Qwen3.8 27B (`unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`), 음성 인식: `qwen3-asr-1.7b`. 선정 근거는 [docs/모델-도구-선정-근거.md](docs/모델-도구-선정-근거.md), 정확도는 [docs/정확도-평가.md](docs/정확도-평가.md).

## 실행

### 1) LLM 서버 (Unsloth)

```bash
unsloth run --model unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL --reasoning medium -c 32768 -p 8888
```

회의 녹음을 쓰려면 Unsloth Studio 설정 > Voice에서 `qwen3-asr-1.7b`를 내려받는다.

### 2) 백엔드 (반드시 `backend/`에서 실행)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python init_db.py               # 첫 관리자: 관리자 / admin1234
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

`.env` 주요 값:

| 변수 | 예시 |
| --- | --- |
| `LM_BASE_URL` | `http://127.0.0.1:8888/v1` (로컬·사설망 주소만 허용) |
| `LM_API_KEY` | Unsloth API 키 |
| `REPORT_MODEL_NAME` | `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL` |
| `DAILY_REASONING` / `WEEKLY_REASONING` / `KEYWORD_REASONING` | `medium` (`none`이면 추론 끔) |

`.env.example`은 `BASE_URL` / `API_KEY`로 적혀 있으니 `LM_BASE_URL` / `LM_API_KEY`로 이름을 바꿔 적는다.

### 3) 프론트엔드

```bash
cd frontend
bun install
bun run dev        # https://localhost:5173
```

마이크 때문에 자체 서명 https로 열린다. 처음 접속할 때 인증서 경고를 넘긴다.

## 기능

- **오늘**: 일일보고 작성(붙여넣기·PPTX 업로드), 프로젝트별 자동 정리와 편집
- **팀**: 부서 제출 현황, 검색·필터, 제출 기록, 프로젝트 흐름, 주간 취합 PPT
- **주간**: 한 주 일일보고로 초안 생성, 편집, 워드·PPT 다운로드
- **다른 보고**: 회의록(녹음 → 받아쓰기 → 요약), 영업보고
- **설정·관리**: 부서, 프로젝트명, 사용자·팀장 지정
