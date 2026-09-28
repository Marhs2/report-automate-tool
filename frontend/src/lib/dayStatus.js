export function memberInitials(name) {
    const text = String(name ?? "").trim();
    if (!text) return "?";
    if (text.length === 1) return text;
    return `${text[0]}${text[text.length - 1]}`;
}

export const CELL_EVENT_LIMIT = 3;

/** 날짜 현황에서 더 보기를 누를 때마다 여는 이름 수. */
export const AGENDA_NAME_LIMIT = 5;

export function filterPeopleByName(people = [], query = "") {
    const needle = String(query).trim().toLowerCase();
    if (!needle) return people;
    return people.filter((entry) =>
        String(entry?.name || "")
            .toLowerCase()
            .includes(needle),
    );
}

/** 검색 중이면 맞는 이름을 모두 보여주고, 아니면 visible명까지만 자른다. */
export function previewPeople(
    people = [],
    { query = "", visible = 0, limit = AGENDA_NAME_LIMIT } = {},
) {
    const matched = filterPeopleByName(people, query);
    const page = Math.max(1, Number(limit) || AGENDA_NAME_LIMIT);
    if (String(query).trim()) {
        return { shown: matched, hidden: 0, matched, next: 0 };
    }
    const count = Math.max(page, Number(visible) || page);
    if (matched.length <= count) {
        return { shown: matched, hidden: 0, matched, next: 0 };
    }
    const hidden = matched.length - count;
    return {
        shown: matched.slice(0, count),
        hidden,
        matched,
        next: Math.min(page, hidden),
    };
}

export function cellEventBars(entries = [], limit = CELL_EVENT_LIMIT) {
    const submitted = entries.filter((entry) => entry.submitted);
    if (submitted.length <= limit) {
        return { shown: submitted, overflow: 0, hidden: [] };
    }
    const shown = submitted.slice(0, limit);
    const hidden = submitted.slice(limit);
    return { shown, overflow: hidden.length, hidden };
}

export function overflowTooltip(hidden = []) {
    const names = hidden.map((entry) => entry.name).filter(Boolean);
    if (!names.length) return "";
    if (names.length <= 6) return names.join(" · ");
    return `${names.slice(0, 6).join(" · ")} 외 ${names.length - 6}명`;
}

export function dayCounts(entries = [], isOffday = false) {
    const submitted = entries.filter((entry) => entry.submitted).length;
    const missed = isOffday
        ? 0
        : entries.filter((entry) => !entry.submitted).length;
    return { submitted, missed };
}

export function isWeekendDate(dateStr) {
    const date = new Date(`${dateStr}T00:00:00`);
    if (Number.isNaN(date.getTime())) return false;
    const weekDay = date.getDay();
    return weekDay === 0 || weekDay === 6;
}

export function isOffdayDate(dateStr, holidayNames = {}) {
    return isWeekendDate(dateStr) || Boolean(holidayNames[dateStr]);
}

export function missingOnDate(dateStr, missingNames = [], holidayNames = {}) {
    if (isOffdayDate(dateStr, holidayNames)) return [];
    return missingNames;
}
