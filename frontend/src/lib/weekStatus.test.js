import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { daySubmission, savedDatesOf, todayState, weekDays, weekStatus } from "./weekStatus.js";

describe("weekDays", () => {
    it("returns Monday to Friday of the given day's week", () => {
        const days = weekDays("2026-07-17");
        assert.deepEqual(
            days.map((day) => day.date),
            ["2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17"],
        );
        assert.deepEqual(days.map((day) => day.weekday), ["월", "화", "수", "목", "금"]);
    });

    it("uses the same week on a Sunday", () => {
        assert.equal(weekDays("2026-07-19")[0].date, "2026-07-13");
    });

    it("crosses month boundaries", () => {
        assert.deepEqual(
            weekDays("2026-07-01").map((day) => day.date),
            ["2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02", "2026-07-03"],
        );
    });
});

describe("weekStatus", () => {
    const rows = [
        { member_id: 7, activities: [
            { report_date: "2026-07-13", count: 1 },
            { report_date: "2026-07-14", count: 0 },
            { report_date: "2026-07-15", count: 2 },
        ] },
        { member_id: 8, activities: [{ report_date: "2026-07-14", count: 1 }] },
    ];

    it("reads only the given member's saved dates", () => {
        assert.deepEqual([...savedDatesOf(rows, "7")], ["2026-07-13", "2026-07-15"]);
        assert.equal(savedDatesOf(rows, 99).size, 0);
    });

    it("labels saved, missing, today and upcoming days", () => {
        const states = weekStatus(weekDays("2026-07-16"), savedDatesOf(rows, 7), "2026-07-16")
            .map((day) => day.state);
        assert.deepEqual(states, ["saved", "missing", "saved", "today", "upcoming"]);
    });
});

describe("todayState", () => {
    it("prefers saved over draft", () => {
        assert.equal(todayState({ saved: true, hasDraft: true }), "saved");
        assert.equal(todayState({ hasDraft: true }), "draft");
        assert.equal(todayState({}), "missing");
    });

    it("does not nag on weekends", () => {
        assert.equal(todayState({ weekend: true }), null);
        assert.equal(todayState({ weekend: true, saved: true }), "saved");
    });
});

describe("daySubmission", () => {
    const members = [
        { id: 1, name: "관리자", team_id: 1, is_admin: true },
        { id: 5, name: "무소속", team_id: null },
        { id: 2, name: "이하늘", team_id: 4 },
        { id: 3, name: "김서연", team_id: 1 },
        { id: 4, name: "박민준", team_id: 2 },
    ];
    const reports = [
        { member_id: 3, report_date: "2026-07-17" },
        { member_id: 2, report_date: "2026-07-16" },
    ];

    it("counts only non-admin people with a team and names who is missing", () => {
        assert.deepEqual(daySubmission(members, reports, "2026-07-17"), {
            total: 3,
            saved: 1,
            missing: ["박민준", "이하늘"],
        });
    });
});
