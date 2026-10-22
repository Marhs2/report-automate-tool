import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { focusColumnsOf } from "./focusColumns.js";

describe("focus columns", () => {
    it("spreads next plans, issues and requests into three columns", () => {
        const columns = focusColumnsOf({ items: [{ project: "MES", nextPlans: ["스테이징 확인"], issues: [], requests: ["로그 확인"] }] });
        assert.deepEqual(columns.map((column) => column.key), ["next", "issue", "request"]);
        assert.deepEqual(columns[0].items, [{ text: "스테이징 확인", project: "" }]);
        assert.equal(columns[1].items.length, 0);
    });

    it("names the project only when there are several", () => {
        const columns = focusColumnsOf({ items: [{ project: "MES", nextPlans: ["a"] }, { project: "RTLS", nextPlans: ["b"] }] });
        assert.deepEqual(columns[0].items.map((item) => item.project), ["MES", "RTLS"]);
    });

    it("returns empty columns without a focus", () => {
        assert.ok(focusColumnsOf(null).every((column) => column.items.length === 0));
    });
});
