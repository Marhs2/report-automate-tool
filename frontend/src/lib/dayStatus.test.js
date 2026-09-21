import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
    dayCounts,
    cellEventBars,
    isOffdayDate,
    memberInitials,
    missingOnDate,
    overflowTooltip,
} from "./dayStatus.js";

describe("memberInitials", () => {
    it("uses first and last characters so similar surnames stay distinct", () => {
        assert.equal(memberInitials("김재휘"), "김휘");
        assert.equal(memberInitials("김재현"), "김현");
        assert.equal(memberInitials("박"), "박");
        assert.equal(memberInitials(""), "?");
    });
});

describe("cellEventBars", () => {
    const people = (submittedCount, missedCount) => [
        ...Array.from({ length: submittedCount }, (_, index) => ({
            name: `제출${index}`,
            submitted: true,
        })),
        ...Array.from({ length: missedCount }, (_, index) => ({
            name: `미제출${index}`,
            submitted: false,
        })),
    ];

    it("only shows submitted people as events", () => {
        const bars = cellEventBars(people(2, 14));
        assert.equal(bars.shown.length, 2);
        assert.equal(bars.overflow, 0);
        assert.deepEqual(bars.hidden, []);
        assert.equal(
            bars.shown.every((entry) => entry.submitted),
            true,
        );
    });

    it("keeps three name bars and folds extra submitted into more", () => {
        const bars = cellEventBars(people(5, 11));
        assert.deepEqual(
            bars.shown.map((entry) => entry.name),
            ["제출0", "제출1", "제출2"],
        );
        assert.equal(bars.overflow, 2);
        assert.deepEqual(
            bars.hidden.map((entry) => entry.name),
            ["제출3", "제출4"],
        );
    });
});

describe("overflowTooltip", () => {
    it("joins a short leftover list", () => {
        assert.equal(
            overflowTooltip([{ name: "정동일" }, { name: "신찬혁" }]),
            "정동일 · 신찬혁",
        );
    });

    it("truncates a long leftover list", () => {
        const hidden = Array.from({ length: 8 }, (_, index) => ({
            name: `이름${index}`,
        }));
        assert.equal(
            overflowTooltip(hidden),
            "이름0 · 이름1 · 이름2 · 이름3 · 이름4 · 이름5 외 2명",
        );
    });
});

describe("dayCounts", () => {
    const entries = [
        { name: "정동일", submitted: true },
        { name: "신찬혁", submitted: true },
        { name: "김재휘", submitted: false },
    ];

    it("counts submitted and missed on a workday", () => {
        assert.deepEqual(dayCounts(entries, false), {
            submitted: 2,
            missed: 1,
        });
    });

    it("does not count misses on an offday", () => {
        assert.deepEqual(dayCounts(entries, true), {
            submitted: 2,
            missed: 0,
        });
    });
});

describe("missingOnDate", () => {
    it("hides missing names on weekends and holidays", () => {
        const names = ["정동일", "김재휘"];
        const holidays = { "2026-03-02": "삼일절 대체 휴일" };
        assert.deepEqual(missingOnDate("2026-03-02", names, holidays), []);
        assert.deepEqual(missingOnDate("2026-03-01", names, holidays), []);
        assert.deepEqual(missingOnDate("2026-03-03", names, holidays), names);
    });

    it("treats a named holiday map hit as an offday", () => {
        assert.equal(
            isOffdayDate("2026-05-01", { "2026-05-01": "노동절" }),
            true,
        );
        assert.equal(isOffdayDate("2026-05-04", {}), false);
    });
});
