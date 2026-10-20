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

const sectionHasContent = (section) => {
    if (!section || typeof section !== "object") return false;
    if (String(section.title || "").trim()) return true;
    return (section.items || []).some((item) => String(item || "").trim());
};

/** 제목도 내용도 없는 칸은 빼서, 화면을 열 때마다 빈 프로젝트가 생기지 않게 한다. */
const keptSections = (list) =>
    (Array.isArray(list) ? list : []).filter(sectionHasContent);

const deckSections = (doneRaw, nextRaw) => {
    const done = keptSections(doneRaw);
    const next = keptSections(nextRaw);
    if (!done.length && !next.length) return { done: [emptySection()], next: [] };
    return { done, next };
};

/** 저장 직전 정리: 빈 프로젝트 · 빈 항목 · 빈 공지 · 빈 이벤트 줄을 본다. 편집 중인 원본은 그대로 둔다. */
export function deckForSave(deck) {
    const data = deck && typeof deck === "object" ? deck : {};
    const filled = (item) => (item && typeof item === "object") || String(item ?? "").trim();
    const sections = (list) =>
        keptSections(list).map((section) => ({ ...section, items: (section.items || []).filter(filled) }));
    return {
        ...data,
        done: sections(data.done),
        next: sections(data.next),
        notices: asNotices(data.notices).map((notice) => ({ ...notice, body: notice.body.filter(filled) })),
        month_events: asEvents(data.month_events),
        next_month_events: asEvents(data.next_month_events),
    };
}

/** 진행 현황을 먼저 보고, 제목이 없는 향후일정만 그 뒤에 붙인다. */
export const projectSectionOrder = (data) => {
    const order = [];
    const seen = new Map();
    const add = (section, kind, index) => {
        const titleKey = section.title || `__blank_${kind}_${index}`;
        if (!seen.has(titleKey)) {
            const block = { done: null, next: null };
            seen.set(titleKey, block);
            order.push(block);
        }
        seen.get(titleKey)[kind] = section;
    };
    (data?.done || []).forEach((section, index) => add(section, "done", index));
    (data?.next || []).forEach((section, index) => add(section, "next", index));
    return order;
};

/** 기준 프로젝트 바로 뒤에 섹션을 넣는다. 기준이 없으면 진행 현황 끝에 붙인다. */
export const placeProjectSection = (data, anchor, section) => {
    if (!Array.isArray(data.done)) data.done = [];
    if (anchor?.done) {
        const index = data.done.indexOf(anchor.done);
        if (index >= 0) {
            data.done.splice(index + 1, 0, section);
            return;
        }
    }
    if (anchor?.next) {
        if (!Array.isArray(data.next)) data.next = [];
        const index = data.next.indexOf(anchor.next);
        if (index >= 0) {
            data.next.splice(index + 1, 0, section);
            return;
        }
    }
    data.done.push(section);
};
export const emptyEvent = () => ({ when: "", title: "" });
export const emptyNotice = () => ({ title: "", body: [""] });
export const COLLAB_CENTERS = ["AC", "BC", "DC", "TC", "CSC"];
const PREVIEW_SAMPLE = {
    done: [{ title: "프로젝트 A", items: ["이번 주에 한 일"] }],
    next: [{ title: "프로젝트 A", items: ["다음 주에 할 일"] }],
};

/**
 * 형식 고르기 미리보기: 내 보고 앞부분을 그 형식으로 줄 세운다. backend pptx_fill의 section_lines · paginate_rows와 같은 꼴.
 * text: { kind, done: [{ text, head }], next } / rows: { kind, rows: [{ title, done: ["- …"], next }] }
 */
export function layoutPreview(deck, layout, { projects = 2, items = 2 } = {}) {
    const pick = (sections) =>
        (sections || [])
            .map((section) => ({
                title: String(section?.title || "").trim(),
                items: texts(section?.items).slice(0, items),
            }))
            .filter((section) => section.title || section.items.length)
            .slice(0, projects);
    let done = pick(deck?.done);
    let next = pick(deck?.next);
    if (!done.length && !next.length) {
        done = PREVIEW_SAMPLE.done;
        next = PREVIEW_SAMPLE.next;
    }
    if (layout === "rows") {
        const rows = new Map();
        for (const [key, sections] of [["done", done], ["next", next]]) {
            for (const section of sections) {
                if (!rows.has(section.title)) rows.set(section.title, { title: section.title, done: [], next: [] });
                rows.get(section.title)[key].push(...section.items.map((item) => `- ${item}`));
            }
        }
        return { kind: "rows", rows: [...rows.values()].slice(0, projects) };
    }
    const lines = (sections) =>
        sections.flatMap((section, index) =>
            layout === "bracket"
                ? [
                      ...(section.title ? [{ text: `[${section.title}]`, head: true }] : []),
                      ...section.items.map((text) => ({ text, head: false })),
                  ]
                : [
                      { text: `${index + 1}. ${section.title}`.trim(), head: true },
                      ...section.items.map((text) => ({ text: `- ${text}`, head: false })),
                  ],
        );
    return { kind: "text", done: lines(done), next: lines(next) };
}

/** 주요 업무 현황 PPT 형식(deck.layout). backend/weekly_deck.py WEEKLY_LAYOUTS와 같은 값. 비면 numbered. */
export const WEEKLY_LAYOUTS = [
    { value: "numbered", label: "1. 번호" },
    { value: "bracket", label: "[대괄호]" },
    { value: "rows", label: "구분 표" },
];
/** 센터 협업 현황: 센터마다 진행 현황(done) · 향후일정(next). backend/weekly_deck.py _as_collab과 같은 모양. */
export const emptyCollab = () => ({
    centers: Object.fromEntries(COLLAB_CENTERS.map((code) => [code, { done: [], next: [] }])),
});

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

/** 예전 모양({supports, done, next})은 첫 지원 센터(없으면 AC) 칸으로 옮긴다. */
export const asCollab = (raw) => {
    const data = raw && typeof raw === "object" ? raw : {};
    const out = emptyCollab();
    if (data.centers && typeof data.centers === "object") {
        for (const [key, row] of Object.entries(data.centers)) {
            const code = String(key || "").trim().toUpperCase();
            if (out.centers[code] && row && typeof row === "object") {
                out.centers[code] = { done: texts(row.done), next: texts(row.next) };
            }
        }
        return out;
    }
    const supports = (data.supports || []).map((item) => String(item || "").trim().toUpperCase());
    const target = supports.find((code) => out.centers[code]) || COLLAB_CENTERS[0];
    out.centers[target] = { done: texts(data.done), next: texts(data.next) };
    return out;
};

export const collabItemCount = (collab) =>
    COLLAB_CENTERS.reduce((sum, code) => {
        const row = collab?.centers?.[code] || {};
        return sum + [...(row.done || []), ...(row.next || [])].filter((item) => String(item || "").trim()).length;
    }, 0);

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

const CONFIRM_FIELD_LABELS = [
    ["nextWeekPlans", "향후일정"],
    ["inProgressTasks", "진행"],
    ["completedTasks", "완료"],
    ["nextPlans", "향후일정"],
];

export function humanizeConfirmText(text) {
    let out = String(text || "");
    for (const [field, label] of CONFIRM_FIELD_LABELS) {
        out = out.replaceAll(field, label);
    }
    return out;
}

function nextSectionFilled(deck, title) {
    return (deck?.next || []).some(
        (section) =>
            String(section?.title || "").trim() === title &&
            (section.items || []).some((item) => String(item || "").trim()),
    );
}

/** 이미 향후일정에 적은 프로젝트는 빈 계획 질문을 다시 내지 않는다. */
export function visibleConfirmQuestions(questions, deck) {
    return (Array.isArray(questions) ? questions : [])
        .map((item, index) => ({
            id: item?.id || `q-${index}`,
            text: humanizeConfirmText(item?.text).trim(),
            ifNo: humanizeConfirmText(item?.ifNo).trim(),
        }))
        .filter((item) => item.text)
        .filter((item) => {
            const emptyNext =
                item.id === "empty-next" ||
                item.text.includes("다음 주 계획이 비어") ||
                item.text.includes("향후일정이 비어");
            if (!emptyNext) return true;
            const name = item.text.split("의 ")[0].replace(/^'/, "").trim();
            const head = name.split(" 외 ")[0].trim();
            if (!head || name.includes(" 외 ")) return true;
            return !nextSectionFilled(deck, head);
        })
        .slice(0, 3);
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
            ...deckSections(data.done, data.next),
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
        layout: data.layout || "",
        notices: asNotices(data.notices),
        month_events: asEvents(data.month_events),
        next_month_events: asEvents(data.next_month_events),
        collab: asCollab(data.collab),
        ...deckSections(done, next),
        projects: data.projects || [],
        confirmQuestions: data.confirmQuestions || [],
    };
}

/* PPT 진행 현황은 한 칸이라 완료, 진행, 이슈가 섞여 있다.
   줄 종류는 legacy projects로 되찾는다. */

export const DONE_KINDS = [
    { kind: "done", label: "완료" },
    { kind: "progress", label: "진행" },
    { kind: "issue", label: "이슈" },
    { kind: "other", label: "기타" },
];

const normKey = (value) => String(value || "").replace(/\s+/g, "").toLowerCase();

const titleKey = (value) => normKey(value) || "미분류프로젝트";

export function doneKindMap(deck) {
    const map = new Map();
    for (const project of deck?.projects || []) {
        if (!project || typeof project !== "object") continue;
        const title = titleKey(project.projectName);
        const put = (list, kind) => {
            for (const text of texts(list)) {
                const key = `${title}\u0000${normKey(text)}`;
                // 완료로 먼저 잡힌 줄은 덮어쓰지 않는다. 같은 문장이 두 칸에 있으면 완료가 이긴다.
                if (!map.has(key)) map.set(key, kind);
            }
        };
        put(project.completedTasks, "done");
        put(project.inProgressTasks, "progress");
        put(project.issues, "issue");
    }
    return map;
}

/** 한 프로젝트의 진행 현황 줄들을 종류별로 묶는다. 비어 있는 종류는 빼낸다. */
export function groupDoneItems(deck, section) {
    const map = doneKindMap(deck);
    const title = titleKey(section?.title);
    const buckets = { done: [], progress: [], issue: [], other: [] };
    for (const raw of section?.items || []) {
        const text = String(raw || "").trim();
        if (!text) continue;
        const kind = map.get(`${title}\u0000${normKey(text)}`) || "other";
        buckets[kind].push(text);
    }
    return DONE_KINDS.filter((entry) => buckets[entry.kind].length).map((entry) => ({
        ...entry,
        items: buckets[entry.kind],
    }));
}

/** PPT 전용 칸이 실제로 채워져 있는지. 0건이면 읽는 화면에 띄우지 않는다. */
export function deckExtrasCount(deck) {
    const notices = asNotices(deck?.notices).length;
    const events =
        asEvents(deck?.month_events).length +
        asEvents(deck?.next_month_events).length;
    const collab = collabItemCount(asCollab(deck?.collab));
    return {
        notices,
        events,
        collab,
        total: notices + events + collab,
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
    if (collabItemCount(collab)) {
        lines.push("");
        lines.push("[센터 협업 현황]");
        for (const code of COLLAB_CENTERS) {
            const row = collab.centers[code];
            if (!row.done.length && !row.next.length) continue;
            lines.push(code);
            for (const item of row.done) lines.push(`- 진행: ${item}`);
            for (const item of row.next) lines.push(`- 향후: ${item}`);
        }
    }
    return lines.join("\n").trim();
}
