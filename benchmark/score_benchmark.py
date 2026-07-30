"""벤치마크 채점기.

results/raw/*.jsonl 의 모델 원시 응답을 gold_dataset.json 과 비교해
항목별 정확도(precision/recall/F1), JSON/스키마 준수율, 지연시간을 계산하고
results/scores.json, results/summary.csv, results/tables.md 를 만든다.

채점 방식
- 프로젝트 매칭: 표기 정규화 + 별칭 병합 후 완전일치, 남은 항목은 유사도 0.6 이상으로 매칭
- 항목 매칭: 매칭된 프로젝트 안에서 필드별로 문자 bigram Dice 유사도 0.5 이상이면 정답 처리(탐욕 매칭)
- 매칭되지 않은 정답 프로젝트의 항목은 전부 미검출(FN), 없는 프로젝트를 만들어낸 경우 항목은 전부 오검출(FP)

사용법: python benchmark/score_benchmark.py
"""

import csv
import json
import pathlib
import re
import statistics
import argparse

from jsonschema import Draft202012Validator

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
RAW_DIR = BENCH / "results" / "raw"
RES_DIR = BENCH / "results"

FIELDS = ["completedTasks", "inProgressTasks", "issues", "requests", "nextPlans"]
FIELD_KO = {
    "completedTasks": "완료 업무",
    "inProgressTasks": "진행 중 업무",
    "issues": "이슈",
    "requests": "협조 요청",
    "nextPlans": "다음 계획",
}

ITEM_SIM_THRESHOLD = 0.5
PROJECT_SIM_THRESHOLD = 0.6

# 표기 차이를 같은 프로젝트로 병합 (정규화된 키 기준)
PROJECT_ALIASES = {
    "mes": "a사mes",
    "a사mes구축": "a사mes",
    "a사mes시스템": "a사mes",
    "a사": "a사mes",
    "yakmap": "yakmap",
    "약맵": "yakmap",
    "약품지도": "yakmap",
    "미분류프로젝트": "미분류",
    "미분류": "미분류",
}


def normalize(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"[^0-9a-z가-힣]", "", text)
    return text


def canonical_project(name: str) -> str:
    key = normalize(name)
    return PROJECT_ALIASES.get(key, key)


def bigrams(s: str):
    if len(s) < 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def similarity(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ba, bb = bigrams(na), bigrams(nb)
    dice = 2 * len(ba & bb) / (len(ba) + len(bb)) if (ba or bb) else 0.0
    # 짧게 요약된 표현을 지나치게 불리하게 보지 않도록 포함 관계 보정
    if len(na) >= 4 and len(nb) >= 4 and (na in nb or nb in na):
        dice = max(dice, 0.75)
    return dice


def item_text(field: str, item) -> str:
    if field == "issues":
        if isinstance(item, dict):
            return str(item.get("content", ""))
        return str(item)
    if isinstance(item, dict):
        return json.dumps(item, ensure_ascii=False)
    return str(item)


def item_status(item) -> str:
    if isinstance(item, dict):
        return str(item.get("status", "미해결"))
    return "미해결"


def greedy_match(gold_items, pred_items, field):
    """(matched_pairs, unmatched_gold_idx, unmatched_pred_idx)"""
    pairs = []
    for gi, g in enumerate(gold_items):
        for pi, p in enumerate(pred_items):
            s = similarity(item_text(field, g), item_text(field, p))
            if s >= ITEM_SIM_THRESHOLD:
                pairs.append((s, gi, pi))
    pairs.sort(reverse=True)
    used_g, used_p, matched = set(), set(), []
    for s, gi, pi in pairs:
        if gi in used_g or pi in used_p:
            continue
        used_g.add(gi)
        used_p.add(pi)
        matched.append((gi, pi, s))
    ug = [i for i in range(len(gold_items)) if i not in used_g]
    up = [i for i in range(len(pred_items)) if i not in used_p]
    return matched, ug, up


def match_projects(gold_projects, pred_projects):
    gold_keys = [canonical_project(p.get("projectName", "")) for p in gold_projects]
    pred_keys = [canonical_project(p.get("projectName", "")) for p in pred_projects]
    used_g, used_p, matched = set(), set(), []

    for gi, gk in enumerate(gold_keys):
        for pi, pk in enumerate(pred_keys):
            if pi in used_p or gi in used_g:
                continue
            if gk and gk == pk:
                used_g.add(gi)
                used_p.add(pi)
                matched.append((gi, pi, 1.0))

    cands = []
    for gi in range(len(gold_projects)):
        if gi in used_g:
            continue
        for pi in range(len(pred_projects)):
            if pi in used_p:
                continue
            s = similarity(gold_keys[gi], pred_keys[pi])
            if s >= PROJECT_SIM_THRESHOLD:
                cands.append((s, gi, pi))
    cands.sort(reverse=True)
    for s, gi, pi in cands:
        if gi in used_g or pi in used_p:
            continue
        used_g.add(gi)
        used_p.add(pi)
        matched.append((gi, pi, s))

    ug = [i for i in range(len(gold_projects)) if i not in used_g]
    up = [i for i in range(len(pred_projects)) if i not in used_p]
    return matched, ug, up


def prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def coerce(content):
    """백엔드 coerce_report_data 와 동일한 관용 파싱 + 코드블록 제거."""
    if not content or not str(content).strip():
        return None, "empty"
    text = str(content).strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    candidate = text[start : end + 1] if start != -1 and end > start else text
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None, "json_error"
    if not isinstance(data, dict):
        return None, "not_object"
    if not isinstance(data.get("projects"), list):
        return None, "no_projects"
    return data, None


def score_model(model, records, cases, validator):
    by_case = {r["case_id"]: r for r in records}
    field_counts = {f: {"tp": 0, "fp": 0, "fn": 0} for f in FIELDS}
    proj_tp = proj_fp = proj_fn = 0
    status_total = status_correct = 0
    latencies, tps_list = [], []
    n_total = len(cases)
    n_called = n_json_ok = n_schema_ok = n_error = n_truncated = 0
    empty_total = empty_correct = 0
    per_case = []

    for case in cases:
        rec = by_case.get(case["id"])
        gold_projects = case["gold"]["projects"]
        if rec is None:
            for f in FIELDS:
                field_counts[f]["fn"] += len(
                    [x for p in gold_projects for x in p.get(f, [])]
                )
            proj_fn += len(gold_projects)
            continue

        n_called += 1
        if rec.get("error"):
            n_error += 1
        if rec.get("finish_reason") == "length":
            n_truncated += 1
        if rec.get("elapsed_s"):
            latencies.append(rec["elapsed_s"])
            if rec.get("completion_tokens"):
                tps_list.append(rec["completion_tokens"] / rec["elapsed_s"])

        data, parse_err = coerce(rec.get("content"))
        json_ok = data is not None
        if json_ok:
            n_json_ok += 1
            if not list(validator.iter_errors(data)):
                n_schema_ok += 1
        pred_projects = data["projects"] if json_ok else []

        if not gold_projects:
            empty_total += 1
            if not pred_projects:
                empty_correct += 1

        matched, ug, up = match_projects(gold_projects, pred_projects)
        proj_tp += len(matched)
        proj_fn += len(ug)
        proj_fp += len(up)

        case_counts = {f: {"tp": 0, "fp": 0, "fn": 0} for f in FIELDS}

        for gi, pi, _ in matched:
            gp, pp = gold_projects[gi], pred_projects[pi]
            for f in FIELDS:
                g_items = gp.get(f, []) or []
                p_items = pp.get(f, []) or []
                if not isinstance(p_items, list):
                    p_items = []
                mp, mug, mup = greedy_match(g_items, p_items, f)
                case_counts[f]["tp"] += len(mp)
                case_counts[f]["fn"] += len(mug)
                case_counts[f]["fp"] += len(mup)
                if f == "issues":
                    for a, b, _s in mp:
                        status_total += 1
                        if item_status(g_items[a]) == item_status(p_items[b]):
                            status_correct += 1

        for gi in ug:
            for f in FIELDS:
                case_counts[f]["fn"] += len(gold_projects[gi].get(f, []) or [])
        for pi in up:
            for f in FIELDS:
                items = pred_projects[pi].get(f, []) or []
                case_counts[f]["fp"] += len(items) if isinstance(items, list) else 0

        for f in FIELDS:
            for k in ("tp", "fp", "fn"):
                field_counts[f][k] += case_counts[f][k]

        tp = sum(case_counts[f]["tp"] for f in FIELDS)
        fp = sum(case_counts[f]["fp"] for f in FIELDS)
        fn = sum(case_counts[f]["fn"] for f in FIELDS)
        _, _, cf1 = prf(tp, fp, fn)
        if tp + fp + fn == 0:
            # 정답도 예측도 비어 있는 경우(업무 없는 보고)는 정답 처리
            cf1 = 1.0
        per_case.append(
            {
                "case_id": case["id"],
                "style": case["style"],
                "json_ok": json_ok,
                "parse_error": parse_err,
                "elapsed_s": rec.get("elapsed_s"),
                "f1": round(cf1, 4),
            }
        )

    field_scores = {}
    for f in FIELDS:
        c = field_counts[f]
        p, r, f1 = prf(c["tp"], c["fp"], c["fn"])
        field_scores[f] = {
            "tp": c["tp"],
            "fp": c["fp"],
            "fn": c["fn"],
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
        }

    tp = sum(field_counts[f]["tp"] for f in FIELDS)
    fp = sum(field_counts[f]["fp"] for f in FIELDS)
    fn = sum(field_counts[f]["fn"] for f in FIELDS)
    micro_p, micro_r, micro_f1 = prf(tp, fp, fn)
    macro_f1 = statistics.mean(field_scores[f]["f1"] for f in FIELDS)
    pp, pr, pf1 = prf(proj_tp, proj_fp, proj_fn)

    return {
        "model": model,
        "cases_total": n_total,
        "cases_called": n_called,
        "api_errors": n_error,
        "truncated": n_truncated,
        "json_valid_rate": round(n_json_ok / n_total, 4),
        "schema_valid_rate": round(n_schema_ok / n_total, 4),
        "output_mode": records[0].get("output_mode") if records else None,
        "project_precision": round(pp, 4),
        "project_recall": round(pr, 4),
        "project_f1": round(pf1, 4),
        "micro_precision": round(micro_p, 4),
        "micro_recall": round(micro_r, 4),
        "micro_f1": round(micro_f1, 4),
        "macro_f1": round(macro_f1, 4),
        "issue_status_accuracy": round(status_correct / status_total, 4) if status_total else None,
        "empty_report_accuracy": round(empty_correct / empty_total, 4) if empty_total else None,
        "latency_mean_s": round(statistics.mean(latencies), 2) if latencies else None,
        "latency_median_s": round(statistics.median(latencies), 2) if latencies else None,
        "latency_max_s": round(max(latencies), 2) if latencies else None,
        "tokens_per_s": round(statistics.mean(tps_list), 1) if tps_list else None,
        "fields": field_scores,
        "per_case": per_case,
    }


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


def pct(x):
    return "-" if x is None else f"{x * 100:.1f}%"


def main():
    global RAW_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=None, help="채점할 원시 응답 디렉터리")
    ap.add_argument("--prefix", default="", help="출력 파일 접두어 (예: run1_)")
    args = ap.parse_args()
    if args.raw_dir:
        RAW_DIR = pathlib.Path(args.raw_dir)
    prefix = args.prefix

    with open(BENCH / "dataset" / "gold_dataset.json", encoding="utf-8") as f:
        dataset = json.load(f)
    with open(ROOT / "backend" / "model_asset" / "json_Schema.json", encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft202012Validator(schema)
    cases = dataset["cases"]

    results = []
    for path in sorted(RAW_DIR.glob("*.jsonl")):
        records = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        if not records:
            continue
        model = records[0]["model"]
        results.append(score_model(model, records, cases, validator))

    results.sort(key=lambda r: r["micro_f1"], reverse=True)

    RES_DIR.mkdir(parents=True, exist_ok=True)
    with open(RES_DIR / f"{prefix}scores.json", "w", encoding="utf-8") as f:
        json.dump({"dataset": dataset["meta"], "results": results}, f, ensure_ascii=False, indent=2)

    csv_cols = [
        "model", "output_mode", "json_valid_rate", "schema_valid_rate",
        "project_f1", "micro_precision", "micro_recall", "micro_f1", "macro_f1",
        "issue_status_accuracy", "empty_report_accuracy",
        "latency_mean_s", "latency_median_s", "latency_max_s", "tokens_per_s",
        "api_errors", "truncated",
    ]
    with open(RES_DIR / f"{prefix}summary.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_cols, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow(r)

    lines = ["## 종합 순위 (micro F1 기준)", ""]
    lines.append(
        md_table(
            ["순위", "모델", "출력 모드", "JSON 유효", "스키마 준수", "프로젝트 F1",
             "정밀도", "재현율", "micro F1", "macro F1", "평균 지연", "tok/s"],
            [
                [
                    i, r["model"], r["output_mode"], pct(r["json_valid_rate"]),
                    pct(r["schema_valid_rate"]), pct(r["project_f1"]),
                    pct(r["micro_precision"]), pct(r["micro_recall"]),
                    pct(r["micro_f1"]), pct(r["macro_f1"]),
                    f"{r['latency_mean_s']}s" if r["latency_mean_s"] else "-",
                    r["tokens_per_s"] or "-",
                ]
                for i, r in enumerate(results, 1)
            ],
        )
    )

    lines += ["", "## 항목별 추출 정확도 (F1)", ""]
    lines.append(
        md_table(
            ["모델"] + [FIELD_KO[f] for f in FIELDS] + ["이슈 상태 정확도", "빈 보고 처리"],
            [
                [r["model"]] + [pct(r["fields"][f]["f1"]) for f in FIELDS]
                + [pct(r["issue_status_accuracy"]), pct(r["empty_report_accuracy"])]
                for r in results
            ],
        )
    )

    lines += ["", "## 작성 스타일별 평균 케이스 F1", ""]
    case_style = {c["id"]: c["style"] for c in cases}
    styles = sorted(set(case_style.values()))
    style_rows = []
    for s in styles:
        row = [s, sum(1 for v in case_style.values() if v == s)]
        for r in results:
            vals = [pc["f1"] for pc in r["per_case"] if case_style.get(pc["case_id"]) == s]
            row.append(pct(statistics.mean(vals)) if vals else "-")
        style_rows.append(row)
    lines.append(md_table(["스타일", "건수"] + [r["model"] for r in results], style_rows))

    for r in results:
        lines += ["", f"### {r['model']} — 항목별 상세", ""]
        lines.append(
            md_table(
                ["항목", "정답 수", "정탐(TP)", "오탐(FP)", "미탐(FN)", "정밀도", "재현율", "F1"],
                [
                    [
                        FIELD_KO[f],
                        r["fields"][f]["tp"] + r["fields"][f]["fn"],
                        r["fields"][f]["tp"],
                        r["fields"][f]["fp"],
                        r["fields"][f]["fn"],
                        pct(r["fields"][f]["precision"]),
                        pct(r["fields"][f]["recall"]),
                        pct(r["fields"][f]["f1"]),
                    ]
                    for f in FIELDS
                ],
            )
        )

    with open(RES_DIR / f"{prefix}tables.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    for r in results:
        print(
            f"{r['model']:<28} microF1={pct(r['micro_f1'])} json={pct(r['json_valid_rate'])} "
            f"lat={r['latency_mean_s']}s"
        )
    print(f"\n결과: {RES_DIR / (prefix + 'scores.json')}, {prefix}summary.csv, {prefix}tables.md")


if __name__ == "__main__":
    main()
