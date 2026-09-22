/** 이슈가 있는 사람을 위로 올린다. pinMemberId는 접혀도 맨 위에 둔다. */
export function sortByIssuesFirst(reports, issueCountOf, { pinMemberId } = {}) {
    const pin = pinMemberId == null ? "" : String(pinMemberId);
    const isPinned = (report) =>
        pin !== "" && String(report?.member_id ?? "") === pin;
    return [...(reports || [])].sort((left, right) => {
        const pinGap = Number(isPinned(right)) - Number(isPinned(left));
        if (pinGap) return pinGap;
        const gap = issueCountOf(right) - issueCountOf(left);
        if (gap) return gap;
        return String(left.member_name || "").localeCompare(
            String(right.member_name || ""),
            "ko",
        );
    });
}

export function peakSubmissionDay(days = []) {
    const work = days.filter((day) => !day.isOffday);
    if (!work.length) return null;
    return work.reduce((best, day) =>
        day.submitted > best.submitted ? day : best,
    );
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
