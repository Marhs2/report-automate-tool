# 모델 벤치마크 및 선정 근거

## 결론

현재 기본 모델은 **qwen3.5-4b**로 유지한다.

이번 동일 조건 일일보고 벤치마크에서 qwen3.5-4b가 세 모델 중
가장 높은 micro F1을 기록했다.

## 실행 조건

- 실행일: 2026-08-05
- 대상: 일일보고 자동 구조화
- 데이터셋: `benchmark/dataset/gold_dataset.json`
- 테스트 건수: 32건
- 작성 스타일: 개조식, 줄글, 메신저체, 표, 혼합, 영어 혼합, 한 줄, 업무 없음
- 프롬프트: `backend/model_asset/prompt.txt`
- 스키마: `backend/model_asset/json_Schema.json`
- 등록 프로젝트 주입: `--known-projects dataset`
- 추론: `none`
- 최대 출력 토큰: 6144

실행 명령:

```bash
python benchmark/run_benchmark.py qwen3.5-4b gemma-4-e2b-it-qat nuextract3 ^
  --force --reasoning none --max-tokens 6144 ^
  --dataset gold --known-projects dataset ^
  --out-dir benchmark/results/three_models_2026-08-05_daily

python benchmark/score_benchmark.py ^
  --raw-dir benchmark/results/three_models_2026-08-05_daily ^
  --prefix three_models_2026_08_05_
```

## 일일보고 종합 결과

| 순위 | 모델               | JSON 유효 | 스키마 준수 | 프로젝트 F1 | 정밀도 | 재현율 |  micro F1 |   평균 지연 |
| ---: | ------------------ | --------: | ----------: | ----------: | -----: | -----: | --------: | ----------: |
|    1 | **qwen3.5-4b**     |    100.0% |      100.0% |       93.7% |  84.9% |  81.1% | **83.0%** |     18.99초 |
|    2 | nuextract3         |    100.0% |      100.0% |       95.7% |  82.6% |  82.6% |     82.6% |     22.10초 |
|    3 | gemma-4-e2b-it-qat |    100.0% |      100.0% |       92.6% |  77.3% |  77.3% |     77.3% | **16.09초** |

## 항목별 F1

| 모델               | 완료 업무 | 진행 중 업무 |      이슈 | 협조 요청 | 다음 계획 |
| ------------------ | --------: | -----------: | --------: | --------: | --------: |
| qwen3.5-4b         |     90.7% |        84.6% |     71.4% |     66.7% |     83.7% |
| nuextract3         |     87.8% |        80.0% | **72.3%** | **85.7%** |     83.7% |
| gemma-4-e2b-it-qat |     89.1% |        73.7% |     68.3% |     63.6% |     69.8% |

## 선정 판단

### qwen3.5-4b

- 세 모델 중 micro F1 1위
- 완료 업무, 진행 중 업무, 다음 계획 추출 성능이 균형적
- JSON과 스키마 준수율 100%
- 평균 지연은 nuextract3보다 짧음

### nuextract3

- 프로젝트 F1, 이슈, 협조 요청 항목은 가장 높음
- 전체 micro F1은 qwen과 0.4%p 차이
- qwen보다 평균 지연이 길어 기본 모델로는 제외

### gemma-4-e2b-it-qat

- 평균 지연은 가장 짧음
- 그러나 전체 micro F1과 진행 중 업무·다음 계획 성능이 가장 낮음
- 속도보다 추출 정확도가 중요한 현재 용도에는 부적합

## 결과 파일

- 원시 응답: `benchmark/results/three_models_2026-08-05_daily/`
- 종합 점수: `benchmark/results/three_models_2026_08_05_scores.json`
- CSV 요약: `benchmark/results/three_models_2026_08_05_summary.csv`
- 상세 표: `benchmark/results/three_models_2026_08_05_tables.md`
