/** 목록 카드용 한 줄 요약과 건수. 이름과 칩만으로는 스캔이 안 된다. */

function itemText(value) {
    if (value && typeof value === "object") {
        return String(value.content ?? "").trim();
    }
    return String(value ?? "").trim();
}

function texts(list) {
    return (Array.isArray(list) ? list : []).map(itemText).filter(Boolean);
}

export function parseReportJson(value) {
    if (!value) return {};
    if (typeof value === "string") {
        try {
            return JSON.parse(value) || {};
        } catch {
            return {};
        }
    }
    return typeof value === "object" ? value : {};
}

export function reportCounts(parsedJson) {
    const parsed = parseReportJson(parsedJson);
    const counts = { done: 0, progress: 0, issues: 0, requests: 0, plans: 0 };
    for (const project of parsed.projects || []) {
        if (!project || typeof project !== "object") continue;
        counts.done += texts(project.completedTasks).length;
        counts.progress += texts(project.inProgressTasks).length;
        counts.issues += texts(project.issues).length;
        counts.requests += texts(project.requests).length;
        counts.plans += texts(
            project.nextWeekPlans?.length
                ? project.nextWeekPlans
                : project.nextPlans,
        ).length;
    }
    return counts;
}

/** 카드 한 줄에 쓸 문장. 이슈가 있으면 이슈를 먼저 보여준다. */
export function reportHeadline(parsedJson) {
    const parsed = parseReportJson(parsedJson);
    const buckets = [[], [], []];
    for (const project of parsed.projects || []) {
        if (!project || typeof project !== "object") continue;
        buckets[0].push(...texts(project.issues));
        buckets[1].push(...texts(project.completedTasks));
        buckets[2].push(...texts(project.inProgressTasks));
    }
    for (const bucket of buckets) {
        if (bucket.length) return bucket[0];
    }
    return "";
}

/** "완료 3 · 진행 2 · 이슈 1" 형태. 0인 항목은 빼서 눈에 걸리지 않게 한다. */
export function reportCountLabel(parsedJson) {
    const counts = reportCounts(parsedJson);
    const parts = [];
    if (counts.done) parts.push(`완료 ${counts.done}`);
    if (counts.progress) parts.push(`진행 ${counts.progress}`);
    if (counts.issues) parts.push(`이슈 ${counts.issues}`);
    if (counts.requests) parts.push(`요청 ${counts.requests}`);
    return parts.join(" · ");
}

export function reportSummary(parsedJson) {
    return {
        counts: reportCounts(parsedJson),
        headline: reportHeadline(parsedJson),
        countLabel: reportCountLabel(parsedJson),
    };
}
