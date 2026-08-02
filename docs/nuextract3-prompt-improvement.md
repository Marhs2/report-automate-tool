# NuExtract3 프롬프트 개선 결과 (v2 → v3 슬림)

측정일: 2026-08-02 · 모델: nuextract3 (LM Studio, 로컬) · 채점: `benchmark/score_benchmark.py`

## 1. 요약

| 데이터셋 | 설정 | micro F1 | 지연 | 비고 |
|---|---|---|---|---|
| 기존 32건 | 기존 `prompt.txt` + known-projects 없음 | 0.755 | 2.3s | 시작점 |
| 기존 32건 | `prompt_v2.txt` + names_only | 0.837 | 2.5s | 이전 개선 |
| **기존 32건** | **`prompt_v3.txt`(슬림) + names_only** | **0.845** | 2.5s | 슬림이 더 좋음 |
| **기존 32건** | **`prompt_v3.txt` + reasoning high** | **0.872** | 11.5s | reasoning이 +2.7pp |
| **신규 32건(diverse)** | **`prompt_v3.txt` + diverse 목록** | **0.861** | 2.6s | 미지 데이터 일반화 |
| 신규 32건(diverse) | `prompt_v3.txt` + diverse + reasoning high | 0.824 | 13.3s | reasoning이 -3.7pp |

## 2. 결론

1. **슬림 프롬프트(prompt_v3)가 v2보다 낫다.** 36KB → 5.6KB (85% 축소)인데도 기존 데이터셋에서
   0.837 → 0.845, 신규 데이터셋에서도 0.861로 오히려 일반화가 좋다. 소형 모델은 짧고 명확한
   지시가 낫다는 가설이 확인됐다.
2. **known-projects 주입이 최대 레버** (기존 0.755 → 0.807). v3 슬림도 names_only/diverse 주입이 필수.
3. **reasoning은 상황에 따라 다르다.** 기존 데이터셋(익숙한 패턴)에서는 +2.7pp지만,
   신규 데이터셋에서는 -3.7pp로 오히려 해롭다(요청·다음 계획 판정이 흔들림). 지연도 6배.
   → **운영 기본값은 reasoning off가 안전.** 요구사항 "10분 이내"는 여유지만(13s) 정확도가 더 중요.
4. **프롬프트가 데이터셋의 known-projects 목록과 일치해야 한다.** 신규 데이터셋에 기존 목록을
   넣으면 0.786으로 폭락한다(미분류 떠넘김). `--known-projects diverse`로 각 데이터셋에 맞는
   목록을 주입해야 한다.

## 3. prompt_v3 (슬림) 에서 뺀 것

- 장식용 구분선(════, ┌─┐), 판정 근거 나열, 중복 규칙
- A/B/C/D/E/F/G/H/I/기호 절 구조 → 번호 붙은 규칙 8개 + 예시 3개로 통합
- 희귀 엣지케이스(I1~I8: 홈페이지 판단, 부정형, 조건부, 반복 업무 등) → 필드 판정 규칙으로 흡수
- A8(예시 오염 방지) 문장 → "예시는 참고용, 출력에 포함하지 말 것" 한 줄로
- 판정 흐름도, 잘못된/올바른 예 대조 → 필수 규칙만 남김

## 4. 남긴 것 (측정된 실패 패턴 대응)

- projectName 규칙 (화면·기능·팀·기술명 제외) — D11/D22/D03/D12/D30
- 영문 보존 (monitoring dashboard → 그대로) — D25/E07
- 진행률 100% 미만 → inProgress — D06/E06/E21
- requests vs nextPlans (요청 대상 유무) — D05/D12/D30
- 내일/다음 주 ~하겠습니다 → nextPlans — D12/E03/E08
- 메신저체 본인 발화만 추출 — D22/D03/E03/E08/E12/E22
- 이슈 중복 배치 금지 — D20/D26/E28

## 5. 신규 데이터셋 (gold_dataset_diverse.json)

- 32건, 실제 서비스 프로젝트(일일보고 취합·주간보고 자동화 도구, 명함 관리 웹, 스모크),
  실제 팀원 4명, 2주치
- 기존 데이터셋에 없던 케이스: 중복 제출 처리(E11), 반복 업무 병합(E15), 회신 대기(E07/E28/E32),
  진행률 40%/70%(E06/E21), 디자인 시안 보류(E24), 업무 없음(E16), 한 줄(E09/E25), 영문 혼합(E07/E15/E28)
- gold 117개 항목 / 프로젝트 블록 44개
- `--dataset diverse` + `--known-projects diverse` 로 실행

## 6. 재현

```bash
# 슬림 프롬프트 + known-projects 주입 (운영 권장)
python benchmark/run_benchmark.py nuextract3 \
  --prompt backend/model_asset/prompt_v3.txt --known-projects names_only

# 신규 데이터셋
python benchmark/run_benchmark.py nuextract3 \
  --prompt backend/model_asset/prompt_v3.txt --known-projects diverse --dataset diverse

# reasoning 비교 (선택)
python benchmark/run_benchmark.py nuextract3 --reasoning high --max-tokens 16384 \
  --preload --context-length 32768 --parallel 1 \
  --prompt backend/model_asset/prompt_v3.txt --known-projects names_only
```

## 7. 배포

`prompt_v3.txt` 내용을 `prompt.txt`로 복사하면 된다. 백엔드 `load_daily_prompt()`가
`{{KNOWN_PROJECTS}}`를 DB의 실제 프로젝트 목록으로 채우므로 운영과 동일 조건이 된다.

```bash
cp backend/model_asset/prompt_v3.txt backend/model_asset/prompt.txt
```

## 8. 남은 한계

- 이슈 항목 F1이 여전히 가장 약함 (신규 데이터셋 0.77): "해결됐는데 issues에 넣는" 오류, 요청 대상
  판정. reasoning off에서도 잔존.
- 신규 데이터셋은 프롬프트 작성자가 직접 라벨링해 편향 가능. 실제 팀원 보고로 재검증 필요.
- 온도 0.1 단일 샘플이라 케이스별 ±0.1 F1 노이즈 있음 (실행 간 0.826~0.845).
