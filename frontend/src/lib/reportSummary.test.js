import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
    reportCountLabel,
    reportCounts,
    reportHeadline,
    reportSummary,
} from "./reportSummary.js";

const PARSED = {
    projects: [
        {
            projectName: "일일보고취합",
            completedTasks: ["구조화 프롬프트 정리", "  "],
            inProgressTasks: ["주간 병합 로직"],
            issues: [{ content: "검색이 안 나옴" }],
            requests: ["디자인 확인 부탁"],
            nextPlans: ["PPT 채우기"],
        },
        {
            projectName: "명함주소록",
            completedTasks: ["OCR 재시도"],
            inProgressTasks: [],
            issues: [],
            requests: [],
            nextPlans: [],
        },
    ],
};

describe("report summary", () => {
    it("counts items across projects and drops blanks", () => {
        assert.deepEqual(reportCounts(PARSED), {
            done: 2,
            progress: 1,
            issues: 1,
            requests: 1,
            plans: 1,
        });
    });

    it("accepts the stringified parsed_json the list API returns", () => {
        assert.deepEqual(reportCounts(JSON.stringify(PARSED)), reportCounts(PARSED));
        assert.deepEqual(reportCounts("not json"), {
            done: 0,
            progress: 0,
            issues: 0,
            requests: 0,
            plans: 0,
        });
    });

    it("leads the card line with the issue when there is one", () => {
        assert.equal(reportHeadline(PARSED), "검색이 안 나옴");
    });

    it("falls back to completed then in-progress work", () => {
        assert.equal(
            reportHeadline({
                projects: [{ completedTasks: ["배포"], inProgressTasks: ["회귀"] }],
            }),
            "배포",
        );
        assert.equal(
            reportHeadline({ projects: [{ inProgressTasks: ["회귀"] }] }),
            "회귀",
        );
        assert.equal(reportHeadline({ projects: [] }), "");
    });

    it("hides zero buckets in the count label", () => {
        assert.equal(reportCountLabel(PARSED), "완료 2 · 진행 1 · 이슈 1 · 요청 1");
        assert.equal(
            reportCountLabel({ projects: [{ completedTasks: ["배포"] }] }),
            "완료 1",
        );
        assert.equal(reportCountLabel({ projects: [] }), "");
    });

    it("bundles everything the card needs in one call", () => {
        const summary = reportSummary(PARSED);
        assert.equal(summary.headline, "검색이 안 나옴");
        assert.equal(summary.counts.issues, 1);
        assert.match(summary.countLabel, /이슈 1/);
    });
});
