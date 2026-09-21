import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
    highlightedRawHtml,
    highlightRangesByProject,
    projectAccentIndex,
} from "./projectAccent.js";

describe("projectAccentIndex", () => {
    it("cycles through six accents", () => {
        assert.equal(projectAccentIndex(0), 0);
        assert.equal(projectAccentIndex(5), 5);
        assert.equal(projectAccentIndex(6), 0);
    });
});

describe("highlightRangesByProject", () => {
    const projects = [
        {
            projectName: "MES",
            completedTasks: ["설비 배치 개발 완료"],
            inProgressTasks: [],
            issues: [],
            requests: [],
            nextPlans: [],
        },
        {
            projectName: "여우비",
            completedTasks: [],
            inProgressTasks: [],
            issues: [],
            requests: [],
            nextPlans: ["포인트 적립 API 착수"],
        },
    ];
    const raw =
        "MES 설비 배치 개발 완료했고 여우비 포인트 적립 API 착수는 다음 주다.";

    it("tags each match with the project accent", () => {
        const ranges = highlightRangesByProject(raw, projects);
        const slices = ranges.map(([start, end, accent]) => [
            raw.slice(start, end),
            accent,
        ]);
        assert.deepEqual(slices, [
            ["MES", 0],
            ["설비 배치 개발 완료", 0],
            ["여우비", 1],
            ["포인트 적립 API 착수", 1],
        ]);
    });

    it("renders distinct data-accent marks", () => {
        const html = highlightedRawHtml(raw, projects);
        assert.match(html, /data-accent="0"[^>]*>MES/);
        assert.match(html, /data-accent="1"[^>]*>여우비/);
    });
});
