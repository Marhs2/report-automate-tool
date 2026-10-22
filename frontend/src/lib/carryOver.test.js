import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { NO_PROJECT, addReportLine, carryItems, periodTotals } from "./carryOver.js";

describe("carryItems", () => {
    const focus = {
        date: "2026-10-21",
        items: [
            { project: "MES", nextPlans: ["스테이징 반영", "스테이징 반영"], issues: ["도면 미수령"] },
            { project: "", nextPlans: ["주간 회의 준비"], issues: [], requests: ["기준 회신"] },
        ],
    };

    it("lists last report's plans, issues and requests once each", () => {
        const items = carryItems(focus, "2026-10-22");
        assert.deepEqual(items.map((item) => [item.project, item.text, item.source]), [
            ["MES", "스테이징 반영", "plan"],
            ["MES", "도면 미수령", "issue"],
            ["", "주간 회의 준비", "plan"],
            ["", "기준 회신", "request"],
        ]);
    });

    it("is empty when the latest report is today's", () => {
        assert.deepEqual(carryItems({ ...focus, date: "2026-10-22" }, "2026-10-22"), []);
        assert.deepEqual(carryItems(null, "2026-10-22"), []);
    });
});

describe("addReportLine", () => {
    it("starts the line format from an empty box", () => {
        assert.equal(
            addReportLine("", { project: "MES", kind: "완료", text: "스테이징 반영" }),
            "프로젝트 명: MES\n\n[완료]\n- 스테이징 반영",
        );
    });

    it("joins an existing project block and ignores duplicates", () => {
        const first = addReportLine("", { project: "MES", kind: "완료", text: "A" });
        const second = addReportLine(first, { project: "MES", kind: "진행", text: "B" });
        assert.equal(second, "프로젝트 명: MES\n\n[완료]\n- A\n\n[진행]\n- B");
        assert.equal(addReportLine(second, { project: "MES", kind: "진행", text: "B" }), second);
    });

    it("keeps prose typed above and files no-project lines under one name", () => {
        const out = addReportLine("오늘 문의 2건 처리", { project: "", kind: "진행", text: "회의 준비" });
        assert.equal(out, `오늘 문의 2건 처리\n\n프로젝트 명: ${NO_PROJECT}\n\n[진행]\n- 회의 준비`);
    });
});

describe("periodTotals", () => {
    const json = (done, progress, issues) =>
        JSON.stringify({
            projects: [{ projectName: "P", completedTasks: done, inProgressTasks: progress, issues }],
        });
    it("counts only my reports inside the range", () => {
        const totals = periodTotals(
            [
                { member_id: 1, report_date: "2026-10-19", parsed_json: json(["a", "b"], ["c"], []) },
                { member_id: 1, report_date: "2026-10-20", parsed_json: json(["d"], [], ["e"]) },
                { member_id: 2, report_date: "2026-10-20", parsed_json: json(["x"], [], []) },
                { member_id: 1, report_date: "2026-10-26", parsed_json: json(["y"], [], []) },
            ],
            1,
            "2026-10-19",
            "2026-10-23",
        );
        assert.equal(totals.days, 2);
        assert.deepEqual([totals.done, totals.progress, totals.issues], [3, 1, 1]);
        assert.deepEqual(totals.byDay["2026-10-20"], { done: 1, progress: 0, issues: 1 });
    });
});
