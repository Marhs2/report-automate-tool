export function memberInitials(name) {
    const text = String(name ?? "").trim();
    if (!text) return "?";
    if (text.length === 1) return text;
    return `${text[0]}${text[text.length - 1]}`;
}

export const CELL_EVENT_LIMIT = 3;

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
