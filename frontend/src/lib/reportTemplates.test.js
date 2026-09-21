import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
    PASTE_TEMPLATES,
    applyTemplate,
    hasTypedContent,
    templateById,
} from "./reportTemplates.js";

describe("paste templates", () => {
    it("ships the four-or-fewer field scaffolds and keeps requests separate", () => {
        const ids = PASTE_TEMPLATES.map((item) => item.id);
        assert.deepEqual(ids, [
            "basic",
            "scrum",
            "office",
            "vs-yesterday",
            "requests",
        ]);
        assert.equal(PASTE_TEMPLATES.some((item) => item.body.includes("09:00")), false);
        assert.match(templateById("requests").body, /지시\/확인 부탁/);
        assert.match(templateById("basic").body, /\[이슈\]/);
        assert.match(templateById("scrum").body, /막힌 것/);
    });

    it("fills an empty editor and appends when there is already text", () => {
        const scrum = templateById("scrum");
        assert.equal(applyTemplate("", scrum), scrum.body);
        assert.equal(
            applyTemplate("어제 배포 완료", scrum),
            `어제 배포 완료\n\n${scrum.body}`,
        );
    });

    it("can replace what is already typed instead of appending", () => {
        const scrum = templateById("scrum");
        assert.equal(applyTemplate("어제 배포 완료", scrum, "replace"), scrum.body);
        assert.equal(applyTemplate("", scrum, "replace"), scrum.body);
    });

    it("knows whether the editor already holds something", () => {
        assert.equal(hasTypedContent(""), false);
        assert.equal(hasTypedContent("   \n "), false);
        assert.equal(hasTypedContent("배포 완료"), true);
    });
});
