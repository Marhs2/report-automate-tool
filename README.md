# 일일보고 취합 · 주간보고 자동화 도구

## 요구 사양

모델 **Qwen3.8 27B** Unsloth `UD-Q4_K_XL`, context 32768, 추론 끄기 기준:

| 항목 | 최소 | 권장 |
| --- | --- | --- |
| CPU | 6코어 | 8코어 이상 |
| GPU | NVIDIA 18GB VRAM | NVIDIA 24GB VRAM 이상 |
| RAM | 32GB | 64GB |
| OS | Windows 10/11 , Ubuntu|  |
| 저장공간 | 25GB 여유 | 40GB 여유 |

(Q4_K_M 참고: 파일 ≈ 16.67GB, 가중치 VRAM ≈ 17.4GB, 여유 포함 권장 24+GB — [llmrun.dev](https://llmrun.dev/model/qwen-qwen3-8-27b). 운영 퀀트는 `UD-Q4_K_XL`.)

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
- **채택 모델**: Qwen3.8 27B (`unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`, 추론 끄기, context 32768) — [선정 근거](docs/모델-도구-선정-근거.md), [자체 32건](docs/정확도-평가.md)

---

## 설치·실행

### 1) Unsloth (LLM 로컬 서버) 준비

1. [Unsloth Desktop](https://unsloth.ai/) 설치 후 모델을 다운로드. ([Linux](https://unsloth.ai/download/linux))
   - **권장: Qwen3.8 27B** (`unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`, 추론 끄기).
   - 선정 근거: [자체 32건](docs/정확도-평가.md), 하드웨어: [llmrun.dev](https://llmrun.dev/model/qwen-qwen3-8-27b), 모델 가이드: [Unsloth Qwen3.8](https://unsloth.ai/docs/models/qwen3.8)
   - **로드 시 추론 끄기**: `unsloth run --model unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL --reasoning off -c 32768 -p 8888`
   - **API 키**: Unsloth 아바타 → Settings → API에서 키 생성 (`sk-unsloth-…`). OpenAI 호환 엔드포인트는 `http://127.0.0.1:8888/v1` ([API 문서](https://unsloth.ai/docs/basics/api))
   - **추론 차단**: 백엔드는 요청마다 `reasoning_effort: "none"`을 명시적으로 전송.
     Qwen3.8 27B는 이 필드를 생략하면 기본적으로 추론을 켜므로, 필드 생략 대신 `none`이 반드시 필요.

### 2) 백엔드

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python init_db.py               
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

환경 변수 (선택, 기본값으로도 동작):

| 변수                | 기본값                     | 설명                                                                                                                                                                                                                                                                                 |
| ------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `REPORT_MODEL_NAME` | `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL` | Unsloth에 로드한 모델명. **Qwen3.8 27B `UD-Q4_K_XL`(기본)** — context 32768 ([선정 근거](docs/모델-도구-선정-근거.md), [자체 32건](docs/정확도-평가.md)) |
| `LM_BASE_URL`       | `http://127.0.0.1:8888/v1` | Unsloth OpenAI 호환 API 주소 ([API 문서](https://unsloth.ai/docs/basics/api)) |
| `LM_API_KEY`        | `sk-unsloth-…`            |  |
| `DAILY_MAX_TOKENS`  | `32768`| 일일 구조화 출력 상한|
| `WEEKLY_MAX_TOKENS` | `32768`| 주간보고 생성 출력 상한|
| `DAILY_REASONING`   | `none`                     | `none`/`low`/`medium`/`high`. 기본 `none` = 요청에 `reasoning_effort:"none"`을 명시적으로 실어 추론을 끈다(필드 생략은 Unsloth/Qwen이 추론을 켜므로 금지). Qwen3.8 27B는 추론 끄고 사용.  |

### 3) 프론트엔드

```bash
cd frontend
bun install
bun run dev        # http://localhost:5173
```

## 기능

| 기능               | 설명                                                                                                |
| ------------------ | --------------------------------------------------------------------------------------------------- |
| 일일보고 입력      | 자유 텍스트(붙여넣기 포함), 작성자·날짜 지정, 같은 날 덮어쓰기                                      |
| 자동 구조화        | 프로젝트명·완료·진행·이슈·협조 요청·다음 계획 추출, 복수 프로젝트 분리, 원문 보존·대조              |
| 모아 보기          | 날짜별 / 사람별 / 프로젝트별(타임라인) 조회, 프로젝트명·키워드로 표기 통일                                   |
| 주간보고 초안      | 기간 선택(주 이동), 프로젝트별 정리, 반복 업무 병합, 남은 이슈만 이슈로 남김, 같은 기간 재생성 시 덮어쓰기 |
| 초안 편집·내보내기 | 초안 수정 후 저장, 화면 복사, 워드(.docx) 다운로드                                                  |
| 미제출 표시        | 사람별·요일별 제출 현황 (주간보고 화면 상단)                                                        |

---

## 테스트 데이터

- `test-data/daily-reports.md`(2주치, 인물 4명, 프로젝트 3개)
- 작성 스타일 혼합: 줄글 11, 개조식 9, 메신저체 4, 표 2, 한 줄 2, 영문 혼합 2, 혼합 1, 업무 없음 1

---

## 벤치마크 · 정확도

자체 32건 (`UD-Q4_K_XL`, context 32768, 추론 끄기):

| 모델 | micro F1 | 평균 지연 |
| --- | ---: | ---: |
| Gemma 4 31B-it | 87.9% | 5.66s |
| Muse Glimmer-30B | 87.5% | 8.63s |
| **Qwen3.8 27B (채택)** | 86.4% | **0.85s** |

채택 이유: F1은 Gemma가 1.5%p 높지만 Qwen3.8이 약 7배 빠르고 빈 보고를 모두 맞춘다.

- 채점 방법·항목별 표: [정확도 평가](docs/정확도-평가.md)
- 요구사항·도구·운영 조건: [모델·도구 선정 근거](docs/모델-도구-선정-근거.md)
- 공개 벤치 참고: [model.md](model.md)
