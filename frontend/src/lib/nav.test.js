import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
    CAPABILITIES,
    COMPOSE_CHOICES,
    HOME_PATH,
    LIVE_ROUTE_PATHS,
    MOBILE_TABS,
    MORE_LINKS,
    PRIMARY_NAV,
    capabilityPaths,
    primaryNavCount,
} from "./nav.js";

describe("primary navigation", () => {
    it("starts with the dashboard, then the day's tabs", () => {
        assert.equal(primaryNavCount(), 4);
        assert.equal(PRIMARY_NAV.length, primaryNavCount());
        assert.deepEqual(PRIMARY_NAV.map((item) => item.label), ["현황", "오늘", "팀", "주간"]);
        assert.equal(PRIMARY_NAV[0].to, HOME_PATH);
        assert.equal(HOME_PATH, CAPABILITIES.dashboard);
        assert.equal(PRIMARY_NAV.find((item) => item.label === "오늘")?.to, "/");
        assert.deepEqual(MOBILE_TABS.map((tab) => tab.id), ["home", "today", "team", "weekly"]);
    });

    it("keeps the mobile tab bar at five tabs that all lead somewhere live", () => {
        assert.ok(MOBILE_TABS.length <= 5);
        const livePath = (to) => LIVE_ROUTE_PATHS.includes(String(to).split("?")[0]);
        for (const tab of MOBILE_TABS) {
            assert.ok(livePath(tab.to), `${tab.label} path ${tab.to} is not a live route`);
        }
        for (const item of [...COMPOSE_CHOICES, ...MORE_LINKS]) {
            assert.ok(livePath(item.to), `${item.label} path ${item.to} is not a live route`);
        }
        assert.deepEqual(COMPOSE_CHOICES.map((item) => item.id), ["daily", "meeting", "sales"]);
        assert.equal(COMPOSE_CHOICES.find((item) => item.id === "daily").label, "일일보고");
        assert.equal(CAPABILITIES.writeReport, "/report");
    });

    it("maps every required capability to a live route path", () => {
        const required = {
            today: "오늘 (일일보고 작성)",
            dashboard: "내 현황",
            team: "팀",
            dailyList: "일일보고 목록",
            writeReport: "보고서 작성",
            weekly: "주간 보고서",
            activities: "사용자 활동",
            projectTimeline: "프로젝트 흐름",
            projectNames: "프로젝트명 관리",
            usersAndTeams: "내 부서",
            admin: "관리",
        };
        for (const [key, label] of Object.entries(required)) {
            const path = CAPABILITIES[key];
            assert.ok(path, `${label} is missing from CAPABILITIES`);
            assert.ok(
                LIVE_ROUTE_PATHS.includes(path),
                `${label} path ${path} is not a live route`,
            );
        }
        assert.deepEqual(capabilityPaths(), Object.values(CAPABILITIES));
    });
});
