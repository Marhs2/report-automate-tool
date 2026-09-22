import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildIssueBoard, sameWork } from "./issueBoard.js";

describe("sameWork", () => {
    it("matches a completion that names the same subject in different words", () => {
        assert.equal(
            sameWork(
                "특정 거래처 코드에 공백이 들어가면 결과가 비움",
                "거래처 코드 공백 트림 반영",
            ),
            true,
        );
    });

    it("does not match unrelated tasks", () => {
        assert.equal(
            sameWork(
                "현장 도면이 2019년 버전이어서 센서 좌표가 어긋남",
                "메뉴 구성안 내부 리뷰 반영",
            ),
            false,
        );
    });
});

describe("buildIssueBoard", () => {
    it("marks an issue resolved when a later report completes the same work", () => {
        const board = buildIssueBoard([
            {
                date: "2026-09-15",
                member_id: 3,
                member_name: "박",
                report_id: 1,
                issues: ["특정 거래처 코드에 공백이 들어가면 결과가 비움"],
                completedTasks: ["검색 쿼리 인덱스 추가"],
                inProgressTasks: [],
            },
            {
                date: "2026-09-16",
                member_id: 3,
                member_name: "박",
                report_id: 2,
                issues: [],
                completedTasks: ["거래처 코드 공백 트림 반영"],
                inProgressTasks: [],
            },
        ]);
        assert.equal(board.open.length, 0);
        assert.equal(board.unmentioned.length, 0);
        assert.equal(board.resolved.length, 1);
        assert.equal(board.resolved[0].resolvedDate, "2026-09-16");
    });

    it("resolves an issue completed in the same report", () => {
        const board = buildIssueBoard([
            {
                date: "2026-09-16",
                member_id: 2,
                report_id: 4,
                issues: ["센서 좌표가 어긋남"],
                completedTasks: ["센서 좌표 18곳 수정"],
                inProgressTasks: [],
            },
        ]);
        assert.equal(board.resolved.length, 1);
        assert.equal(board.open.length, 0);
    });

    it("reopens an issue that is written again after it was completed", () => {
        const board = buildIssueBoard([
            {
                date: "2026-09-15",
                member_id: 3,
                report_id: 1,
                issues: ["거래처 코드 공백 때문에 결과가 비움"],
                completedTasks: [],
                inProgressTasks: [],
            },
            {
                date: "2026-09-16",
                member_id: 3,
                report_id: 2,
                issues: [],
                completedTasks: ["거래처 코드 공백 트림 반영"],
                inProgressTasks: [],
            },
            {
                date: "2026-09-17",
                member_id: 3,
                report_id: 3,
                issues: ["거래처 코드 공백이 다시 결과에 남음"],
                completedTasks: [],
                inProgressTasks: [],
            },
        ]);
        assert.equal(board.resolved.length, 0);
        assert.equal(board.open.length, 1);
    });
});
