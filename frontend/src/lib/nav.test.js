import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
    CAPABILITIES,
    COMPOSE_CHOICES,
    LIVE_ROUTE_PATHS,
    MOBILE_TABS,
    MORE_LINKS,
    PRIMARY_NAV,
    capabilityPaths,
    primaryNavCount,
} from "./nav.js";

describe("primary navigation", () => {
    it("keeps the sidebar shorter than eight destinations", () => {
        assert.ok(primaryNavCount() < 8);
        assert.equal(PRIMARY_NAV.length, primaryNavCount());
        assert.equal(
            PRIMARY_NAV.find((item) => item.label === "작성")?.to,
            "/compose",
        );
    });

    it("keeps the mobile tab bar at five tabs that all lead somewhere live", () => {
        assert.ok(MOBILE_TABS.length <= 5);
        const livePath = (to) => LIVE_ROUTE_PATHS.includes(String(to).split("?")[0]);
        for (const tab of MOBILE_TABS) {
            assert.ok(tab.to ? livePath(tab.to) : tab.sheet === "more");
        }
        for (const item of [...COMPOSE_CHOICES, ...MORE_LINKS]) {
            assert.ok(livePath(item.to), `${item.label} path ${item.to} is not a live route`);
        }
        assert.equal(COMPOSE_CHOICES[0].to, "/compose?kind=daily");
        assert.equal(CAPABILITIES.writeReport, "/report");
    });

    it("maps every required capability to a live route path", () => {
        const required = {
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
