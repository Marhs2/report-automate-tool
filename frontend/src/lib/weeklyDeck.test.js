import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
    deckExtrasCount,
    doneKindMap,
    groupDoneItems,
    humanizeConfirmText,
    nextWeekLabel,
    placeProjectSection,
    projectSectionOrder,
    toWeeklyDeck,
    visibleConfirmQuestions,
} from "./weeklyDeck.js";

describe("nextWeekLabel", () => {
    it("uses the Monday-Friday after a single selected day", () => {
        assert.equal(nextWeekLabel("9/18", "2026.09.18"), "9/21~9/25");
    });

    it("uses the week after a Mon-Fri span", () => {
        assert.equal(nextWeekLabel("9/14~9/18", "2026.09.18"), "9/21~9/25");
    });

    it("falls back to the report date when the done label is empty", () => {
        assert.equal(nextWeekLabel("", "2026-09-18"), "9/21~9/25");
    });

    it("crosses the year boundary", () => {
        assert.equal(nextWeekLabel("12/28~12/31", "2026.12.31"), "1/4~1/8");
    });
});

describe("confirm questions", () => {
    it("replaces schema field names with the labels on the form", () => {
        assert.equal(
            humanizeConfirmText(
                "다음 주 할 일이 있으면 nextWeekPlans에 추가해 주세요.",
            ),
            "다음 주 할 일이 있으면 향후일정에 추가해 주세요.",
        );
    });

    it("drops an empty-next question once that project has a next item", () => {
        const questions = visibleConfirmQuestions(
            [
                {
                    id: "empty-next",
                    text: "오늘 보고의 다음 주 계획이 비어 있습니다. 다음 일이 없는 게 맞나요?",
                    ifNo: "다음 주 할 일이 있으면 nextWeekPlans에 추가해 주세요.",
                },
            ],
            {
                next: [{ title: "오늘 보고", items: ["검수 메모"] }],
            },
        );
        assert.deepEqual(questions, []);
    });
});

describe("toWeeklyDeck", () => {
    it("overwrites a stale next-week label", () => {
        const deck = toWeeklyDeck({
            schema: "weekly-deck-v1",
            report_date: "2026.09.18",
            week_label_done: "9/14~9/18",
            week_label_next: "9/14~9/18",
            done: [{ title: "A", items: ["x"] }],
            next: [{ title: "A", items: ["y"] }],
        });
        assert.equal(deck.week_label_next, "9/21~9/25");
    });

    it("keeps notices events collab and director", () => {
        const deck = toWeeklyDeck({
            schema: "weekly-deck-v1",
            director: "김동심",
            done: [{ title: "A", items: ["x"] }],
            next: [{ title: "A", items: ["y"] }],
            notices: [{ title: "보안규정", body: ["문건 검토"] }],
            month_events: [{ when: "9/15", title: "월보고" }],
            next_month_events: [{ when: "10/1", title: "결산" }],
            collab: { supports: ["dc"], done: ["펌웨어 지원"], next: [] },
        });
        assert.equal(deck.director, "김동심");
        assert.equal(deck.notices[0].title, "보안규정");
        assert.equal(deck.month_events[0].title, "월보고");
        assert.deepEqual(deck.collab.supports, ["DC"]);
        assert.deepEqual(deck.collab.done, ["펌웨어 지원"]);
    });

    it("does not invent a blank project when the next list is empty", () => {
        const deck = toWeeklyDeck({
            schema: "weekly-deck-v1",
            done: [{ title: "HD 현대건설기계", items: ["점검"] }],
            next: [],
        });
        assert.deepEqual(
            projectSectionOrder(deck).map((block) => block.done?.title || block.next?.title),
            ["HD 현대건설기계"],
        );
    });

    it("drops a saved section that has neither a title nor text", () => {
        const deck = toWeeklyDeck({
            schema: "weekly-deck-v1",
            done: [
                { title: "내부 보고", items: ["정리"] },
                { title: "", items: [""] },
            ],
            next: [{ title: "", items: [] }],
        });
        assert.deepEqual(
            projectSectionOrder(deck).map((block) => block.done?.title || block.next?.title),
            ["내부 보고"],
        );
    });
});

/** 슬라이드에서는 "진행 현황" 한 칸이지만, 읽을 때는 끝난 것과 막힌 것이 구분돼야 한다. */
describe("splitting the merged 진행 현황 column", () => {
    const DECK = {
        schema: "weekly-deck-v1",
        done: [
            {
                title: "일일보고취합",
                items: [
                    "프롬프트 정리",
                    "주간 병합 로직",
                    "검색이 안 나옴",
                    "출처를 모르는 줄",
                ],
            },
        ],
        next: [{ title: "일일보고취합", items: ["PPT 채우기"] }],
        projects: [
            {
                projectName: "일일보고 취합",
                completedTasks: ["프롬프트 정리"],
                inProgressTasks: ["주간 병합 로직"],
                issues: ["검색이 안 나옴"],
            },
        ],
    };

    it("recovers each line's kind from the legacy projects, ignoring spacing", () => {
        const map = doneKindMap(DECK);
        assert.equal(map.get("일일보고취합\u0000프롬프트정리"), "done");
        assert.equal(map.get("일일보고취합\u0000주간병합로직"), "progress");
        assert.equal(map.get("일일보고취합\u0000검색이안나옴"), "issue");
    });

    it("groups a section into 완료 / 진행 / 이슈 and parks the rest in 기타", () => {
        const groups = groupDoneItems(DECK, DECK.done[0]);
        assert.deepEqual(
            groups.map((group) => [group.kind, group.items]),
            [
                ["done", ["프롬프트 정리"]],
                ["progress", ["주간 병합 로직"]],
                ["issue", ["검색이 안 나옴"]],
                ["other", ["출처를 모르는 줄"]],
            ],
        );
    });

    it("drops empty kinds instead of printing empty headings", () => {
        const groups = groupDoneItems(
            { projects: [{ projectName: "A", completedTasks: ["x"] }] },
            { title: "A", items: ["x"] },
        );
        assert.deepEqual(groups.map((group) => group.kind), ["done"]);
    });

    it("counts PPT-only slots so empty ones stay out of the reading view", () => {
        assert.equal(deckExtrasCount(DECK).total, 0);
        const filled = deckExtrasCount({
            notices: [{ title: "보안규정", body: ["검토"] }],
            month_events: [{ when: "9/15", title: "월보고" }],
            collab: { supports: ["DC"], done: ["펌웨어 지원"], next: [] },
        });
        assert.equal(filled.notices, 1);
        assert.equal(filled.events, 1);
        assert.equal(filled.collab, 2);
        assert.equal(filled.total, 4);
    });
});

describe("placeProjectSection", () => {
    const section = (title) => ({ title, items: ["내용"] });
    const titles = (data) =>
        projectSectionOrder(data).map(
            (block) => block.done?.title || block.next?.title || "",
        );

    it("inserts the new project after the one being edited", () => {
        const first = section("가");
        const middle = section("나");
        const last = section("다");
        const data = {
            done: [first, middle, last],
            next: [first, middle, last],
        };
        const added = section("");
        placeProjectSection(data, projectSectionOrder(data)[1], added);
        assert.deepEqual(titles(data), ["가", "나", "", "다"]);
    });

    it("keeps a next-only project after the inserted card", () => {
        const first = section("가");
        const tail = section("라");
        const data = { done: [first], next: [first, tail] };
        const added = section("");
        placeProjectSection(data, projectSectionOrder(data)[0], added);
        assert.deepEqual(titles(data), ["가", "", "라"]);
    });

    it("appends when nothing is selected and the list is empty", () => {
        const data = { done: [], next: [] };
        placeProjectSection(data, null, section("새"));
        assert.deepEqual(titles(data), ["새"]);
    });
});
