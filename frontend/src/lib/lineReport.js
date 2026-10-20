/** 모바일 한 줄 작성기. 제목은 추출기가 읽는 칸 이름이라 바꾸면 제출 결과가 달라진다. */

export const LINE_KINDS = ["완료", "진행", "이슈", "요청", "다음 계획"];

export const KIND_FIELDS = {
    "완료": { label: "끝낸 일", placeholder: "오늘 마무리한 일" },
    "진행": { label: "하고 있는 일", placeholder: "아직 끝나지 않은 일" },
    "이슈": { label: "막힌 점", placeholder: "무엇이 막혔는지" },
    "요청": { label: "요청", placeholder: "필요한 도움" },
    "다음 계획": { label: "다음 계획", placeholder: "다음에 할 일" },
};

const PROJECT_RE = /^프로젝트 명:\s*(.+)\s*$/;
const KIND_RE = /^\[(완료|진행|이슈|요청|다음 계획)\]\s*$/;
const ITEM_RE = /^-\s+(.+)$/;

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

const KIND_KEYS = {
    "완료": "completedTasks",
    "진행": "inProgressTasks",
    "이슈": "issues",
    "요청": "requests",
    "다음 계획": "nextPlans",
};

/** 한 줄씩 쓴 보고는 사람이 이미 나눴다. AI 추출 없이 일일보고 스키마(json_Schema.json) 모양으로 바로 옮긴다. */
export function linesToReportJson(lines) {
    const projects = [];
    for (const line of lines || []) {
        const name = String(line?.project || "").trim();
        const text = String(line?.text || "").trim();
        const key = KIND_KEYS[line?.kind];
        if (!name || !text || !key) continue;
        let project = projects.find((item) => item.projectName === name);
        if (!project) {
            project = {
                projectName: name,
                completedTasks: [],
                inProgressTasks: [],
                issues: [],
                requests: [],
                nextPlans: [],
            };
            projects.push(project);
        }
        if (!project[key].includes(text)) project[key].push(text);
    }
    return { projects };
}

/** 내가 최근에 보고한 프로젝트를 앞에 둔다. 나머지는 원래 순서를 지킨다. */
export function orderProjectsByRecent(names, reports, memberId) {
    const mine = (reports || [])
        .filter((report) => String(report?.member_id) === String(memberId))
        .sort((a, b) => String(b?.report_date || "").localeCompare(String(a?.report_date || "")));
    const recent = [];
    for (const report of mine) {
        let parsed = report?.parsed_json;
        if (typeof parsed === "string") {
            try {
                parsed = JSON.parse(parsed);
            } catch {
                parsed = null;
            }
        }
        for (const project of parsed?.projects || []) {
            const name = String(project?.projectName || "").trim();
            if (name && !recent.includes(name)) recent.push(name);
        }
    }
    const known = (names || []).map((name) => String(name || "").trim()).filter(Boolean);
    return [...recent, ...known.filter((name) => !recent.includes(name))];
}
