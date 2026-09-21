export const WEEKLY_DECK_SCHEMA = "weekly-deck-v1";

const texts = (values) => {
    const out = [];
    const seen = new Set();
    for (const raw of values || []) {
        const text =
            raw && typeof raw === "object"
                ? String(raw.content || "").trim()
                : String(raw || "").trim();
        if (!text || seen.has(text)) continue;
        seen.add(text);
        out.push(text);
    }
    return out;
};

export const emptySection = () => ({ title: "", items: [""] });
export const emptyEvent = () => ({ when: "", title: "" });
export const emptyNotice = () => ({ title: "", body: [""] });
export const COLLAB_CENTERS = ["AC", "BC", "DC", "TC", "CSC"];
export const emptyCollab = () => ({ supports: [], done: [""], next: [""] });

const asNotices = (raw) => {
    const out = [];
    for (const item of raw || []) {
        if (!item || typeof item !== "object") continue;
        const title = String(item.title || "").trim();
        const body = (item.body || [])
            .map((line) => String(line || "").trim())
            .filter(Boolean);
        if (title || body.length) out.push({ title, body: body.length ? body : [""] });
    }
    return out;
};

const asEvents = (raw) => {
    const out = [];
    for (const item of raw || []) {
        if (!item || typeof item !== "object") continue;
        const when = String(item.when || "").trim();
        const title = String(item.title || "").trim();
        if (when || title) out.push({ when, title });
    }
    return out;
};

const asCollab = (raw) => {
    const data = raw && typeof raw === "object" ? raw : {};
    const seen = new Set();
    const supports = [];
    for (const item of data.supports || []) {
        const code = String(item || "").trim().toUpperCase();
        if (COLLAB_CENTERS.includes(code) && !seen.has(code)) {
            seen.add(code);
            supports.push(code);
        }
    }
    const done = texts(data.done);
    const next = texts(data.next);
    return {
        supports,
        done: done.length ? done : [""],
        next: next.length ? next : [""],
    };
};

const yearOf = (value) => {
    const text = String(value || "").replaceAll(".", "-");
    const year = Number(text.slice(0, 4));
    if (year >= 1900 && year <= 2100) return year;
    return new Date().getFullYear();
};

const parseMonthDays = (label, year) => {
    const days = [];
    const matches = String(label || "").matchAll(/(\d{1,2})[/.](\d{1,2})/g);
    for (const match of matches) {
        const month = Number(match[1]);
        const day = Number(match[2]);
        const date = new Date(year, month - 1, day);
        if (
            date.getFullYear() === year &&
            date.getMonth() === month - 1 &&
            date.getDate() === day
        ) {
            days.push(date);
        }
    }
    return days;
};

const monthDay = (date) => `${date.getMonth() + 1}/${date.getDate()}`;

const parseFullDate = (value) => {
    const text = String(value || "").replaceAll(".", "-");
    const match = text.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (!match) return null;
    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    const date = new Date(year, month - 1, day);
    if (
        date.getFullYear() !== year ||
        date.getMonth() !== month - 1 ||
        date.getDate() !== day
    ) {
        return null;
    }
    return date;
};

export function nextWeekLabel(doneLabel, reportDate = "") {
    const year = yearOf(reportDate);
    let days = parseMonthDays(doneLabel, year);
    if (!days.length) {
        const fallback = parseFullDate(reportDate);
        days = fallback ? [fallback] : [];
    }
    const end = days[days.length - 1];
    if (!end) return "";
    const monday = new Date(end);
    const weekday = (end.getDay() + 6) % 7;
    monday.setDate(end.getDate() - weekday + 7);
    const friday = new Date(monday);
    friday.setDate(monday.getDate() + 4);
    return `${monthDay(monday)}~${monthDay(friday)}`;
}

export function toWeeklyDeck(report) {
    const data = report && typeof report === "object" ? report : {};
    if (data.schema === WEEKLY_DECK_SCHEMA && Array.isArray(data.done)) {
        const deck = {
            ...data,
            director: String(data.director || "").trim(),
            notices: asNotices(data.notices),
            month_events: asEvents(data.month_events),
            next_month_events: asEvents(data.next_month_events),
            collab: asCollab(data.collab),
            done: data.done.length ? data.done : [emptySection()],
            next: data.next?.length ? data.next : [emptySection()],
        };
        deck.week_label_next =
            nextWeekLabel(deck.week_label_done, deck.report_date) ||
            deck.week_label_next ||
            "";
        return deck;
    }
    const done = [];
    const next = [];
    for (const project of data.projects || []) {
        const title = String(project.projectName || "").trim();
        const doneItems = texts([
            ...(project.completedTasks || []),
            ...(project.inProgressTasks || []),
            ...(project.issues || []),
        ]);
        const nextItems = texts(
            project.nextWeekPlans?.length
                ? project.nextWeekPlans
                : project.nextPlans,
        );
        if (doneItems.length) done.push({ title, items: doneItems });
        if (nextItems.length) next.push({ title, items: nextItems });
    }
    return {
        schema: WEEKLY_DECK_SCHEMA,
        report_date: data.report_date || "",
        author: data.author || "",
        center: data.center || "",
        week_label_done: data.week_label_done || "",
        week_label_next:
            nextWeekLabel(data.week_label_done, data.report_date) ||
            data.week_label_next ||
            "",
        director: String(data.director || "").trim(),
        notices: asNotices(data.notices),
        month_events: asEvents(data.month_events),
        next_month_events: asEvents(data.next_month_events),
        collab: asCollab(data.collab),
        done: done.length ? done : [emptySection()],
        next: next.length ? next : [emptySection()],
        projects: data.projects || [],
        confirmQuestions: data.confirmQuestions || [],
    };
}

export function projectsFromDeck(deck) {
    const map = new Map();
    for (const section of deck?.done || []) {
        const title = String(section.title || "").trim() || "미분류 프로젝트";
        map.set(title, {
            projectName: title,
            completedTasks: (section.items || []).filter(Boolean),
            inProgressTasks: [],
            issues: [],
            nextPlans: [],
            nextWeekPlans: [],
        });
    }
    for (const section of deck?.next || []) {
        const title = String(section.title || "").trim() || "미분류 프로젝트";
        const row = map.get(title) || {
            projectName: title,
            completedTasks: [],
            inProgressTasks: [],
            issues: [],
            nextPlans: [],
            nextWeekPlans: [],
        };
        const items = (section.items || []).filter(Boolean);
        row.nextPlans = items;
        row.nextWeekPlans = items;
        map.set(title, row);
    }
    return [...map.values()];
}

export function formatDeck(deck) {
    if (!deck) return "";
    const lines = [];
    const notices = asNotices(deck.notices);
    if (notices.length) {
        lines.push("[공지사항]");
        notices.forEach((notice, index) => {
            lines.push(`${index + 1}. ${notice.title}`.trim());
            for (const item of notice.body || []) {
                if (item) lines.push(`- ${item}`);
            }
        });
        lines.push("");
    }
    const monthEvents = asEvents(deck.month_events);
    const nextEvents = asEvents(deck.next_month_events);
    if (monthEvents.length || nextEvents.length) {
        lines.push("[금월 주요 이벤트]");
        for (const item of monthEvents) {
            lines.push(`- ${[item.when, item.title].filter(Boolean).join(" ")}`);
        }
        lines.push("[익월 주요 이벤트]");
        for (const item of nextEvents) {
            lines.push(`- ${[item.when, item.title].filter(Boolean).join(" ")}`);
        }
        lines.push("");
    }
    lines.push(`[진행 현황 ${deck.week_label_done || ""}]`.trim());
    for (const section of deck.done || []) {
        if (section.title) lines.push(section.title);
        for (const item of section.items || []) {
            if (item) lines.push(`- ${item}`);
        }
    }
    lines.push("");
    lines.push(`[향후일정 ${deck.week_label_next || ""}]`.trim());
    for (const section of deck.next || []) {
        if (section.title) lines.push(section.title);
        for (const item of section.items || []) {
            if (item) lines.push(`- ${item}`);
        }
    }
    const collab = asCollab(deck.collab);
    const collabDone = (collab.done || []).filter(Boolean);
    const collabNext = (collab.next || []).filter(Boolean);
    if (collab.supports.length || collabDone.length || collabNext.length) {
        lines.push("");
        lines.push("[센터 협업 현황]");
        if (collab.supports.length) {
            lines.push(`지원: ${collab.supports.join(", ")}`);
        }
        for (const item of collabDone) lines.push(`- ${item}`);
        for (const item of collabNext) lines.push(`- ${item}`);
    }
    return lines.join("\n").trim();
}
