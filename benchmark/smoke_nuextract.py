"""NuExtract3 빠른 스모크 테스트 — 프롬프트 개선 이터레이션용.

전체 32건 대신 실패가 집중된 케이스만 골라 호출하고 score_benchmark 와 동일한
채점 로직으로 case F1과 프로젝트명 일치를 바로 보여준다.

사용법:
    python benchmark/smoke_nuextract.py --prompt backend/model_asset/prompt.txt
    python benchmark/smoke_nuextract.py --prompt ... --cases D22 D25 D11 D07 D15 D03 D12 D30 D16 D20 D26
    python benchmark/smoke_nuextract.py --prompt ... --known-projects dataset
"""

import argparse
import json
import pathlib
import sys

from openai import OpenAI

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
sys.path.insert(0, str(BENCH))
from run_benchmark import KNOWN_PROJECTS_DATASET, KNOWN_PROJECTS_DIVERSE, KNOWN_PROJECTS_FRESH, KNOWN_PROJECTS_NAMES_ONLY, KNOWN_PROJECTS_NONE, load_assets

LM_BASE_URL = "http://127.0.0.1:1234/v1"
LM_API_KEY = "lm-studio"

DEFAULT_CASES = ["D01", "D02", "D03", "D05", "D07", "D10", "D11", "D12", "D13",
                 "D14", "D15", "D16", "D19", "D20", "D22", "D24", "D25", "D26",
                 "D27", "D28", "D30", "D31", "D32"]

FIELDS = ["completedTasks", "inProgressTasks", "issues", "requests", "nextPlans"]


def norm(t):
    import re
    return re.sub(r"[^0-9a-z가-힣]", "", str(t).lower())


def bigrams(s):
    if len(s) < 2:
        return {s} if s else set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def sim(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ba, bb = bigrams(na), bigrams(nb)
    d = 2 * len(ba & bb) / (len(ba) + len(bb)) if (ba or bb) else 0.0
    if len(na) >= 4 and len(nb) >= 4 and (na in nb or nb in na):
        d = max(d, 0.75)
    return d


def match_projects(gold, pred):
    from score_benchmark import canonical_project
    gk = [canonical_project(p.get("projectName", "")) for p in gold]
    pk = [canonical_project(p.get("projectName", "")) for p in pred]
    pairs = []
    for gi, g in enumerate(gk):
        for pi, p in enumerate(pk):
            pairs.append((sim(g, p), gi, pi))
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


def score_case(gold, pred):
    """gold/pred: projects list. Returns (f1, per-field detail string)."""
    matched = match_projects(gold, pred)
    tp = fp = fn = 0
    detail = []
    for gi, pi, _ in matched:
        gp, pp = gold[gi], pred[pi]
        for f in FIELDS:
            g_items = gp.get(f, []) or []
            p_items = pp.get(f, []) or []
            if not isinstance(p_items, list):
                p_items = []
            g_txt = [x.get("content", "") if isinstance(x, dict) else str(x) for x in g_items]
            p_txt = [x.get("content", "") if isinstance(x, dict) else str(x) for x in p_items]
            pairs = []
            for a, gt in enumerate(g_txt):
                for b, pt in enumerate(p_txt):
                    pairs.append((sim(gt, pt), a, b))
            pairs.sort(reverse=True)
            used_g, used_p = set(), set()
            for s, a, b in pairs:
                if a in used_g or b in used_p:
                    continue
                if s >= 0.5:
                    used_g.add(a)
                    used_p.add(b)
            tp += len(used_g)
            fp += len(p_txt) - len(used_p)
            fn += len(g_txt) - len(used_g)
            miss = [g_txt[i] for i in range(len(g_txt)) if i not in used_g]
            extra = [p_txt[i] for i in range(len(p_txt)) if i not in used_p]
            if miss or extra:
                detail.append(f"{f}: -{miss} +{extra}")
    g_idx = {gi for gi, _, _ in matched}
    p_idx = {pi for _, pi, _ in matched}
    for gi, gp in enumerate(gold):
        if gi not in g_idx:
            fn += sum(len(gp.get(f, []) or []) for f in FIELDS)
    for pi, pp in enumerate(pred):
        if pi not in p_idx:
            fp += sum(len(pp.get(f, []) or []) for f in FIELDS)
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else (1.0 if (tp + fp + fn == 0) else 0.0)
    return f1, detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--cases", nargs="*", default=DEFAULT_CASES)
    ap.add_argument("--known-projects", default="none", choices=["none", "dataset", "names_only", "diverse", "fresh"])
    ap.add_argument("--dataset", default="gold", choices=["gold", "diverse", "fresh"])
    ap.add_argument("--max-tokens", type=int, default=6144)
    ap.add_argument("--reasoning", default="none", choices=["none", "low", "medium", "high"])
    args = ap.parse_args()

    prompt, schema, dataset = load_assets(args.prompt, args.known_projects, args.dataset)
    filler = KNOWN_PROJECTS_DATASET if args.known_projects == "dataset" else KNOWN_PROJECTS_NONE
    if args.known_projects == "names_only":
        filler = KNOWN_PROJECTS_NAMES_ONLY
    if args.known_projects == "diverse":
        filler = KNOWN_PROJECTS_DIVERSE
    if args.known_projects == "fresh":
        filler = KNOWN_PROJECTS_FRESH
    prompt = prompt.replace("{{KNOWN_PROJECTS}}", filler)
    cases = {c["id"]: c for c in dataset["cases"]}
    todo = [cases[cid] for cid in args.cases if cid in cases]
    print(f"프롬프트: {args.prompt or 'backend/model_asset/prompt.txt'} ({len(prompt)}자), "
          f"known_projects={args.known_projects}, 케이스 {len(todo)}건", flush=True)

    client = OpenAI(base_url=LM_BASE_URL, api_key=LM_API_KEY, timeout=900, max_retries=1)
    kwargs = dict(
        model="nuextract3",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": None},
        ],
        temperature=0.1,
        max_tokens=args.max_tokens,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "daily_report", "strict": True, "schema": schema},
        },
    )
    if args.reasoning != "none":
        kwargs["reasoning_effort"] = args.reasoning

    results = []
    for case in todo:
        kwargs["messages"][1]["content"] = case["raw"]
        content = None
        for attempt in range(3):
            try:
                resp = client.chat.completions.create(**kwargs)
                content = resp.choices[0].message.content
                if (content or "").strip():
                    break
            except Exception as e:
                print(f"  {case['id']} 호출 실패({attempt+1}): {type(e).__name__}: {str(e)[:100]}")
                content = None
        if not content:
            results.append((case["id"], 0.0, ["호출 실패"]))
            continue
        try:
            data = json.loads(content[content.find("{"):content.rfind("}") + 1])
            pred_projects = data.get("projects", [])
        except Exception as e:
            results.append((case["id"], 0.0, [f"파싱 실패: {e}"]))
            continue
        f1, detail = score_case(case["gold"]["projects"], pred_projects)
        gnames = [p["projectName"] for p in case["gold"]["projects"]]
        pnames = [p.get("projectName", "") for p in pred_projects]
        flags = []
        if gnames != pnames:
            flags.append(f"프로젝트명: gold={gnames} pred={pnames}")
        results.append((case["id"], f1, detail + flags))

    print("\n=== 결과 (case F1) ===")
    tot_f1 = 0
    for cid, f1, detail in results:
        tot_f1 += f1
        print(f"{cid}: {f1:.3f}  {'; '.join(detail)[:220]}")
    print(f"\n평균 케이스 F1: {tot_f1/len(results):.3f}")


if __name__ == "__main__":
    main()
