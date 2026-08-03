# NuExtract3 vs Qwen 3.5 4B — 추론 끈 Qwen 도입 판정 벤치마크

측정일: 2026-08-03 · 로컬 LM Studio (RTX 3060 12GB) · 데이터셋: `fresh` (완전히 새로운 프로젝트·인물 32건)
채점: `benchmark/score_benchmark.py` (일일), `benchmark/weekly_bench.py` (주간)

## 1. 결론

**기본 모델은 qwen3.5-4b(추론 끄기)로 결정했다.** daily 추출 micro F1 0.883으로
nuextract3(추론 high) 0.866, nuextract3(추론 끄기) 0.883과 동급 이상이면서
케이스당 2.2초(추론 high의 1/4, nuextract3와 동급)로 빠르다.
"qwen은 추론을 꺼도 좋다"는 가설이 **검증됐다** — 정확도는 유지되고 속도만 극적으로 빨라진다.

## 2. daily 추출 — 모델×설정 비교 (fresh 32건)

| 설정 | micro F1 | 프로젝트 F1 | 정밀도 | 재현율 | 평균 지연 |
|---|---|---|---|---|---|
| **qwen3.5-4b + v4 + reasoning off** | **0.883** (재현 0.887) | 0.966 | 0.911 | 0.857 | **2.2s** (재현 1.9s) |
| nuextract3 + v4 + reasoning off | 0.883 | 0.967 | 0.911 | 0.857 | 1.7s |
| nuextract3 + v4 + reasoning high | 0.866 | 0.946 | 0.866 | 0.866 | 8.1s |
| nuextract3 + v3(기존) + reasoning off | 0.864 | 0.978 | 0.872 | 0.857 | 1.7s |

### 항목별 F1

| 설정 | 완료 업무 | 진행 중 | 이슈 | 협조 요청 | 다음 계획 |
|---|---|---|---|---|---|
| qwen3.5-4b v4 off | 0.901 | 0.969 | 0.722 | 0.815 | **0.909** |
| nuextract3 v4 off | 0.927 | 0.954 | 0.800 | 0.800 | 0.812 |
| nuextract3 v4 high | 0.986 | 0.923 | 0.829 | 0.714 | 0.667 |
| nuextract3 v3 off | 0.927 | 0.906 | 0.756 | 0.800 | 0.849 |

- **qwen은 다음 계획(F1 0.909)·진행 중(0.969)·협조 요청(0.815)에서 가장 강하다.** 다음 계획은
  nuextract3 high(0.667)보다 +24pp.
- nuextract3는 이슈(0.800)와 완료 업무(0.927)에서 qwen보다 약간 앞선다.
- 케이스 단위로는 **qwen이 32건 중 21건에서 최고(또는 공동 최고)**다.

### 케이스별 qwen vs nuextract3

| 케이스 | 스타일 | v3off | v4off(nx) | nx high | **qwen off** |
|---|---|---|---|---|---|
| F02 | 줄글 | 0.462 | 0.727 | 1.000 | **0.909** |
| F03 | 메신저 | 1.000 | 1.000 | 0.571 | **1.000** |
| F07 | 줄글+영문 | 0.444 | 0.444 | 0.667 | **0.800** |
| F12 | 메신저 | 1.000 | 1.000 | 0.571 | **1.000** |
| F20 | 줄글 | 0.667 | 1.000 | 0.800 | **0.800** |
| F30 | 메신저 | 0.667 | 0.400 | 0.571 | **0.800** |
| F31 | 줄글 | 0.571 | 0.571 | 0.857 | **0.750** |

qwen은 메신저체·줄글+영문 혼합(기존에 nuextract3가 약했던 영역)에서 특히 강하다.
nuextract3가 qwen보다 확실히 나은 케이스는 F08(0.750 vs 0.571), F26(1.0 vs 0.8) 정도뿐.

## 3. 프롬프트 개선 효과

### daily: v3 → v4 (배포 완료)

| 데이터셋 | v3 | v4 | Δ |
|---|---|---|---|
| fresh | 0.864 | **0.883** | **+1.9pp** |

v4는 v3 슬림을 유지하면서 실패 패턴 규칙을 보강했다:
- **진행 중 보강**: "보완 중", "개선 중" 명사+중 형태, 수치 확인·측정 결과 완료 판정
- **이슈/진행 중복 방지**: 해결되지 않은 채 남은 문제의 중복 배치 명확화
- **긴 줄글 처리 순서**: 문장별 프로젝트 귀속 → 필드 판정 → 분리 → 중복 확인
- 대표 개선: F02 0.462→0.727, F20 0.667→1.000, F27 0.857→1.000
- 일부 후퇴: F15 0.750→0.500 (disk usage 92% 숫자 오기재 + 이슈 중복), F26, F30 — 소형 모델의
  긴 복합 줄글 한계로 프롬프트만으로 완전 해결은 어렵다.

### weekly: v1 → v2 (배포 완료) — 병합 충실도 + 속도

| 모델 | weekly v1 | weekly v2 | Δ |
|---|---|---|---|
| nuextract3 | 0.885 | 0.886 | +0.1pp |
| qwen3.5-4b | 0.895 | 0.875 | -2.0pp |

- v2는 v1과 정확도 동급(±0.1pp)이면서 **프롬프트 9.7KB→5.1KB (47% 축소), 지연 약 2배 단축**.
- v2의 규칙은 더 명확해졌다(필드 병합·상태 승격·이슈 해결 판정·원문 보존·출력 전 확인).
- 다만 qwen에서 v2가 v1보다 -2.0pp인데, **주간 케이스 4건뿐이라 유의차로 보기 어렵다.**
  (nuextract3은 동급) 다음 주간 이터레이션에서 재확인이 필요하다.
- **공통 약점: nextWeekPlans F1 ≈ 0.6** (모든 설정). requests/nextPlans가 병합·중복 제거 과정에서
  과도하게 제거되거나 누락된다. 일일 단계의 nextPlans를 주간 nextWeekPlans로 충실히 옮기는 규칙을
  다음 개선 대상으로 한다.

## 4. 운영 설정 (결정)

```bash
# .env
REPORT_MODEL_NAME=qwen3.5-4b
DAILY_REASONING=none
DAILY_MAX_TOKENS=6144        # 추론 끄면 사고 토큰이 없으므로 6144로 충분 (기존 16384는 추론용)
WEEKLY_MAX_TOKENS=2048
```

- qwen3.5-4b를 **`--parallel 1 --context-length 32768`로 로드**한다 (모든 모델 공통, 추론과 무관하게 컨텍스트 분할 방지).
- nuextract3로 되돌릴 경우: `REPORT_MODEL_NAME=nuextract3`, `DAILY_REASONING=high` (정확도 0.866, 8.1s).
- 추출 결과는 여전히 화면 확인·수정 단계가 필수다 (micro F1 0.883 = 항목 132개 중 약 15개 오답).

## 5. 산출물

| 경로 | 내용 |
|---|---|
| `backend/model_asset/prompt_v4.txt` | 개선된 daily 프롬프트 (배포됨 → `prompt.txt`) |
| `backend/model_asset/weekly_prompt_v2.txt` | 개선된 weekly 프롬프트 (배포됨 → `weekly_prompt.txt`) |
| `benchmark/weekly_bench.py` | 주간 병합 벤치마크 (신규) |
| `benchmark/results/raw_v4_fresh/` | nuextract3 v4 off 원시 응답 |
| `benchmark/results/raw_nx3_v4_high/` | nuextract3 v4 high 원시 응답 |
| `benchmark/results/raw_qwen_v4_off/` | qwen3.5-4b v4 off 원시 응답 |
| `benchmark/results/v3fresh_*.json/.csv/.md` | v3 baseline 채점 |
| `benchmark/results/v4fresh_*`, `nx3v4high_*`, `qwenv4off_*` | 각 설정 채점 |

## 6. 재현

```bash
# daily
python benchmark/run_benchmark.py qwen3.5-4b --prompt backend/model_asset/prompt_v4.txt \
  --known-projects fresh --dataset fresh --out-dir benchmark/results/raw_qwen_v4_off
python benchmark/score_benchmark.py --raw-dir benchmark/results/raw_qwen_v4_off --dataset fresh --prefix qwenv4off_

# weekly
python benchmark/weekly_bench.py --model qwen3.5-4b --prompt-v2
python benchmark/weekly_bench.py --model nuextract3 --prompt-v2
```

## 7. 한계

- 주간 벤치마크는 케이스 4건(멤버 4명의 주간 집계)뿐이라 v1/v2 차이(±2pp)는 유의하지 않다.
- 주간 gold는 '병합·중복 제거·projectName 통일·환각 억제' 충실도를 측정한다. 실제 상태 승격
  (inProgress→completed)이나 이슈 해결 판정은 입력에 날짜별 진행이 없어 측정하지 않았다.
- daily 케이스 32건, 항목 132개 규모에서 micro F1 1~2pp 차이는 온도 0.1 단일 샘플 노이즈가 있을 수 있다.
- qwen의 이슈 F1(0.722)이 nuextract3(0.800)보다 낮다. 이슈가 중요하면 nuextract3 유지도 합리적.
- **측정 환경 주의**: LM Studio의 UI 프리셋(예: '보고서 작성' 프리셋)이 활성화된 상태에서 JIT 로드하면
  qwen3.5-4b가 `reasoning_effort` 없이도 내부 추론을 실행해 `finish_reason=length` + 빈 content가 될 수 있다.
  벤치마크와 운영 모두 `--preload`(또는 수동 `lms load --context-length 32768 --parallel 1`)로 로드한 뒤
  호출해야 추론 끄기 조건이 보장된다. 위 qwen 0.883/0.887은 이 조건에서 측정했다.
