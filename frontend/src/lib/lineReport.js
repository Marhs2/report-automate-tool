/** 모바일 한 줄 작성기. 제목은 추출기가 읽는 칸 이름이라 바꾸면 제출 결과가 달라진다. */

export const LINE_KINDS = ["완료", "진행", "이슈", "다음 계획", "일정"];

export const KIND_FIELDS = {
    "완료": { label: "끝낸 일", placeholder: "오늘 마무리한 일" },
    "진행": { label: "하고 있는 일", placeholder: "아직 끝나지 않은 일" },
    "이슈": { label: "막힌 점", placeholder: "무엇이 막혔는지" },
    "다음 계획": { label: "다음 계획", placeholder: "다음에 할 일" },
    "일정": { label: "일정 날짜", placeholder: "" },
};

const PROJECT_RE = /^프로젝트 명:\s*(.+)\s*$/;
const KIND_RE = /^\[(완료|진행|이슈|다음 계획|일정)\]\s*$/;
const ITEM_RE = /^-\s+(.+)$/;

export function formatScheduleDate(iso) {
    const parts = String(iso || "").split("-");
    if (parts.length !== 3 || !/^\d{4}$/.test(parts[0])) return "";
    const month = Number(parts[1]);
    const day = Number(parts[2]);
    if (!month || !day) return "";
    return `${parts[0]}.${month}.${day}`;
}

export function scheduleLine(iso, title) {
    const date = formatScheduleDate(iso);
    const name = String(title || "").trim();
    if (!date || !name) return "";
    return `${date} ${name}`;
}

export function serializeLineReport(lines) {
    const names = [];
    for (const line of lines || []) {
        const project = String(line?.project || "").trim();
        const text = String(line?.text || "").trim();
        if (!project || !text || !LINE_KINDS.includes(line?.kind)) continue;
        if (!names.includes(project)) names.push(project);
    }

    return names.map((name) => {
        const chunks = [`프로젝트 명: ${name}`];
        for (const kind of LINE_KINDS) {
            const rows = (lines || []).filter(
                (line) =>
                    String(line?.project || "").trim() === name &&
                    line?.kind === kind &&
                    String(line?.text || "").trim(),
            );
            if (!rows.length) continue;
            chunks.push("", `[${kind}]`);
            for (const row of rows) chunks.push(`- ${String(row.text).trim()}`);
        }
        return chunks.join("\n");
    }).join("\n\n");
}

/** 줄로 읽히는 부분만 남긴다. 앞에 붙어 있던 예전 글은 빼서 다시 합치지 않는다. */
export function onlyStructuredLineReport(raw) {
    return serializeLineReport(parseLineReport(raw).lines);
}

export function parseLineReport(raw) {
    const text = String(raw || "").replace(/\r\n/g, "\n");
    if (!text.trim()) return { lines: [], looseText: "" };

    const blocks = text.split(/\n(?=프로젝트 명:)/);
    const lines = [];
    const loose = [];

    for (const block of blocks) {
        const rows = block.split("\n");
        const head = rows[0].match(PROJECT_RE);
        if (!head) {
            if (block.trim()) loose.push(block.trim());
            continue;
        }

        const project = head[1].trim();
        let kind = "";
        let any = false;
        const leftover = [];
        for (const row of rows.slice(1)) {
            const kindMatch = row.match(KIND_RE);
            if (kindMatch) {
                kind = kindMatch[1];
                continue;
            }
            const item = row.match(ITEM_RE);
            if (item && kind) {
                lines.push({ project, kind, text: item[1].trim() });
                any = true;
                continue;
            }
            if (row.trim()) leftover.push(row);
        }
        if (!any) loose.push(block.trim());
        else if (leftover.length) loose.push(leftover.join("\n").trim());
    }

    return { lines, looseText: loose.join("\n\n").trim() };
}
