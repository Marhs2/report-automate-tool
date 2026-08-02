# NuExtract3 신규 데이터셋(fresh) 테스트 결과

측정일: 2026-08-02 · 모델: nuextract3 (LM Studio) · 배포된 `backend/model_asset/prompt.txt`(v3 슬림)
채점: `benchmark/score_benchmark.py --dataset fresh`

## 1. 요약

| 데이터셋 | 설정 | micro F1 | 지연 | JSON |
|---|---|---|---|---|
| 기존 32건 | v3 + names_only | 0.845 | 2.5s | 100% |
| 기존 32건 | v3 + names_only + reasoning high | 0.872 | 11.5s | 100% |
| diverse 32건 | v3 + diverse | 0.861 | 2.6s | 100% |
| **fresh 32건** | **v3 + fresh** | **0.864 / 0.862** | 2.0s | 100% |
| **fresh 32건** | **v3 + fresh + reasoning high** | **0.871** | 15.2s | 100% |

- fresh(완전히 새로운 프로젝트·인물·도메인)에서도 기존 데이터셋과 동등한 성능 → **프롬프트가
  특정 프로젝트명에 과적합되지 않았다**.
- reasoning high: fresh에서 +0.7pp (diverse에선 -3.7pp, gold에선 +2.7pp). 데이터셋에 따라
  부호가 갈리지만, 편차 폭이 작아 어느 쪽이든 큰 영향은 없다. 지연만 7~8배 증가.

## 2. fresh 데이터셋 구성

- **완전히 새로운 프로젝트 3개**: AI면접코치, 물류추적시스템, 전자계약 (기존 gold/diverse와 0 overlap)
- **새 인물 4명**: 강서준, 임나연, 조민석, 한지우
- 2주치 32건, gold 항목 119개 / 프로젝트 블록 50개
- 기존 데이터셋보다 어려운 케이스:
  - 같은 날 중복 제출 처리, 프로젝트 간 업무(F05/F11/F15/F20/F31)
  - 긴 복합 줄글(2~3개 프로젝트 혼재), 영문·기술용어 혼합(F07: TLS 1.2, webhook, retry / F15: disk usage, false positive)
  - 진행률 40%/70% 표(F06/F21), 메신저 다중 화자(F03/F08/F12/F22/F30)
  - 업무 없음(반차 F16), 대기/보류/차단(F24/F32), 이름만 있는 헤더(F09/F25/F29)

## 3. 안정적 실패 케이스 (두 실행 모두 F1 < 0.7)

| 케이스 | 스타일 | F1 | 실패 내용 |
|---|---|---|---|
| F07 | 줄글+영문 | 0.44 | 요청 대상을 잘못 귀속 (보안팀 침투 테스트 요청을 전자계약이 아니라 물류추적에 넣음) |
| F02 | 줄글 | 0.45 | "매핑 테이블 보완 중"을 inProgress로 못 잡고 issues·requests로 분산 |
| F31 | 줄글 | 0.57 | 3개 프로젝트 혼재 시 완료/진행/요청 분리가 흔들림 |
| F20 | 줄글 | 0.67 | "발송 시각 지연 문제"를 issues와 inProgress 양쪽에 중복 |
| F30 | 메신저체 | 0.67 | "적중률 78% 확인"을 completed로 못 잡음 |

**공통 패턴**: 긴 줄글(문장 3개 이상) + 프로젝트 2개 이상 + 영문/기술용어 혼합 조합에서
완료/진행/이슈/요청 4분류와 프로젝트 귀속이 함께 어긋난다. 단일 프로젝트·짧은 보고는 안정적.

## 4. 결론

1. **현재 배포된 v3 슬림 프롬프트는 미지 도메인에서도 일반화된다** (0.862~0.864, 기존과 동등).
   새 프로젝트·새 인물·새 업무 영역이 나와도 성능 저하가 없다.
2. **reasoning은 fresh에서 약간 도움** (+0.7pp)이지만 지연 15초. 운영 기본은 off 유지가 합리적.
3. 남은 한계는 소형 모델 본질: **긴 복합 줄글의 4분류 + 다중 프로젝트 귀속 동시 판정**.
   프롬프트로는 한계가 있고, 입력 화면에서 항목별 확인·수정 단계가 실질적 보완책.

## 5. 재현

```bash
# fresh + reasoning off (운영과 동일 조건)
python benchmark/run_benchmark.py nuextract3 \
  --prompt backend/model_asset/prompt.txt --known-projects fresh --dataset fresh \
  --out-dir benchmark/results/raw_fresh_off
python benchmark/score_benchmark.py --raw-dir benchmark/results/raw_fresh_off --dataset fresh --prefix fresh_off_

# fresh + reasoning high
python benchmark/run_benchmark.py nuextract3 --reasoning high --max-tokens 16384 \
  --preload --context-length 32768 --parallel 1 \
  --prompt backend/model_asset/prompt.txt --known-projects fresh --dataset fresh \
  --out-dir benchmark/results/raw_fresh_high
```

데이터셋: `benchmark/dataset/gold_dataset_fresh.json`
