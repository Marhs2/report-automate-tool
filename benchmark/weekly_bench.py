"""주간보고 프롬프트 벤치마크 실행 + 채점.

일일보고 gold 데이터셋(32건, 4명 × ~8일)을 멤버별로 모아 주간 입력 JSON으로 만들고,
weekly_prompt.txt(v1) vs weekly_prompt_v2.txt(v2) 를 각 모델(추론 끄기)에 적용해
주간 병합 품질을 비교한다.

gold 주간 결과는 daily gold JSON 을 '병합 규칙'에 따라 직접 조립해 만든다:
- completedTasks: 일일 completedTasks 전체 (중복 제거, 보존)
- inProgressTasks: 일일 inProgressTasks 전체 (중복 제거)
- issues: 일일 issues 전체 (중복 제거, status 유지 — 여기선 승격/해결 시나리오가 없으므로 유지)
- nextWeekPlans: 일일 requests + nextPlans 전체 (중복 제거)
- projectName: 정식 명칭으로 통일 (aliases)

주간 병합은 '추가·승격·해결'이 없는 단순 집계 형태이므로, 이 gold 는 프롬프트의
'복사와 병합만 수행, 환각 금지' 원칙에 대한 충실도를 측정한다.
(실제 상태 승격/이슈 해결 판정은 주간 gold 를 수동 라벨링하지 않는 한 측정 불가 —
이 스크립트는 병합·중복제거·projectName 통일·환각 억제를 검증한다.)

사용법:
    python benchmark/weekly_bench.py --model nuextract3
    python benchmark/weekly_bench.py --model qwen3.5-4b
    python benchmark/weekly_bench.py --model nuextract3 --prompt-v2
    python benchmark/weekly_bench.py --model qwen3.5-4b --reasoning high
"""

import argparse
import json
import pathlib
import re
import statistics
import sys
import time

from openai import OpenAI

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
sys.path.insert(0, str(BENCH))
from score_benchmark import FIELDS, bigrams, canonical_project, item_text, item_status, normalize, prf, similarity

LM_BASE_URL = "http://127.0.0.1:1234/v1"
LM_API_KEY = "lm-studio"
DATASET = "fresh"  # gold/diverse/fresh 중 선택. fresh 가 가장 어렵고 미지 도메인

WEEKLY_FIELDS = ["completedTasks", "inProgressTasks", "issues", "nextWeekPlans"]


def load_daily_prompt(prompt_path):
    with open(prompt_path, encoding="utf-8") as f:
        return f.read()


def assemble_weekly_inputs(dataset_name=DATASET):
    """일일 gold 케이스를 멤버별로 모아 주간 입력 JSON + gold 주간 JSON 을 만든다."""
    fn = {
        "gold": "gold_dataset.json",
        "diverse": "gold_dataset_diverse.json",
        "fresh": "gold_dataset_fresh.json",
    }[dataset_name]
    with open(BENCH / "dataset" / fn, encoding="utf-8") as f:
        d = json.load(f)
    cases = d["cases"]
    members = {}
    for c in cases:
        members.setdefault(c["member"], []).append(c)
    weekly = []
    for mem, mcases in sorted(members.items()):
        mcases.sort(key=lambda c: c["date"])
        # 주간 입력: 각 일일 gold 의 projects 배열 (원문 JSON 그대로)
        inputs = [c["gold"] for c in mcases]
        # gold 주간: 병합 규칙대로 조립
        merged = {}
        for c in mcases:
            for p in c["gold"]["projects"]:
                name = canonical_project(p.get("projectName", ""))
                d = merged.setdefault(name, {
                    "projectName": p.get("projectName", ""),
                    "completedTasks": [],
                    "inProgressTasks": [],
                    "issues": [],
                    "nextWeekPlans": [],
                })
                d["completedTasks"].extend(p.get("completedTasks", []) or [])
                d["inProgressTasks"].extend(p.get("inProgressTasks", []) or [])
                d["issues"].extend(p.get("issues", []) or [])
                d["nextWeekPlans"].extend(p.get("requests", []) or [])
                d["nextWeekPlans"].extend(p.get("nextPlans", []) or [])
        gold_projects = []
        for name, d in merged.items():
            # 정식 명칭으로 통일 (aliases 에 맞춤)
            canon = canonical_project(d["projectName"])
            # 원문 표기 복원: canonical key → 원래 있던 표기 중 가장 흔한 것
            name_by_key = {}
            for c in mcases:
                for p in c["gold"]["projects"]:
                    name_by_key.setdefault(canonical_project(p.get("projectName", "")), p["projectName"])
            proj = {
                "projectName": name_by_key.get(canon, d["projectName"]),
                "completedTasks": list(dict.fromkeys(d["completedTasks"])),
                "inProgressTasks": list(dict.fromkeys(d["inProgressTasks"])),
                "issues": [],
                "nextWeekPlans": list(dict.fromkeys(d["nextWeekPlans"])),
            }
            seen = set()
            for iss in d["issues"]:
                key = item_text("issues", iss)
                if key not in seen:
                    seen.add(key)
                    proj["issues"].append(iss)
            if any(proj[k] for k in WEEKLY_FIELDS):
                gold_projects.append(proj)
        weekly.append({
            "id": f"W-{mem}",
            "member": mem,
            "dates": [c["date"] for c in mcases],
            "input_json": inputs,
            "gold": {"projects": gold_projects},
        })
    return weekly


def call_weekly(client, model, prompt, weekly_schema, input_json, max_tokens, reasoning):
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(input_json, ensure_ascii=False)},
        ],
        temperature=0.1,
        max_tokens=max_tokens,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "weekly_report", "strict": True, "schema": weekly_schema},
        },
    )
    if reasoning:
        kwargs["reasoning_effort"] = reasoning
    t0 = time.perf_counter()
    resp = client.chat.completions.create(**kwargs)
    elapsed = time.perf_counter() - t0
    msg = resp.choices[0].message
    usage = resp.usage
    return {
        "content": msg.content,
        "finish_reason": getattr(resp.choices[0], "finish_reason", None),
        "elapsed_s": round(elapsed, 3),
        "prompt_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
        "completion_tokens": getattr(usage, "completion_tokens", None) if usage else None,
    }


def coerce(content):
    if not content or not str(content).strip():
        return None, "empty"
    text = str(content).strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    candidate = text[start:end + 1] if start != -1 and end > start else text
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None, "json_error"
    if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
        return None, "no_projects"
    return data, None


def match_projects(gold_projects, pred_projects):
    gk = [canonical_project(p.get("projectName", "")) for p in gold_projects]
    pk = [canonical_project(p.get("projectName", "")) for p in pred_projects]
    pairs = []
    for gi, g in enumerate(gk):
        for pi, p in enumerate(pk):
            pairs.append((similarity(g, p), gi, pi))
    pairs.sort(reverse=True)
    used_g, used_p, m = set(), set(), []
    for s, gi, pi in pairs:
        if gi in used_g or pi in used_p:
            continue
        if s >= 0.6:
            used_g.add(gi)
            used_p.add(pi)
            m.append((gi, pi, s))
    return m


def score_weekly(gold, pred, fields=WEEKLY_FIELDS):
    """gold/pred: {"projects": [...]}. 항목 정확도(precision/recall/F1) + 프로젝트 매칭."""
    if not isinstance(pred, dict):
        pred = {}
    pred_projects = pred.get("projects", []) if isinstance(pred, dict) else []
    matched = match_projects(gold["projects"], pred_projects)
    field_counts = {f: {"tp": 0, "fp": 0, "fn": 0} for f in fields}
    proj_tp = proj_fp = proj_fn = 0
    g_idx = {gi for gi, _, _ in matched}
    p_idx = {pi for _, pi, _ in matched}
    proj_tp += len(matched)
    proj_fn += len(gold["projects"]) - len(g_idx)
    proj_fp += len(pred_projects) - len(p_idx)

    for gi, pi, _ in matched:
        gp, pp = gold["projects"][gi], pred_projects[pi]
        for f in fields:
            g_items = gp.get(f, []) or []
            p_items = pp.get(f, []) or []
            if not isinstance(p_items, list):
                p_items = []
            g_txt = [item_text(f, x) for x in g_items]
            p_txt = [item_text(f, x) for x in p_items]
            pairs = []
            for a, gt in enumerate(g_txt):
                for b, pt in enumerate(p_txt):
                    pairs.append((similarity(gt, pt), a, b))
            pairs.sort(reverse=True)
            used_g, used_p = set(), set()
            for s, a, b in pairs:
                if a in used_g or b in used_p:
                    continue
                if s >= 0.5:
                    used_g.add(a)
                    used_p.add(b)
            field_counts[f]["tp"] += len(used_g)
            field_counts[f]["fp"] += len(p_txt) - len(used_p)
            field_counts[f]["fn"] += len(g_txt) - len(used_g)

    for gi in range(len(gold["projects"])):
        if gi not in g_idx:
            for f in fields:
                field_counts[f]["fn"] += len(gold["projects"][gi].get(f, []) or [])
    for pi in range(len(pred_projects)):
        if pi not in p_idx:
            for f in fields:
                field_counts[f]["fp"] += len(pred_projects[pi].get(f, []) or [])

    tp = sum(field_counts[f]["tp"] for f in fields)
    fp = sum(field_counts[f]["fp"] for f in fields)
    fn = sum(field_counts[f]["fn"] for f in fields)
    p, r, f1 = prf(tp, fp, fn)
    pp, pr, pf1 = prf(proj_tp, proj_fp, proj_fn)
    return {
        "micro_f1": f1,
        "precision": p,
        "recall": r,
        "project_f1": pf1,
        "field_scores": {f: dict(zip(["tp", "fp", "fn"], field_counts[f].values())) for f in fields},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="nuextract3", help="LM Studio 모델 id")
    ap.add_argument("--prompt-v2", action="store_true", help="weekly_prompt_v2.txt 사용 (기본은 v1)")
    ap.add_argument("--reasoning", default="none", choices=["none", "low", "medium", "high"])
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--dataset", default=DATASET, choices=["gold", "diverse", "fresh"])
    args = ap.parse_args()

    prompt_file = "weekly_prompt_v2.txt" if args.prompt_v2 else "weekly_prompt.txt"
    with open(ROOT / "backend" / "model_asset" / prompt_file, encoding="utf-8") as f:
        prompt = f.read()
    with open(ROOT / "backend" / "model_asset" / "weekly_json_schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    # {{KNOWN_PROJECTS}} 채우기 (fresh 데이터셋 프로젝트)
    from run_benchmark import KNOWN_PROJECTS_FRESH
    prompt = prompt.replace("{{KNOWN_PROJECTS}}", KNOWN_PROJECTS_FRESH)

    weekly = assemble_weekly_inputs(args.dataset)
    print(f"프롬프트: {prompt_file} ({len(prompt)}자) | 모델: {args.model} | reasoning={args.reasoning} | 주간 케이스 {len(weekly)}건", flush=True)

    client = OpenAI(base_url=LM_BASE_URL, api_key=LM_API_KEY, timeout=900, max_retries=1)

    results = []
    for w in weekly:
        rec = None
        for attempt in range(3):
            try:
                rec = call_weekly(client, args.model, prompt, schema, w["input_json"], args.max_tokens, args.reasoning)
                if (rec.get("content") or "").strip():
                    break
                rec = None
            except Exception as e:
                print(f"  {w['id']} 호출 실패({attempt+1}): {type(e).__name__}: {str(e)[:100]}")
                rec = None
        if rec is None:
            results.append({"id": w["id"], "error": "call_failed", "micro_f1": 0.0})
            continue
        data, parse_err = coerce(rec["content"])
        if data is None:
            results.append({"id": w["id"], "error": parse_err, "micro_f1": 0.0})
            continue
        score = score_weekly(w["gold"], data)
        results.append({"id": w["id"], "error": None, **score, "latency_s": rec["elapsed_s"]})

    # 출력
    f1s = [r["micro_f1"] for r in results]
    avg = statistics.mean(f1s) if f1s else 0.0
    print("\n=== 주간 병합 결과 (case F1) ===")
    for r in results:
        extra = f" (error: {r['error']})" if r.get("error") else f" (lat={r.get('latency_s')}s)"
        print(f"{r['id']:<8} microF1={r['micro_f1']:.3f}{extra}")
    print(f"\n평균 주간 microF1: {avg:.3f}")
    # 필드별 평균
    field_tp = {f: 0 for f in WEEKLY_FIELDS}
    field_fp = {f: 0 for f in WEEKLY_FIELDS}
    field_fn = {f: 0 for f in WEEKLY_FIELDS}
    for r in results:
        for f in WEEKLY_FIELDS:
            fs = r.get("field_scores", {}).get(f, {})
            field_tp[f] += fs.get("tp", 0)
            field_fp[f] += fs.get("fp", 0)
            field_fn[f] += fs.get("fn", 0)
    print("\n=== 필드별 (총) ===")
    for f in WEEKLY_FIELDS:
        p, r_, f1 = prf(field_tp[f], field_fp[f], field_fn[f])
        print(f"{f:<18} TP={field_tp[f]} FP={field_fp[f]} FN={field_fn[f]} F1={f1:.3f}")


if __name__ == "__main__":
    main()
