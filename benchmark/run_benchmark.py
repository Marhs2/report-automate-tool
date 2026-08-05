"""일일보고 구조화 모델 벤치마크 실행기.

LM Studio(OpenAI 호환 API)에 올려둔 로컬 모델들에게
backend/model_asset/prompt.txt + json_Schema.json 을 그대로 적용해
benchmark/dataset/gold_dataset.json 의 원문 32건을 추출시키고
원시 응답·지연시간·토큰 사용량을 <out-dir>/<model>.jsonl 에 기록한다.

채점은 score_benchmark.py 가 담당한다. (재채점 시 모델 재호출 불필요)

중요: 추론(reasoning)을 켜고 돌릴 때는 모델을 반드시 `--parallel 1` 로 로드해야 한다.
LM Studio 기본값은 parallel=4 이고, 이 경우 컨텍스트가 4등분되어(8192/4 → 실효 8192)
사고 과정 도중 컨텍스트가 차서 JSON을 한 글자도 출력하지 못한다.
이 스크립트는 --preload 옵션으로 lms CLI를 통해 알맞게 로드한다.

사용법:
    # 추론 끄기 (서비스 기본 설정)
    python benchmark/run_benchmark.py

    # 추론 최대
    python benchmark/run_benchmark.py --reasoning high --max-tokens 16384 \
        --preload --context-length 32768 --out-dir benchmark/results/raw_reasoning_high

    python benchmark/run_benchmark.py qwen3.5-4b     # 특정 모델만
    python benchmark/run_benchmark.py --force        # 체크포인트 무시하고 재실행
"""

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

from openai import OpenAI

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
DEFAULT_RAW_DIR = BENCH / "results" / "raw"

LM_BASE_URL = "http://127.0.0.1:1234/v1"
LM_API_KEY = "lm-studio"

# 후보 모델. LM Studio에 로드 가능한 텍스트 생성 모델만 포함
# (text-embedding-nomic-embed-text-v1.5 는 임베딩 전용이라 추출 태스크 대상 아님)
MODELS = [
    "lfm2.5-8b-a1b",
    "kanana-2-3b-instruct-i1",
    "nuextract3",
    "minicpm5-1b",
    "google/gemma-4-e2b",
    "qwen3.5-4b",
    "nvidia/nemotron-3-nano-4b",
]

TEMPERATURE = 0.1
TIMEOUT_S = 900.0
MAX_ATTEMPTS = 3

# prompt.txt 의 {{KNOWN_PROJECTS}} 슬롯에 넣을 내용.
# 실제 서비스에서는 DB(known_projects, project_aliases)에서 만들어 넣는다.
# 벤치마크에서는 프로젝트 단위 정보만 넣고 개별 케이스의 정답은 넣지 않는다.
KNOWN_PROJECTS_NONE = "(등록된 프로젝트가 없다. 원문에서 직접 판단한다.)"

# backend/main.py 의 get_known_projects_block() 과 동일한 형태: 이름 + 별칭만.
# 실제 서비스가 주입하는 것과 같은 조건을 재현한다 (주요 구성 요소는 넣지 않는다).
KNOWN_PROJECTS_NAMES_ONLY = """- A사 MES
  · 표기 변형: MES, A사 MES 구축, A사 MES 시스템
- 여우비
  · 표기 변형: 여우비 앱
- Yak-Map
  · 표기 변형: 약맵, 약품 지도"""

# gold_dataset_diverse.json 의 프로젝트 (실제 서비스 DB와 동일). names_only 와 같은 형식.
KNOWN_PROJECTS_DIVERSE = """- 일일보고 취합·주간보고 자동화 도구
  · 표기 변형: 자동화 도구, 일일보고 자동화 도구, 자동화
- 명함 관리 웹
  · 표기 변형: 명함 관리, 명함 웹
- 스모크
  · 표기 변형: 스모크 테스트"""

# gold_dataset_fresh.json 의 프로젝트. 이전 데이터셋과 완전히 다르다.
KNOWN_PROJECTS_FRESH = """- AI면접코치
  · 표기 변형: 면접코치, AI면접, 면접AI
- 물류추적시스템
  · 표기 변형: 물류추적, 추적시스템
- 전자계약
  · 표기 변형: 전자계약시스템, 계약시스템"""

KNOWN_PROJECTS_VALIDATION = """- 스마트팩토리
  · 표기 변형: 스마트공장, 공장자동화
- 헬스케어앱
  · 표기 변형: 건강관리앱, 헬스케어
- 전자상거래플랫폼
  · 표기 변형: 쇼핑몰, 이커머스"""

# gold_dataset_report.json 의 프로젝트 (test-data/daily-reports.md 자체 작성 테스트 데이터).
KNOWN_PROJECTS_REPORT = """- 일일보고취합
  · 표기 변형: 일일보고 취합·주간보고 자동화 도구, 일일보고, 주간보고 자동화 도구, 취합
  · 주요 구성 요소: 보고서 작성 화면, 보고서 미리보기, 임시 저장, 저장 목록, 활동 현황, 주간보고 초안, 제출 기능, 제출 현황, 이전 보고서 보존·이동, 통합 확인 화면, 대시보드
- 명함주소록
  · 표기 변형: 명함 관리 웹, 명함 관리, 명함
  · 주요 구성 요소: 명함 사진 인식, 연락처 목록, 명함 상세 보기, 명함 공유 화면, 중복 명함 판단, 명함 분류, 모바일 화면
- 회의록자동화
  · 표기 변형: 회의록 자동화, 회의록
  · 주요 구성 요소: 회의 녹음 파일 업로드, 녹음 요약, 참석자별 발화 정리, 회의 상세 보기, 음성 전처리, 회의록 양식"""

KNOWN_PROJECTS_DATASET = """- A사 MES
  · 표기 변형: MES, A사 MES 구축, A사 MES 시스템
  · 주요 구성 요소: 설비 데이터 수집 배치, 실시간 알림 이력 화면, 알림 조건 설정,
    재고관리 화면, 입고 API, 설비 마스터 데이터 마이그레이션, PLC 연동, 운영 서버
- 여우비
  · 표기 변형: 여우비 앱
  · 주요 구성 요소: 회원가입, 기관 추천코드, 선배 도움 버튼, 포인트 적립/사용,
    마이페이지(프로필 영역, 활동 내역 탭), staging 환경, SSL 인증서
- Yak-Map
  · 표기 변형: 약맵, 약품 지도
  · 주요 구성 요소: 약품 검색 API, 약국 지도 화면, 약국 상세 화면, 처방전 OCR,
    위치 권한 안내, CI 파이프라인, monitoring dashboard, alert 규칙"""


def safe_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", model)


def load_assets(prompt_path=None, known_projects="none", dataset_name="gold"):
    path = pathlib.Path(prompt_path) if prompt_path else ROOT / "backend" / "model_asset" / "prompt.txt"
    with open(path, encoding="utf-8") as f:
        prompt = f.read()
    filler = KNOWN_PROJECTS_DATASET if known_projects == "dataset" else KNOWN_PROJECTS_NONE
    if known_projects == "names_only":
        filler = KNOWN_PROJECTS_NAMES_ONLY
    if known_projects == "diverse":
        filler = KNOWN_PROJECTS_DIVERSE
    if known_projects == "fresh":
        filler = KNOWN_PROJECTS_FRESH
    if known_projects == "validation":
        filler = KNOWN_PROJECTS_VALIDATION
    if known_projects == "report":
        filler = KNOWN_PROJECTS_REPORT
    prompt = prompt.replace("{{KNOWN_PROJECTS}}", filler)
    with open(ROOT / "backend" / "model_asset" / "json_Schema.json", encoding="utf-8") as f:
        schema = json.load(f)
    dataset_file = "gold_dataset.json" if dataset_name == "gold" else f"gold_dataset_{dataset_name}.json"
    with open(BENCH / "dataset" / dataset_file, encoding="utf-8") as f:
        dataset = json.load(f)
    return prompt, schema, dataset


def read_done(path: pathlib.Path):
    done = {}
    if not path.exists():
        return done
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            done[rec["case_id"]] = rec
    return done


def lms(*args, timeout=900):
    cmd = ["lms", *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        return proc.returncode, (proc.stdout or "")[-400:], (proc.stderr or "")[-400:]
    except Exception as e:
        return -1, "", f"{type(e).__name__}: {e}"


def preload(model, context_length, parallel):
    """추론 모드에서 컨텍스트가 부족해 실패하지 않도록 명시적으로 로드한다."""
    lms("unload", "--all")
    for ctx in (context_length, context_length // 2, context_length // 4):
        rc, out, err = lms(
            "load", model,
            "--context-length", str(ctx),
            "--parallel", str(parallel),
            "--gpu", "max",
            "--yes",
        )
        if rc == 0:
            print(f"  preload {model} ctx={ctx} parallel={parallel} -> ok", flush=True)
            return ctx
        print(
            f"  preload {model} ctx={ctx} 실패: {err.strip()[:200]}",
            flush=True,
        )
    print(f"  preload {model} 전부 실패 → JIT 로드에 의존", flush=True)
    return None


def call_model(client, model, prompt, schema, raw_text, max_tokens,
               use_schema=True, reasoning=None):
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": raw_text},
        ],
        temperature=TEMPERATURE,
        max_tokens=max_tokens,
    )
    if use_schema:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "daily_report",
                "strict": True,
                "schema": schema,
            },
        }
    if reasoning:
        kwargs["reasoning_effort"] = reasoning

    t0 = time.perf_counter()
    completion = client.chat.completions.create(**kwargs)
    elapsed = time.perf_counter() - t0

    choice = completion.choices[0]
    msg = choice.message
    usage = completion.usage
    reasoning_text = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
    return {
        "content": msg.content,
        "reasoning_chars": len(reasoning_text) if reasoning_text else 0,
        "finish_reason": getattr(choice, "finish_reason", None),
        "elapsed_s": round(elapsed, 3),
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
    }


def probe_config(client, model, prompt, schema, max_tokens, reasoning):
    """모델이 받아주는 (구조화 출력, reasoning_effort) 조합을 찾고 로딩 시간을 잰다."""
    combos = [
        (True, reasoning, f"json_schema+reasoning={reasoning}"),
        (True, None, "json_schema"),
        (False, reasoning, f"text+reasoning={reasoning}"),
        (False, None, "text"),
    ]
    for use_schema, eff, label in combos:
        try:
            t0 = time.perf_counter()
            call_model(
                client, model, prompt, schema,
                "테스트 보고입니다. 특별한 이슈 없습니다.",
                max_tokens, use_schema=use_schema, reasoning=eff,
            )
            warm = round(time.perf_counter() - t0, 2)
            print(f"  warmup[{label}] ok: {warm}s", flush=True)
            return use_schema, eff, label, warm
        except Exception as e:
            print(f"  warmup[{label}] 실패: {type(e).__name__}: {str(e)[:160]}", flush=True)
    return True, None, "failed", None


def run_model(client, model, prompt, schema, cases, out_dir, args):
    out_path = out_dir / f"{safe_name(model)}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = {} if args.force else read_done(out_path)
    if args.force and out_path.exists():
        out_path.unlink()

    todo = [c for c in cases if c["id"] not in done]
    print(f"\n=== {model} === (남은 케이스 {len(todo)}/{len(cases)})", flush=True)
    if not todo:
        return

    loaded_ctx = args.context_length
    if args.preload:
        loaded_ctx = preload(model, args.context_length, args.parallel) or args.context_length

    use_schema, eff, mode_label, warmup_s = probe_config(
        client, model, prompt, schema, args.max_tokens, args.reasoning
    )

    with open(out_path, "a", encoding="utf-8") as f:
        for i, case in enumerate(todo, 1):
            rec = {
                "model": model,
                "case_id": case["id"],
                "output_mode": mode_label,
                "reasoning_effort": eff,
                "max_tokens": args.max_tokens,
                "context_length": loaded_ctx if args.preload else None,
                "parallel": args.parallel if args.preload else None,
                "warmup_s": warmup_s,
            }
            last_err = None
            res = None
            attempts = 0
            # 일시적 400('terminated')이나 빈 응답은 재시도한다.
            for attempts in range(1, MAX_ATTEMPTS + 1):
                try:
                    res = call_model(
                        client, model, prompt, schema, case["raw"], args.max_tokens,
                        use_schema=use_schema, reasoning=eff,
                    )
                    last_err = None
                    if (res.get("content") or "").strip():
                        break
                    last_err = f"empty_content(finish={res.get('finish_reason')})"
                except Exception as e:
                    res = None
                    last_err = f"{type(e).__name__}: {str(e)[:300]}"
                time.sleep(1.0)

            rec["attempts"] = attempts
            if res is not None:
                rec.update(res)
                rec["error"] = last_err
            else:
                rec.update(
                    {
                        "content": None,
                        "reasoning_chars": None,
                        "finish_reason": None,
                        "elapsed_s": None,
                        "prompt_tokens": None,
                        "completion_tokens": None,
                        "error": last_err,
                    }
                )
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if rec["error"]:
                state = f"ERR({rec['error'][:40]})"
            else:
                state = f"{rec['elapsed_s']}s/{rec['completion_tokens']}tok"
            print(f"  [{i}/{len(todo)}] {case['id']} {state}", flush=True)


class _Tee:
    """stdout과 로그 파일에 동시에 쓴다 (백그라운드 실행 모니터링용)."""

    def __init__(self, path):
        self.file = open(path, "a", encoding="utf-8")
        self.stdout = sys.stdout

    def write(self, data):
        self.stdout.write(data)
        self.file.write(data)
        self.file.flush()

    def flush(self):
        self.stdout.flush()
        self.file.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="*", help="실행할 모델 id (생략 시 전체)")
    ap.add_argument("--force", action="store_true", help="기존 결과 삭제 후 재실행")
    ap.add_argument(
        "--reasoning", default="none", choices=["none", "low", "medium", "high"],
        help="reasoning_effort 값 (기본 none = 추론 끄기)",
    )
    ap.add_argument("--max-tokens", type=int, default=6144)
    ap.add_argument("--out-dir", default=str(DEFAULT_RAW_DIR))
    ap.add_argument(
        "--preload", action="store_true",
        help="lms CLI로 모델을 명시적 로드 (추론 모드에서는 필수)",
    )
    ap.add_argument("--context-length", type=int, default=32768)
    ap.add_argument(
        "--parallel", type=int, default=1,
        help="LM Studio parallel 슬롯 수. 컨텍스트가 이 수만큼 분할되므로 벤치마크는 1을 쓴다",
    )
    ap.add_argument("--prompt", default=None, help="사용할 프롬프트 파일 (기본 backend/model_asset/prompt.txt)")
    ap.add_argument(
        "--known-projects", default="none", choices=["none", "dataset", "names_only", "diverse", "fresh", "validation", "report"],
        help="prompt의 {{KNOWN_PROJECTS}} 슬롯 채우기. dataset은 DB에 프로젝트가 등록된 상황을 재현",
    )
    ap.add_argument(
        "--dataset", default="gold", choices=["gold", "diverse", "fresh", "validation", "report"],
        help="사용할 데이터셋 (gold=기존 32건, diverse=신규 32건, fresh=신규 32건, validation=검증 32건, report=자체 작성 테스트 보고 32건)",
    )
    args = ap.parse_args()

    prompt, schema, dataset = load_assets(args.prompt, args.known_projects, args.dataset)
    cases = dataset["cases"]
    targets = args.models or MODELS
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sys.stdout = _Tee(out_dir / "run_log.txt")

    print(
        f"설정: reasoning={args.reasoning} max_tokens={args.max_tokens} "
        f"preload={args.preload} ctx={args.context_length} parallel={args.parallel}",
        flush=True,
    )
    print(
        f"프롬프트: {args.prompt or 'backend/model_asset/prompt.txt'} "
        f"(known_projects={args.known_projects}, {len(prompt)}자)",
        flush=True,
    )
    print(f"출력: {out_dir}", flush=True)

    client = OpenAI(base_url=LM_BASE_URL, api_key=LM_API_KEY, timeout=TIMEOUT_S, max_retries=1)

    for model in targets:
        try:
            run_model(client, model, prompt, schema, cases, out_dir, args)
        except KeyboardInterrupt:
            print("중단됨", file=sys.stderr)
            raise
        except Exception as e:
            print(f"{model} 실행 실패: {type(e).__name__}: {e}", file=sys.stderr)

    print(f"\n완료. 채점: python benchmark/score_benchmark.py --raw-dir {out_dir}")


if __name__ == "__main__":
    main()
