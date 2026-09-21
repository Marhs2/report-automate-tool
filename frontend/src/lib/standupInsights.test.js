import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
    fromDailyReport,
    missingBanner,
    peakDayLabel,
    peakSubmissionDay,
    sortByIssuesFirst,
    weekdaySubmitted,
    weeklyHighlights,
    weeklyRollup,
    weeklyRollupLabel,
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

    it("collects unique missing names for a Dailybot-style banner", () => {
        assert.deepEqual(
            missingBanner([
                { missing: ["정동일", "김재휘"] },
                { missing: ["김재휘", "신찬혁"] },
            ]),
            ["정동일", "김재휘", "신찬혁"],
        );
    });
});

describe("weekly rollup", () => {
    it("counts days, reports, contributors, and blockers", () => {
        const rollup = weeklyRollup({
            days: ["2026-09-14", "2026-09-15", "2026-09-16"],
            dayCounts: { "2026-09-14": 2, "2026-09-15": 1 },
            submittedNames: ["정동일", "김재휘"],
            blockerCount: 3,
        });
        assert.deepEqual(rollup, {
            days: 3,
            reports: 3,
            contributors: 2,
            blockers: 3,
        });
        assert.equal(weeklyRollupLabel(rollup), "3일 · 3건 · 2명 · 이슈 3");
    });
});

describe("weekly highlights", () => {
    it("splits wins, blockers, and next from a generated weekly", () => {
        const highlights = weeklyHighlights([
            {
                memberName: "정동일",
                report: {
                    done: [{ title: "MES", items: ["배치 완료"] }],
                    next: [{ title: "MES", items: ["포인트 API"] }],
                    projects: [
                        {
                            projectName: "MES",
                            issues: ["앱스토어 미승인"],
                        },
                    ],
                },
            },
        ]);
        assert.equal(highlights.wins[0].text, "배치 완료");
        assert.equal(highlights.next[0].text, "포인트 API");
        assert.equal(highlights.blockers[0].text, "앱스토어 미승인");
    });

    it("maps daily parsed_json into highlight shape without folding issues into wins", () => {
        const row = fromDailyReport({
            member_name: "김",
            parsed_json: {
                projects: [
                    {
                        projectName: "A",
                        completedTasks: ["배포"],
                        inProgressTasks: ["점검 중"],
                        nextPlans: ["점검"],
                        issues: ["지연"],
                    },
                ],
            },
        });
        const highlights = weeklyHighlights([row]);
        assert.equal(highlights.wins[0].text, "배포");
        assert.equal(highlights.next[0].text, "점검");
        assert.equal(highlights.blockers[0].text, "지연");
        assert.equal(
            highlights.wins.some((item) => item.text === "지연"),
            false,
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

    it("sums submitted counts per weekday", () => {
        const rows = weekdaySubmitted([
            { weekday: 1, submitted: 4, isOffday: false },
            { weekday: 1, submitted: 1, isOffday: false },
            { weekday: 5, submitted: 8, isOffday: false },
            { weekday: 0, submitted: 3, isOffday: true },
        ]);
        assert.deepEqual(rows, [
            { label: "월", submitted: 5, total: 2 },
            { label: "금", submitted: 8, total: 1 },
        ]);
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
