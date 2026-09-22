import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
    peakDayLabel,
    peakSubmissionDay,
    sortByIssuesFirst,
} from "./standupInsights.js";

describe("home list ranking", () => {
    it("puts people with issues above people without", () => {
        const rows = [
            { member_name: "박", issues: 0 },
            { member_name: "김", issues: 2 },
            { member_name: "이", issues: 0 },
        ];
        const sorted = sortByIssuesFirst(rows, (row) => row.issues);
        assert.deepEqual(
            sorted.map((row) => row.member_name),
            ["김", "박", "이"],
        );
    });
});

describe("activity peak day", () => {
    it("picks the workday with the most submissions", () => {
        const peak = peakSubmissionDay([
            { date: "2026-09-13", weekday: 0, submitted: 9, isOffday: true },
            { date: "2026-09-14", weekday: 1, submitted: 4, isOffday: false },
            { date: "2026-09-15", weekday: 2, submitted: 7, isOffday: false },
            { date: "2026-09-16", weekday: 3, submitted: 2, isOffday: false },
        ]);
        assert.equal(peak.date, "2026-09-15");
        assert.equal(peak.submitted, 7);
    });

    it("formats the peak day for the calendar toolbar", () => {
        assert.equal(
            peakDayLabel({ date: "2026-09-15", weekday: 2, submitted: 7 }),
            "제출 최다 · 화 9.15 · 7건",
        );
        assert.equal(
            peakDayLabel({ date: "2026-09-15", weekday: 2, submitted: 0 }),
            "",
        );
    });
});
