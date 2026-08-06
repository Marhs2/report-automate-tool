# 모델 벤치마크 및 선정 근거

> (`test-data/daily-reports.md`, 32건)의 항목별 추출 정확도·케이스별 오류 분석은
> [docs/정확도-평가.md](docs/정확도-평가.md) 참고.

## 결론

현재 기본 모델은 **qwen3.5-4b**로 유지한다.

2026-08-06 재측정에서 종합 점수(micro F1)는 nuextract3가 1위를 기록했으나,
완료 업무·이슈 정밀도·협조 요청에서 qwen3.5-4b가 우위이고, 오탐(FP)이 적어
실제 운영에서 이슈를 부풀리지 않는 안정성이 강점이다.

## 실행 조건

- 실행일: 2026-08-06 (재측정)
- 대상: 일일보고 자동 구조화
- 데이터셋: `benchmark/dataset/gold_dataset.json` (gold) + `gold_dataset_report.json` (report)
- 테스트 건수: 각 32건
- 작성 스타일: 개조식, 줄글, 메신저체, 표, 혼합, 영어 혼합, 한 줄, 업무 없음
- 프롬프트: `backend/model_asset/prompt.txt`
- 스키마: `backend/model_asset/json_Schema.json`
- 등록 프로젝트 주입: gold=`--known-projects dataset`, report=`--known-projects report`
- 추론: `none`
- 최대 출력 토큰: 6144

실행 명령:

```bash
python benchmark/run_benchmark.py qwen3.5-4b google/gemma-4-e2b nuextract3 ^
  --force --reasoning none --max-tokens 6144 ^
  --dataset gold --known-projects dataset ^
  --out-dir benchmark/results/three_models_2026-08-05_daily

python benchmark/score_benchmark.py ^
  --raw-dir benchmark/results/three_models_2026-08-05_daily ^
  --prefix three_models_2026_08_05_

python benchmark/run_benchmark.py qwen3.5-4b google/gemma-4-e2b nuextract3 ^
  --force --reasoning none --max-tokens 6144 ^
  --dataset report --known-projects report ^
  --out-dir benchmark/results/report_2026-08-05

python benchmark/score_benchmark.py ^
  --raw-dir benchmark/results/report_2026-08-05 ^
  --prefix report_2026_08_05_ --dataset report
```

## gold 데이터셋 종합 결과 (2026-08-06 재측정)

| 순위 | 모델               | JSON 유효 | 스키마 준수 | 프로젝트 F1 | 정밀도 | 재현율 |  micro F1 |   평균 지연 | tok/s |
| ---: | ------------------ | --------: | ----------: | ----------: | -----: | -----: | --------: | ----------: | ----: |
|    1 | **nuextract3**     |    100.0% |      100.0% |       93.9% |  82.6% |  82.6% | **82.6%** |     2.54초 |  45.3 |
|    2 | **qwen3.5-4b**     |    100.0% |      100.0% |       97.3% |  82.2% |  80.3% |     81.2% |     3.04초 |  54.4 |
|    3 | google/gemma-4-e2b |    100.0% |      100.0% |       97.3% |  70.2% |  84.1% |     76.5% |   **2.74초** |  73.7 |

## report 데이터셋 종합 결과 (2026-08-06 재측정)

| 순위 | 모델                   | JSON 유효 | 스키마 준수 | 프로젝트 F1 |  micro F1 | 평균 지연 | tok/s |
| ---: | ---------------------- | --------: | ----------: | ----------: | --------: | --------: | ----: |
|    1 | **nuextract3**         |    100.0% |      100.0% |  **98.8%** | **77.6%** | **2.09초** |  43.4 |
|    2 | **google/gemma-4-e2b** |    100.0% |      100.0% |       97.6% |     76.4% |    2.41초 |  72.3 |
|    3 | **qwen3.5-4b**         |    100.0% |      100.0% |       94.2% |     73.3% |    2.65초 |  52.3 |

## 항목별 F1 (gold 데이터셋)

| 모델               | 완료 업무 | 진행 중 업무 |      이슈 | 협조 요청 | 다음 계획 |
| ------------------ | --------: | -----------: | --------: | --------: | --------: |
| nuextract3         |     88.7% |    **85.2%** |     65.2% |     69.6% | **90.9%** |
| **qwen3.5-4b**     | **91.8%** |        79.3% | **68.4%** | **75.0%** |     74.4% |
| google/gemma-4-e2b |     89.3% |        66.7% |     65.4% |     78.3% |     73.5% |

## 선정 판단

### qwen3.5-4b (채택)

- **완료 업무 91.8%** — 세 모델 중 최고, gold 오탐 0건(정밀도 100%)
- **이슈 정밀도 81.2%** — 오탐이 적어 이슈를 부풀리지 않음
- **협조 요청 75.0%** — 세 모델 중 최고
- JSON·스키마 준수율 100%, 빈 보고 처리 100%
- 평균 지연 2.65~3.04초로 20초 목표 대비 충분히 빠름
- 한계: report 데이터셋 종합 3위(73.3%), 다음 계획(68.2%)이 약함

### nuextract3

- 종합 점수 1위 (gold 82.6% / report 77.6%), 지연도 가장 짧음(2.09~2.54초)
- 그러나 **이슈 정밀도가 62.5%(gold)로 낮아 오탐이 많고**, 협조 요청도 qwen보다 낮음
- 종합 점수만 보면 최적이나, 이슈 오탐이 실사용에서 문제가 되면 전환 재검토

### google/gemma-4-e2b

- 재현율(84.1%)은 가장 높으나 정밀도(70.2%)가 낮아 micro F1이 최하(76.5%)
- 진행 중 업무(66.7%)·이슈(65.4%) 오탐이 많고, 빈 보고 처리 50%(report)로 불안정

## 결과 파일

- 원시 응답: `benchmark/results/three_models_2026-08-05_daily/`, `benchmark/results/report_2026-08-05/`
- 종합 점수: `benchmark/results/three_models_2026_08_05_scores.json`, `benchmark/results/report_2026_08_05_scores.json`
- CSV 요약: `benchmark/results/three_models_2026_08_05_summary.csv`, `benchmark/results/report_2026_08_05_summary.csv`
- 상세 표: `benchmark/results/three_models_2026_08_05_tables.md`, `benchmark/results/report_2026_08_05_tables.md`
