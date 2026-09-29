/** 이번 주(월~금) 제출 현황. 사이드바 배지, 내 현황, 모바일 탭이 같은 판단을 쓴다. */

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

const pad = (value) => String(value).padStart(2, "0");

export const isoDate = (day) =>
    `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`;

const parseIso = (text) => {
    const [year, month, day] = String(text || "").split("-").map(Number);
    if (!year || !month || !day) return null;
    return new Date(year, month - 1, day);
};

/** 기준일이 속한 주의 월~금 날짜. 주말이면 그 주 월~금이다. */
export function weekDays(today) {
    const base = today instanceof Date ? today : parseIso(today);
    if (!base) return [];
    const offset = (base.getDay() + 6) % 7;
    const monday = new Date(base.getFullYear(), base.getMonth(), base.getDate() - offset);
    return Array.from({ length: 5 }, (_, index) => {
        const day = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + index);
        return { date: isoDate(day), weekday: WEEKDAYS[day.getDay()], day: day.getDate() };
    });
}

/** getUserActivities 응답에서 한 사람의 날짜별 저장 여부를 뽑는다. */
export function savedDatesOf(rows, memberId) {
    const mine = (rows || []).find((row) => String(row?.member_id) === String(memberId));
    const saved = new Set();
    for (const activity of mine?.activities || []) {
        if (Number(activity?.count) > 0) saved.add(String(activity.report_date));
    }
    return saved;
}

/**
 * 요일별 상태. saved: 저장됨, missing: 지난 날인데 없음,
 * today: 오늘인데 아직 없음, upcoming: 아직 오지 않은 날.
 */
export function weekStatus(days, savedDates, todayIso) {
    return (days || []).map((entry) => {
        let state = "upcoming";
        if (savedDates?.has(entry.date)) state = "saved";
        else if (entry.date === todayIso) state = "today";
        else if (entry.date < todayIso) state = "missing";
        return { ...entry, state };
    });
}

/** 오늘 보고 상태. 저장이 초안보다 앞선다. 주말은 null(재촉하지 않는다). */
export function todayState({ saved = false, hasDraft = false, weekend = false } = {}) {
    if (saved) return "saved";
    if (hasDraft) return "draft";
    if (weekend) return null;
    return "missing";
}

export const TODAY_LABELS = {
    saved: "오늘 제출",
    draft: "오늘 초안",
    missing: "오늘 미제출",
};

/**
 * 하루 제출 현황. 부서가 있는 실무자만 센다. 관리자 계정은 보고 대상이 아니다.
 * 반환: { total, saved, missing: [이름...] }
 */
export function daySubmission(members, reports, day) {
    const people = (members || []).filter(
        (member) => member?.team_id != null && !member?.is_admin,
    );
    const savedIds = new Set(
        (reports || [])
            .filter((report) => String(report?.report_date) === String(day))
            .map((report) => String(report.member_id)),
    );
    const missing = people
        .filter((member) => !savedIds.has(String(member.id)))
        .map((member) => String(member.name || ""))
        .sort((a, b) => a.localeCompare(b, "ko"));
    return { total: people.length, saved: people.length - missing.length, missing };
}
