/** 오늘을 여기서만 계산한다. 최신 저장일이 미래 시드면 금요일이 오늘이 된다. */

export function toDateString(value) {
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) return "";
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}

export function todayString(now = new Date()) {
    return toDateString(now);
}

/** YYYY-MM-DD 문자열 비교로 충분하다. 시간대 변환을 타지 않는다. */
export function isFutureDate(dateStr, now = new Date()) {
    const text = String(dateStr || "").slice(0, 10);
    if (!text) return false;
    return text > todayString(now);
}

export function isPastOrToday(dateStr, now = new Date()) {
    const text = String(dateStr || "").slice(0, 10);
    if (!text) return false;
    return text <= todayString(now);
}

function parseDateString(dateStr) {
    const [year, month, day] = String(dateStr || "")
        .slice(0, 10)
        .split("-")
        .map(Number);
    if (!year || !month || !day) return null;
    const date = new Date(year, month - 1, day);
    if (
        date.getFullYear() !== year ||
        date.getMonth() !== month - 1 ||
        date.getDate() !== day
    ) {
        return null;
    }
    return date;
}

/** 월요일 시작. 일요일(getDay() === 0)은 그 주의 마지막 날로 본다. */
export function mondayOf(dateStr) {
    const date = parseDateString(dateStr);
    if (!date) return "";
    const weekday = (date.getDay() + 6) % 7;
    const monday = new Date(date);
    monday.setDate(date.getDate() - weekday);
    return toDateString(monday);
}

/** 월~일 7일 범위. 목록의 "이번 주" 필터가 쓴다. */
export function weekRange(now = new Date()) {
    const start = mondayOf(todayString(now));
    const monday = parseDateString(start);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return { start, end: toDateString(sunday) };
}

/** 월~금 5일 범위. 주간보고가 쓰는 업무 주간. */
export function workWeekRange(dateStr) {
    const start = mondayOf(dateStr);
    if (!start) return { start: "", end: "" };
    const monday = parseDateString(start);
    const friday = new Date(monday);
    friday.setDate(monday.getDate() + 4);
    return { start, end: toDateString(friday) };
}

/** 같은 주에 만든 주간보고를 한 줄로 묶는 키. 날짜 조합이 달라도 같은 주면 같은 키. */
export function weekKeyOf(dateStr) {
    return mondayOf(dateStr);
}

/** 날짜 목록을 주 단위로 접는다. 가장 늦은 날짜가 그 주를 대표한다. */
export function weekKeyOfDates(dates) {
    const days = [...(dates || [])]
        .map((value) => String(value || "").slice(0, 10))
        .filter(Boolean)
        .sort();
    if (!days.length) return "";
    return weekKeyOf(days[days.length - 1]);
}

export function weekRangeLabel(dateStr) {
    const { start, end } = workWeekRange(dateStr);
    if (!start) return "";
    return `${shortDate(start)} ~ ${shortDate(end)}`;
}

export function shortDate(dateStr) {
    const [, month, day] = String(dateStr || "")
        .slice(0, 10)
        .split("-");
    if (!month || !day) return String(dateStr || "");
    return `${Number(month)}.${Number(day)}`;
}

export const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

export function weekdayLabelOf(dateStr) {
    const date = parseDateString(dateStr);
    if (!date) return "";
    return WEEKDAY_LABELS[date.getDay()];
}
