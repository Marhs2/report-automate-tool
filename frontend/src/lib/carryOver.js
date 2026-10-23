import { parseLineReport, serializeLineReport } from "./lineReport.js";
import { reportCounts } from "./reportSummary.js";

/** 프로젝트 없이 쓴 계획은 이 이름 아래로 넣는다. */
export const NO_PROJECT = "기타 업무";

/**
 * 지난 보고의 다음 계획 · 이슈 · 요청을 오늘 쓸 거리로 편다. 오늘 쓴 보고면 비운다.
 * 같은 프로젝트 · 같은 글은 한 번만.
 */
export function carryItems(focus, today) {
    if (!focus || !focus.date || focus.date >= today) return [];
    const seen = new Set();
    const items = [];
    for (const entry of focus.items || []) {
        const project = String(entry?.project || "").trim();
        for (const [source, list] of [["plan", entry?.nextPlans], ["issue", entry?.issues], ["request", entry?.requests]]) {
            for (const raw of list || []) {
                const text = String(raw || "").trim();
                const key = `${project}\u0000${text}`;
                if (!text || seen.has(key)) continue;
                seen.add(key);
                items.push({ key, project, text, source });
            }
        }
    }
    return items;
}

/**
 * 쓰는 칸에 한 줄을 더한다. 한 줄 작성기와 같은 형식(프로젝트 명 · [종류] · - 내용)으로 넣어
 * 텍스트로 쓰든 한 줄씩 쓰든 같은 자리에 들어간다. 줄글로 쓴 부분은 앞에 그대로 둔다.
 */
export function addReportLine(raw, { project, kind, text }) {
    const line = { project: String(project || "").trim() || NO_PROJECT, kind, text: String(text || "").trim() };
    if (!line.text) return String(raw || "");
    const { lines, looseText } = parseLineReport(raw);
    if (lines.some((row) => row.project === line.project && row.kind === line.kind && row.text === line.text)) {
        return String(raw || "");
    }
    const body = serializeLineReport([...lines, line]);
    return looseText ? `${looseText}\n\n${body}` : body;
}

/** 이 기간에 내가 낸 일일보고를 모아 센다. 주간 화면 머리의 "이번 주 한 일". */
/** memberId는 한 사람 또는 여러 사람(부서 주간보고)의 id 배열. */
export function periodTotals(reports, memberId, start, end) {
    const ids = new Set([].concat(memberId).map(String));
    const totals = { days: 0, done: 0, progress: 0, issues: 0, byDay: {} };
    for (const row of reports || []) {
        if (!ids.has(String(row?.member_id))) continue;
        const day = String(row?.report_date || "");
        if (!day || day < start || day > end) continue;
        const counts = reportCounts(row.parsed_json);
        const slot = totals.byDay[day] || (totals.byDay[day] = { done: 0, progress: 0, issues: 0 });
        slot.done += counts.done;
        slot.progress += counts.progress;
        slot.issues += counts.issues;
        totals.done += counts.done;
        totals.progress += counts.progress;
        totals.issues += counts.issues;
    }
    totals.days = Object.keys(totals.byDay).length;
    return totals;
}
