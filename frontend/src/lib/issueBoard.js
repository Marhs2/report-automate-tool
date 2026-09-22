const STOP = new Set([
    "진행",
    "중",
    "완료",
    "예정",
    "착수",
    "시작",
    "내일",
    "하겠습니다",
    "반영",
    "수정",
    "추가",
    "확인",
    "작성",
    "통과",
]);

const PARTICLES = ["으로", "에서", "에게", "에는", "은", "는", "을", "를", "이", "가", "와", "과", "에"];

export const itemText = (value) =>
    value && typeof value === "object"
        ? String(value.content ?? "").trim()
        : String(value ?? "").trim();

export const textsOf = (list) =>
    (Array.isArray(list) ? list : []).map(itemText).filter(Boolean);

const tokensOf = (value) => {
    const text = itemText(value)
        .toLowerCase()
        .replace(/[^0-9a-z가-힣]+/g, " ");
    const tokens = new Set();
    for (let token of text.split(/\s+/)) {
        if (!token || STOP.has(token)) continue;
        for (const particle of PARTICLES) {
            if (token.length > particle.length + 1 && token.endsWith(particle)) {
                token = token.slice(0, -particle.length);
                break;
            }
        }
        if (token.length >= 2 && !STOP.has(token)) tokens.add(token);
    }
    return tokens;
};

/** 완료 문장과 이슈 문장이 달라도, 같은 대상을 가리키면 같은 일이다. */
export const sameWork = (left, right) => {
    const leftTokens = tokensOf(left);
    const rightTokens = tokensOf(right);
    const common = [...leftTokens].filter((token) => rightTokens.has(token));
    if (!common.length) return false;
    const extraLeft = [...leftTokens].filter(
        (token) => !rightTokens.has(token) && token.length >= 4,
    );
    const extraRight = [...rightTokens].filter(
        (token) => !leftTokens.has(token) && token.length >= 4,
    );
    if (extraLeft.length && extraRight.length) return false;
    if (common.length >= 2) return true;
    return common.some((token) => token.length >= 4);
};

export const looksLikeIssue = (value) =>
    /검색|안\s*나|나오지|오류|버그|깨지|느려|실패|장애/.test(itemText(value));

const issueTexts = (entry) => [
    ...textsOf(entry.issues),
    ...textsOf(entry.inProgressTasks).filter(looksLikeIssue),
];

/**
 * 완료가 그 이슈의 마지막 언급과 같은 날이거나 그 이후면 해결이다.
 * 해결 뒤에 다시 적히면 열린 일로 되돌린다.
 */
export function buildIssueBoard(entries) {
    const byMember = new Map();
    const latestByMember = new Map();
    const chronological = [...(entries || [])].sort((a, b) => {
        const dateCmp = String(a.date).localeCompare(String(b.date));
        if (dateCmp) return dateCmp;
        return String(a.member_id).localeCompare(String(b.member_id));
    });

    for (const entry of chronological) {
        const memberKey = String(entry.member_id);
        latestByMember.set(memberKey, entry);
        if (!byMember.has(memberKey)) byMember.set(memberKey, []);
        const threads = byMember.get(memberKey);

        const touch = (text, fromIssue) => {
            const existing = threads.find((item) => sameWork(item.text, text));
            if (existing) {
                if (fromIssue) existing.text = text;
                existing.fromIssue = existing.fromIssue || fromIssue;
                existing.lastDate = entry.date;
                existing.report_id = entry.report_id;
                return;
            }
            threads.push({
                text,
                fromIssue,
                firstDate: entry.date,
                lastDate: entry.date,
                report_id: entry.report_id,
                member_id: entry.member_id,
                member_name: entry.member_name,
            });
        };

        for (const text of textsOf(entry.issues)) touch(text, true);
        for (const text of textsOf(entry.inProgressTasks).filter(looksLikeIssue)) {
            touch(text, false);
        }

        for (const done of textsOf(entry.completedTasks)) {
            for (const item of threads) {
                if (!sameWork(item.text, done)) continue;
                if (String(entry.date) < String(item.firstDate)) continue;
                item.resolvedDate = entry.date;
                item.resolvedReportId = entry.report_id;
            }
        }
    }

    const open = [];
    const unmentioned = [];
    const resolved = [];

    for (const [memberKey, threads] of byMember) {
        const latest = latestByMember.get(memberKey);
        const latestOpen = latest ? issueTexts(latest) : [];
        for (const item of threads) {
            const closed =
                item.resolvedDate &&
                String(item.resolvedDate) >= String(item.lastDate);
            const stillOpen = latestOpen.some((text) => sameWork(item.text, text));
            let status = "unmentioned";
            if (closed) status = "resolved";
            else if (stillOpen) status = "open";
            const row = { ...item, status };
            if (status === "open") open.push(row);
            else if (status === "resolved") resolved.push(row);
            else unmentioned.push(row);
        }
    }

    const byFirst = (a, b) => String(a.firstDate).localeCompare(String(b.firstDate));
    open.sort(byFirst);
    unmentioned.sort(byFirst);
    resolved.sort(byFirst);
    return { open, unmentioned, resolved };
}
