/** 사용자 활동 표: 사람(행) × 평일(열). 누가 언제 일일보고를 빠뜨렸는지 한눈에 본다. */

export const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

const pad = (n) => String(n).padStart(2, "0");
const toIso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const fromIso = (iso) => new Date(`${iso}T00:00:00`);

export function todayIso(now = new Date()) {
    return toIso(now);
}

/** 주는 그 주 월~금, 달은 그 달의 월~금 전부. 주말은 열로 두지 않는다. */
export function periodDays(mode, anchorIso) {
    const anchor = fromIso(anchorIso);
    let start;
    let end;
    if (mode === "week") {
        start = new Date(anchor);
        start.setDate(anchor.getDate() - ((anchor.getDay() + 6) % 7));
        end = new Date(start);
        end.setDate(start.getDate() + 4);
    } else {
        start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
        end = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
    }
    const days = [];
    for (const cursor = new Date(start); cursor <= end; cursor.setDate(cursor.getDate() + 1)) {
        const weekday = cursor.getDay();
        if (weekday !== 0 && weekday !== 6) days.push(toIso(cursor));
    }
    return days;
}

export function shiftAnchor(mode, anchorIso, step) {
    const anchor = fromIso(anchorIso);
    if (mode === "week") anchor.setDate(anchor.getDate() + step * 7);
    else anchor.setMonth(anchor.getMonth() + step, 1);
    return toIso(anchor);
}

export function periodLabel(mode, days) {
    if (!days.length) return "";
    const first = fromIso(days[0]);
    if (mode === "month") return `${first.getFullYear()}년 ${first.getMonth() + 1}월`;
    const last = fromIso(days[days.length - 1]);
    return `${first.getMonth() + 1}.${first.getDate()} ~ ${last.getMonth() + 1}.${last.getDate()}`;
}

/** done: 냈음 · off: 공휴일 · future: 아직 안 온 날 · missed: 지난 평일인데 없음. 오늘은 아직 낼 수 있으니 future로 본다. */
export function cellState(dateIso, item, { today, holidays = {} }) {
    if (item && item.count > 0) return "done";
    if (holidays[dateIso]) return "off";
    if (dateIso >= today) return "future";
    return "missed";
}

/**
 * 부서별로 묶은 행. 보고를 안 쓰는 관리자는 기간 안에 낸 날이 있을 때만 넣는다.
 * missedFirst면 부서 안에서 빠진 날이 많은 사람을 위로 올린다.
 * query는 이름 검색, onlyMissed는 빠진 날이 있는 사람만. 부서 집계(dayCounts 포함)는 보이는 사람만 센다.
 */
export function buildRows(
    activities,
    days,
    {
        today,
        holidays = {},
        adminIds = new Set(),
        teamNames = {},
        teamFilter = "all",
        missedFirst = false,
        query = "",
        onlyMissed = false,
    },
) {
    const needle = String(query || "").trim().toLowerCase();
    const teams = [];
    const byTeam = new Map();
    for (const activity of activities || []) {
        if (teamFilter !== "all" && String(activity.team_id) !== String(teamFilter)) continue;
        if (needle && !String(activity.name || "").toLowerCase().includes(needle)) continue;
        const items = new Map((activity.activities || []).map((item) => [item.report_date, item]));
        const cells = days.map((date) => {
            const item = items.get(date);
            return { date, state: cellState(date, item, { today, holidays }), reportId: item?.report_id ?? null };
        });
        const submitted = cells.filter((cell) => cell.state === "done").length;
        if (adminIds.has(String(activity.member_id)) && !submitted) continue;
        const missed = cells.filter((cell) => cell.state === "missed").length;
        if (onlyMissed && !missed) continue;
        const key = String(activity.team_id ?? "");
        if (!byTeam.has(key)) {
            const team = { teamId: activity.team_id ?? null, teamName: teamNames[key] || "부서 없음", members: [] };
            byTeam.set(key, team);
            teams.push(team);
        }
        byTeam.get(key).members.push({
            memberId: activity.member_id,
            name: activity.name,
            cells,
            submitted,
            missed,
            due: submitted + missed,
        });
    }
    for (const team of teams) {
        team.members.sort((a, b) =>
            (missedFirst ? b.missed - a.missed : 0) || String(a.name).localeCompare(String(b.name), "ko"),
        );
        team.submitted = team.members.reduce((sum, m) => sum + m.submitted, 0);
        team.due = team.members.reduce((sum, m) => sum + m.due, 0);
        team.dayCounts = days.map((date, index) => {
            const states = team.members.map((m) => m.cells[index].state);
            return {
                date,
                done: states.filter((state) => state === "done").length,
                missed: states.filter((state) => state === "missed").length,
                total: states.length,
                off: Boolean(holidays[date]),
                future: date >= today,
            };
        });
    }
    teams.sort((a, b) => Number(a.teamId ?? 0) - Number(b.teamId ?? 0));
    return teams;
}

/** 부서별 오늘 제출 요약(관리자 홈). 오늘이 기간 밖(주말)이면 빈 배열. */
export function todayByTeam(teams, days, today) {
    const index = days.indexOf(today);
    if (index < 0) return [];
    return teams
        .map((team) => {
            const pending = team.members
                .filter((member) => member.cells[index].state !== "done")
                .map((member) => member.name);
            return {
                teamId: team.teamId,
                teamName: team.teamName,
                done: team.members.length - pending.length,
                total: team.members.length,
                pending,
            };
        })
        .filter((team) => team.total);
}

export function dayHeader(dateIso, holidays = {}) {
    const date = fromIso(dateIso);
    return {
        date: dateIso,
        day: date.getDate(),
        weekLabel: WEEKDAY_LABELS[date.getDay()],
        holidayName: holidays[dateIso] || "",
    };
}
