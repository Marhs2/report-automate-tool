# 모델 벤치마크 및 선정 근거

> 대상: **텍스트 일일보고 → JSON 구조화** (이미지 OCR 아님).
> 자체 32건 채점 방법·항목별 표는 [docs/정확도-평가.md](docs/정확도-평가.md).
> 이 문서는 그 측정으로 모델을 고른 이유와, 참고용 공개 벤치를 같이 적는다.

## 결론

현재 기본 모델은 **Qwen3.8 27B** (`unsloth/Qwen3.8-27B-GGUF:Q4_K_M`)이다.

운영 전제: **추론 끄기** (`reasoning_effort: none`) + JSON 스키마 강제 + context **32768**.
기본 thinking은 짧은 추출에서 불필요하게 길어진다.

자체 32건에서 Gemma 4 31B-it의 micro F1이 1.5%p 높지만(87.9% vs 86.4%),
Qwen3.8은 평균 **0.85s**(Gemma 5.66s, Muse 8.63s)이고 빈 보고 2건을 모두 맞춘다.
프로젝트 매칭도 Qwen3.8이 가장 높다(98.8%).

## 실행 조건

- 측정일: 2026-09-14
- 데이터: `test-data/daily-reports.md` 32건
- 런타임: Unsloth  `http://127.0.0.1`
- 퀀트: `Q4_K_M`, context 32768, temperature 0.1, max_tokens 6144
- 비교: Qwen3.8-27B, Gemma 4 31B-it, Muse Glimmer-30B
- 추론: `none`

## 자체 32건

| 순위 | 모델 | JSON | micro F1 | 프로젝트 F1 | 빈 보고 | 평균 지연 | tok/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Gemma 4 31B-it | 100% | **87.9%** | 96.5% | 50% | 5.66s | 145.8 |
| 2 | Muse Glimmer-30B | 100% | 87.5% | 97.6% | 50% | 8.63s | 157.5 |
| 3 | **Qwen3.8 27B** | 100% | 86.4% | **98.8%** | **100%** | **0.85s** | 121.4 |

항목별 F1:

| 모델 | 완료 | 진행 중 | 이슈 | 협조 요청 | 다음 계획 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gemma 4 31B-it | 91.5% | 76.2% | **100%** | **100%** | 78.4% |
| Muse Glimmer-30B | 91.3% | **82.6%** | 92.3% | **100%** | 78.4% |
| **Qwen3.8 27B** | 91.1% | 77.5% | 91.9% | 85.7% | **82.6%** |

세 모델 모두 API 오류·잘림 없음. 스키마 JSON은 전부 통과했다.

## 선정 판단

### Qwen3.8 27B (채택)

- 지연 0.85s. 같은 32건에서 Gemma 대비 약 7배, Muse 대비 약 10배 빠름
- 빈 보고(`projects: []`) 2/2, 프로젝트 F1 98.8%
- 영문 혼합 2건 F1은 63.3%로 약함. 개조식도 Gemma보다 낮음
- 한계: 기본 thinking이 과함. 요청마다 `reasoning_effort: "none"` 필수

### Gemma 4 31B-it

- micro F1 최고, 이슈·요청 100%, 개조식 92.6%
- 평균 5.66s, 빈 보고 50%(한 줄을 업무로 채움)
- 이 파이프라인에서는 JSON 스키마가 동작했다(32/32). 운영 기본값으로는 지연 때문에 두지 않음

### Muse Glimmer-30B

- F1 87.5%로 Gemma와 비슷, 진행 중 업무 F1은 세 모델 중 최고(82.6%)
- 평균 8.63s로 가장 느리고 빈 보고도 50%
- 추출 기본값으로는 채택하지 않음

## 운영 전제

1. thinking **off**
2. `response_format` / JSON 스키마로 출력 고정
3. 없는 필드는 `[]`. 발명 금지
4. 로드: `unsloth run --model unsloth/Qwen3.8-27B-GGUF:Q4_K_M --reasoning off -c 32768 -p 8888`

---

## 참고: 공개 벤치

한국어 일일보고 JSON 공개 벤치는 없다. 선정에는 쓰지 않았고, 체급 감만 볼 때 아래를 참고한다.

| 지표 | 이 작업과의 거리 |
| --- | --- |
| IFBench | 형식·제약 준수. 스키마 JSON과 제일 가깝다 |
| Kingy 툴콜 | 선언된 필드만 채우기 |
| Kingy 문서 QA | 텍스트에서 값 추출 |

| 순위 | 모델 | IFBench | 출처 |
| --- | --- | ---: | --- |
| 1 | Qwen3.8-27B | 79.5 | Qwen 모델 카드 |
| 2 | Muse Glimmer-30B | 77.0 | Qwen 모델 카드 비교열 |
| 3 | Gemma 4 31B | 75.6 | OrcaRouter / Artificial Analysis |


출처: [Artificial Analysis](https://artificialanalysis.ai/models/qwen3-8-27b), [Kingy](https://kingy.ai/blog/qwen3-8-27b-vs-qwen3-6-27b-vs-gemma-4-31b/), [Muse Glimmer AA](https://artificialanalysis.ai/models/muse-glimmer), [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B).
