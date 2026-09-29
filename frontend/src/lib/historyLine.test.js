import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { splitHistoryLine } from "./historyLine.js";

describe("splitHistoryLine", () => {
    it("splits a known category prefix into a tag", () => {
        assert.deepEqual(splitHistoryLine("완료: 요약 기능 개발"), {
            tag: "완료",
            tone: "success",
            text: "요약 기능 개발",
        });
        assert.equal(splitHistoryLine("후속: 양식 요청 (정동일)").tone, "warning");
    });

    it("leaves unknown prefixes and plain text alone", () => {
        assert.deepEqual(splitHistoryLine("URL: http://x"), { tag: "", tone: "", text: "URL: http://x" });
        assert.equal(splitHistoryLine("본문만 있는 줄").tag, "");
        assert.equal(splitHistoryLine(null).text, "");
    });
});
