"""정답 대비 오차 정성 분석 덤프.

사용법: python benchmark/error_report.py [모델id] [케이스id ...]
인수 없으면 모델별 최저 점수 케이스 3건씩을 results/error_analysis.md 로 저장한다.
"""

import json
import pathlib
import sys

import score_benchmark as sb

ROOT = pathlib.Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"


def load(raw_dir):
    with open(BENCH / "dataset" / "gold_dataset.json", encoding="utf-8") as f:
        dataset = json.load(f)
    raws = {}
    for path in sorted(pathlib.Path(raw_dir).glob("*.jsonl")):
        recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if recs:
            raws[recs[0]["model"]] = {r["case_id"]: r for r in recs}
    return dataset, raws


def fmt_projects(projects):
    out = []
    for p in projects:
        out.append(f"  - projectName: {p.get('projectName')!r}")
        for f in sb.FIELDS:
            items = p.get(f) or []
            if items:
                pretty = [
                    (i.get("content", "") + f" [{i.get('status')}]") if isinstance(i, dict) else str(i)
                    for i in items
                ]
                out.append(f"      {f}: {pretty}")
    return "\n".join(out) or "  (없음)"


def main():
    argv = [a for a in sys.argv[1:]]
    raw_dir = BENCH / "results" / "raw"
    prefix = ""
    if argv and argv[0].startswith("--raw-dir="):
        raw_dir = pathlib.Path(argv.pop(0).split("=", 1)[1])
    if argv and argv[0].startswith("--prefix="):
        prefix = argv.pop(0).split("=", 1)[1]

    dataset, raws = load(raw_dir)
    cases = {c["id"]: c for c in dataset["cases"]}
    args = argv

    if args:
        model = args[0]
        ids = args[1:] or list(cases)
        for cid in ids:
            rec = raws[model][cid]
            data, err = sb.coerce(rec.get("content"))
            print(f"\n===== {model} / {cid} ({cases[cid]['style']}) parse={err} =====")
            print("[원문]")
            print(cases[cid]["raw"])
            print("[정답]")
            print(fmt_projects(cases[cid]["gold"]["projects"]))
            print("[예측]")
            print(fmt_projects(data["projects"] if data else []))
        return

    with open(BENCH / "results" / f"{prefix}scores.json", encoding="utf-8") as f:
        scores = json.load(f)

    lines = ["# 오차 정성 분석 (모델별 최저 점수 케이스)", ""]
    for r in scores["results"]:
        model = r["model"]
        worst = sorted(r["per_case"], key=lambda c: c["f1"])[:3]
        lines.append(f"## {model}")
        for wc in worst:
            cid = wc["case_id"]
            rec = raws[model][cid]
            data, err = sb.coerce(rec.get("content"))
            lines += [
                "",
                f"### {cid} ({cases[cid]['style']}) — 케이스 F1 {wc['f1'] * 100:.1f}%, parse={err}",
                "",
                "원문:",
                "```",
                cases[cid]["raw"],
                "```",
                "정답:",
                "```",
                fmt_projects(cases[cid]["gold"]["projects"]),
                "```",
                "예측:",
                "```",
                fmt_projects(data["projects"] if data else []),
                "```",
            ]
        lines.append("")

    out = BENCH / "results" / f"{prefix}error_analysis.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("작성:", out)


if __name__ == "__main__":
    main()
