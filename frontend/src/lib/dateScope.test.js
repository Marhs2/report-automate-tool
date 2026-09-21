import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
    isFutureDate,
    isPastOrToday,
    mondayOf,
    shortDate,
    todayString,
    weekKeyOf,
    weekKeyOfDates,
    weekRange,
    weekRangeLabel,
    weekdayLabelOf,
    workWeekRange,
} from "./dateScope.js";

const MONDAY = new Date(2026, 8, 21); // 2026-09-21 (월)

describe("date scope", () => {
    it("reads today from the clock, not from the newest row", () => {
        assert.equal(todayString(MONDAY), "2026-09-21");
    });

    it("treats the rest of this week as future on a Monday", () => {
        assert.equal(isFutureDate("2026-09-21", MONDAY), false);
        assert.equal(isFutureDate("2026-09-22", MONDAY), true);
        assert.equal(isFutureDate("2026-09-25", MONDAY), true);
        assert.equal(isFutureDate("2026-09-18", MONDAY), false);
        assert.equal(isPastOrToday("2026-09-18", MONDAY), true);
        assert.equal(isPastOrToday("2026-09-22", MONDAY), false);
    });

    it("anchors a week on Monday, including Sundays", () => {
        assert.equal(mondayOf("2026-09-21"), "2026-09-21");
        assert.equal(mondayOf("2026-09-25"), "2026-09-21");
        assert.equal(mondayOf("2026-09-27"), "2026-09-21"); // 일요일
        assert.equal(mondayOf("2026-09-28"), "2026-09-28");
    });

    it("gives Mon..Sun for list filters and Mon..Fri for weekly reports", () => {
        assert.deepEqual(weekRange(MONDAY), {
            start: "2026-09-21",
            end: "2026-09-27",
        });
        assert.deepEqual(workWeekRange("2026-09-24"), {
            start: "2026-09-21",
            end: "2026-09-25",
        });
    });

    it("folds different date picks in one week onto one key", () => {
        assert.equal(weekKeyOf("2026-09-23"), "2026-09-21");
        assert.equal(
            weekKeyOfDates(["2026-09-21", "2026-09-22", "2026-09-23"]),
            weekKeyOfDates([
                "2026-09-21",
                "2026-09-22",
                "2026-09-23",
                "2026-09-24",
                "2026-09-25",
            ]),
        );
        assert.notEqual(
            weekKeyOfDates(["2026-09-18"]),
            weekKeyOfDates(["2026-09-21"]),
        );
        assert.equal(weekKeyOfDates([]), "");
    });

    it("labels weeks and weekdays for headers", () => {
        assert.equal(weekRangeLabel("2026-09-23"), "9.21 ~ 9.25");
        assert.equal(shortDate("2026-09-01"), "9.1");
        assert.equal(weekdayLabelOf("2026-09-21"), "월");
        assert.equal(weekdayLabelOf("2026-09-26"), "토");
        assert.equal(weekdayLabelOf("nope"), "");
    });
});
