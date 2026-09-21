import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
    CAPABILITIES,
    LIVE_ROUTE_PATHS,
    PRIMARY_NAV,
    capabilityPaths,
    primaryNavCount,
} from "./nav.js";

describe("primary navigation", () => {
    it("keeps the sidebar shorter than eight destinations", () => {
        assert.ok(primaryNavCount() < 8);
        assert.equal(PRIMARY_NAV.length, primaryNavCount());
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
