import { missingOnDate } from "./dayStatus.js";

export function sortByIssuesFirst(reports, issueCountOf) {
    return [...(reports || [])].sort((left, right) => {
        const gap = issueCountOf(right) - issueCountOf(left);
        if (gap) return gap;
        return String(left.member_name || "").localeCompare(
            String(right.member_name || ""),
            "ko",
        );
    });
}

export function missingBanner(groups) {
    const names = [];
    const seen = new Set();
    for (const group of groups || []) {
        for (const name of group.missing || []) {
            if (!name || seen.has(name)) continue;
            seen.add(name);
            names.push(name);
        }
    }
    return names;
}

export function weeklyRollup({ days = [], dayCounts = {}, submittedNames = [], blockerCount = 0 } = {}) {
    const reports = days.reduce(
        (sum, day) => sum + Number(dayCounts[day] || 0),
        0,
    );
    return {
        days: days.length,
        reports,
        contributors: submittedNames.length,
        blockers: Number(blockerCount) || 0,
    };
}

export function weeklyRollupLabel(rollup) {
    const item = rollup || weeklyRollup();
    return `${item.days}일 · ${item.reports}건 · ${item.contributors}명 · 이슈 ${item.blockers}`;
}

export function peakSubmissionDay(days = []) {
    const work = days.filter((day) => !day.isOffday);
    if (!work.length) return null;
    return work.reduce((best, day) =>
        day.submitted > best.submitted ? day : best,
    );
}

export function weekdaySubmitted(days = []) {
    const labels = ["일", "월", "화", "수", "목", "금", "토"];
    const buckets = labels.map((label) => ({ label, submitted: 0, total: 0 }));
    for (const day of days) {
        if (day.isOffday) continue;
        const index = Number(day.weekday);
        if (!Number.isInteger(index) || index < 0 || index > 6) continue;
        buckets[index].submitted += Number(day.submitted) || 0;
        buckets[index].total += 1;
    }
    return buckets.filter((bucket) => bucket.total > 0);
}

export function issueSnippets(report) {
    const who = report?.memberName || report?.member_name || "";
    const items = [];
    for (const project of report?.report?.projects || report?.projects || []) {
        for (const issue of project.issues || []) {
            const text =
                issue && typeof issue === "object"
                    ? String(issue.content || "").trim()
                    : String(issue || "").trim();
            if (!text) continue;
            items.push({
                who,
                project: project.projectName || "",
                text,
            });
        }
    }
    return items;
}

function parseJson(value) {
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

export function fromDailyReport(row) {
    const parsed = parseJson(row?.parsed_json ?? row?.report ?? row);
    const projects = parsed.projects || [];
    return {
        memberName: row?.member_name || row?.memberName || "",
        report: {
            done: projects.map((project) => ({
                title: project.projectName || "",
                items: project.completedTasks || [],
            })),
            next: projects.map((project) => ({
                title: project.projectName || "",
                items:
                    Array.isArray(project.nextWeekPlans) &&
                    project.nextWeekPlans.length
                        ? project.nextWeekPlans
                        : project.nextPlans || [],
            })),
            projects,
        },
    };
}

export function weeklyHighlights(reports, { winLimit = 6, nextLimit = 6 } = {}) {
    const wins = [];
    const next = [];
    const blockers = [];
    for (const report of reports || []) {
        const who = report.memberName || report.member_name || "";
        const deck = report.report || report;
        for (const section of deck.done || []) {
            for (const item of section.items || []) {
                const text = String(item || "").trim();
                if (text) wins.push({ who, project: section.title || "", text });
            }
        }
        for (const section of deck.next || []) {
            for (const item of section.items || []) {
                const text = String(item || "").trim();
                if (text) next.push({ who, project: section.title || "", text });
            }
        }
        blockers.push(...issueSnippets(report));
    }
    return {
        wins: wins.slice(0, winLimit),
        blockers,
        next: next.slice(0, nextLimit),
    };
}

export function peakDayLabel(peak) {
    if (!peak || !(Number(peak.submitted) > 0)) return "";
    const parts = String(peak.date || "").split("-");
    const month = Number(parts[1]);
    const day = Number(parts[2]);
    const labels = ["일", "월", "화", "수", "목", "금", "토"];
    const week = labels[Number(peak.weekday)] || "";
    const when = month && day ? `${week} ${month}.${day}` : week;
    return `제출 최다 · ${when} · ${peak.submitted}건`;
}

export function missingForDate(date, roster, submitted, holidayNames) {
    return missingOnDate(
        date,
        (roster || []).filter((name) => !submitted.has(name)),
        holidayNames || {},
    );
}
