import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { reportLines, shiftWorkday, teamDay } from "./teamDay.js";

const parsed = (projects) => JSON.stringify({ projects });

describe("team day", () => {
    const users = [
        { id: 1, name: "관리자", team_id: 1, is_admin: true },
        { id: 2, name: "김서연", team_id: 2 },
        { id: 3, name: "박민준", team_id: 3 },
        { id: 4, name: "이하늘", team_id: 4 },
        { id: 5, name: "최도윤", team_id: 3 },
    ];
    const teams = [{ id: 2, team_name: "기획" }, { id: 3, team_name: "개발" }, { id: 4, team_name: "운영" }];
    const reports = [
        { id: 10, member_id: 5, report_date: "2026-10-22", parsed_json: parsed([{ projectName: "내부 보고 자동화", completedTasks: ["시나리오 초안"] }]) },
        { id: 11, member_id: 2, report_date: "2026-10-22", parsed_json: parsed([{ projectName: "대한전선 IoT", completedTasks: ["실측"], issues: [{ content: "도면 지연" }] }]) },
        { id: 12, member_id: 3, report_date: "2026-10-21", parsed_json: parsed([{ projectName: "MES", completedTasks: ["문의 처리"] }]) },
    ];

    it("leaves admins out and counts who submitted that day", () => {
        const day = teamDay({ reports, users, teams, date: "2026-10-22", today: "2026-10-22" });
        assert.equal(day.total, 4);
        assert.equal(day.submitted, 2);
        assert.deepEqual(day.notYet.map((person) => person.name), ["박민준", "이하늘"]);
    });

    it("puts people with issues first and people who have not written last", () => {
        const day = teamDay({ reports, users, teams, date: "2026-10-22", today: "2026-10-22" });
        assert.deepEqual(day.people.map((person) => person.name), ["김서연", "최도윤", "박민준", "이하늘"]);
        assert.equal(day.people[0].team, "기획");
        assert.equal(day.people[0].issueCount, 1);
    });

    it("calls a past day without a report missing and today's one waiting", () => {
        const past = teamDay({ reports, users, teams, date: "2026-10-21", today: "2026-10-22" });
        assert.equal(past.people.find((person) => person.name === "이하늘").status, "missing");
        const now = teamDay({ reports, users, teams, date: "2026-10-22", today: "2026-10-22" });
        assert.equal(now.people.find((person) => person.name === "이하늘").status, "waiting");
    });

    it("spreads report lines by project in display order", () => {
        const lines = reportLines(parsed([{ projectName: "MES", issues: ["막힘"], completedTasks: ["끝"], nextWeekPlans: ["다음 일"] }]));
        assert.deepEqual(lines.map((line) => line.kind), ["done", "issue", "next"]);
        assert.equal(lines[0].project, "MES");
    });

    it("skips weekends when moving a day", () => {
        assert.equal(shiftWorkday("2026-10-19", -1), "2026-10-16");
        assert.equal(shiftWorkday("2026-10-16", 1), "2026-10-19");
    });
});
