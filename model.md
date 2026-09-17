# 모델 벤치마크 및 선정 근거

> 대상: **텍스트 일일보고 → JSON 구조화**.
> 자체 32건 채점 방법·항목별 표는 [docs/정확도-평가.md](docs/정확도-평가.md).
> 이 문서는 그 측정으로 모델을 고른 이유와, 참고용 공개 벤치를 같이 적는다.

## 결론

현재 기본 모델은 **Qwen3.8 27B** (`unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`)이다.

운영 전제: **추론 medium** (`reasoning_effort: medium`) + JSON 스키마 강제 + context **32768**.

자체 32건에서 Qwen3.8의 micro F1이 가장 높고(89.4% vs Gemma 89.3%),
평균 **4.82s**(Gemma 5.33s, Muse 7.98s)로 가장 빠르다.
프로젝트 매칭도 Qwen3.8이 가장 높다(96.5%). Muse는 JSON 1건이 깨졌다(96.9%).

## 실행 조건

- 측정일: 2026-09-17
- 데이터: `test-data/daily-reports.md` 32건
- 런타임: Unsloth  `http://127.0.0.1`
- 퀀트: `UD-Q4_K_XL`, context 32768, temperature 0.1, max_tokens 6144
- 비교: Qwen3.8-27B, Gemma 4 31B-it, Muse Glimmer-30B
- 추론: `medium`

## 자체 32건

| 순위 | 모델 | JSON | micro F1 | 프로젝트 F1 | 빈 보고 | 평균 지연 | tok/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | **Qwen3.8 27B** | 100% | **89.4%** | **96.5%** | 50% | **4.82s** | 147.8 |
| 2 | Gemma 4 31B-it | 100% | 89.3% | 94.2% | 50% | 5.33s | 133.7 |
| 3 | Muse Glimmer-30B | 96.9% | 85.0% | 92.7% | 50% | 7.98s | 154.4 |

항목별 F1:

| 모델 | 완료 | 진행 중 | 이슈 | 협조 요청 | 다음 계획 |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Qwen3.8 27B** | **93.8%** | 84.4% | **97.4%** | **100%** | 77.8% |
| Gemma 4 31B-it | 91.7% | **88.4%** | 92.3% | **100%** | 80.8% |
| Muse Glimmer-30B | 85.7% | 73.5% | 91.9% | **100%** | **86.3%** |

세 모델 모두 API 오류·잘림 없음. Qwen·Gemma 스키마 JSON은 전부 통과했다. Muse는 1건 실패.

## 선정 판단

### Qwen3.8 27B (채택)

- micro F1 89.4%로 1위. 재현율 92.4%, 이슈 97.4%, 완료 93.8%
- 지연 4.82s. 같은 32건에서 Gemma·Muse보다 짧음
- 프로젝트 F1 96.5%, JSON 100%
- 영문 혼합 2건 F1은 68.5%로 약함. 다음 계획(77.8%)·한 줄(50%)도 약함
- 요청마다 `reasoning_effort: "medium"`을 명시

### Gemma 4 31B-it

- micro F1 89.3%로 0.1%p 차. 진행 중 업무 F1 최고(88.4%)
- 평균 5.33s, 빈 보고 50%
- 이 파이프라인에서는 JSON 스키마가 동작했다(32/32). F1은 비슷하지만 지연 때문에 기본값으로 두지 않음

### Muse Glimmer-30B

- F1 85.0%, 다음 계획 F1은 세 모델 중 최고(86.3%)
- JSON 96.9%(1건 실패), 평균 7.98s로 가장 느리고 빈 보고도 50%
- 추출 기본값으로는 채택하지 않음
---

## 참고: 공개 벤치

| 지표 | 설명 |
| --- | --- |
| IFBench | 형식·제약 준수. 스키마 JSON과 제일 가깝다 |


| 순위 | 모델 | IFBench | 출처 |
| --- | ---: | ---: | --- |
| 1 | Qwen3.8-27B | 79.5 | Qwen 모델 카드 |
| 2 | Muse Glimmer-30B | 77.0 | Qwen 모델 카드 비교열 |
| 3 | Gemma 4 31B | 75.6 | OrcaRouter / Artificial Analysis |


출처: [Artificial Analysis](https://artificialanalysis.ai/models/qwen3-8-27b), [Kingy](https://kingy.ai/blog/qwen3-8-27b-vs-qwen3-6-27b-vs-gemma-4-31b/), [Muse Glimmer AA](https://artificialanalysis.ai/models/muse-glimmer), [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B).