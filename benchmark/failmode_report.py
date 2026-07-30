"""모델별 실패 유형 집계.

정답 항목을 뽑는 능력과, 그 항목을 올바른 프로젝트에 붙이는 능력을 분리해서 본다.
results/failmodes.md 를 만든다.

사용법: python benchmark/failmode_report.py
"""

import collections
import json
import pathlib
import argparse

import score_benchmark as sb

BENCH = pathlib.Path(__file__).resolve().parent

# backend/model_asset/prompt.txt 의 예시에만 등장하는 문구.
# 입력에 없는데 출력에 나오면 모델이 예시를 입력으로 착각한 것이다.
PROMPT_EXAMPLE_MARKERS = ["로그인 오류", "API 연동 테스트", "결제 모듈", "스테이징 배포", "QA 일정 공유"]

COLS = [
    ("merged", "복수 프로젝트를 하나로 병합"),
    ("wrong_project", "프로젝트 전부 오인"),
    ("unclassified", "미분류로 떠넘김"),
    ("empty", "빈 결과"),
    ("parse_fail", "파싱 실패"),
    ("contaminated", "프롬프트 예시 오염"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=str(BENCH / "results" / "raw"))
    ap.add_argument("--prefix", default="")
    args = ap.parse_args()
    raw_dir = pathlib.Path(args.raw_dir)

    with open(BENCH / "dataset" / "gold_dataset.json", encoding="utf-8") as f:
        dataset = json.load(f)
    cases = {c["id"]: c for c in dataset["cases"]}
    gold_item_total = sum(
        len(p.get(f) or []) for c in cases.values() for p in c["gold"]["projects"] for f in sb.FIELDS
    )
    multi_total = sum(1 for c in cases.values() if len(c["gold"]["projects"]) > 1)

    rows = []
    for path in sorted(raw_dir.glob("*.jsonl")):
        recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not recs:
            continue
        stats = collections.Counter()
        items = 0
        for r in recs:
            case = cases[r["case_id"]]
            gold_projects = case["gold"]["projects"]
            content = r.get("content") or ""
            if any(m in content for m in PROMPT_EXAMPLE_MARKERS):
                stats["contaminated"] += 1
            data, _err = sb.coerce(content)
            if data is None:
                stats["parse_fail"] += 1
                continue
            preds = data["projects"]
            items += sum(
                len(p.get(f) or []) for p in preds
                for f in sb.FIELDS if isinstance(p.get(f) or [], list)
            )
            if not preds and gold_projects:
                stats["empty"] += 1
            names = [sb.canonical_project(p.get("projectName", "")) for p in preds]
            gold_names = {sb.canonical_project(p["projectName"]) for p in gold_projects}
            if "미분류" in names:
                stats["unclassified"] += 1
            if preds and gold_projects and not (set(names) & gold_names):
                stats["wrong_project"] += 1
            if len(gold_projects) > 1 and len(preds) == 1:
                stats["merged"] += 1
        rows.append((recs[0]["model"], stats, items))

    rows.sort(key=lambda x: sum(x[1].values()))

    lines = [
        "# 모델별 실패 유형 집계",
        "",
        f"- 전체 케이스: {len(cases)}건 / 정답 항목: {gold_item_total}개 / 복수 프로젝트 보고: {multi_total}건",
        "- '복수 프로젝트를 하나로 병합'의 분모는 복수 프로젝트 보고 건수, 나머지는 전체 케이스 수",
        "",
        "| 모델 | " + " | ".join(label for _, label in COLS) + " | 출력 항목 수 |",
        "|" + "|".join(["---"] * (len(COLS) + 2)) + "|",
    ]
    for model, stats, items in rows:
        lines.append(
            f"| {model} | " + " | ".join(str(stats.get(k, 0)) for k, _ in COLS) + f" | {items} |"
        )

    out = BENCH / "results" / f"{args.prefix}failmodes.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("\n작성:", out)


if __name__ == "__main__":
    main()
