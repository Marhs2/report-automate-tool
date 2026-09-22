<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ChevronLeft, ChevronRight } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import { dayCounts } from "../lib/dayStatus";

const router = useRouter();
const { alert: showAlert } = useDialog();
const { getUserActivities, getReports, getHolidays, getTeams } = useApi();

const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

const userActivities = ref([]);
const holidayNames = ref({});

const currentDate = new Date();
const selectedYear = ref(currentDate.getFullYear());
const selectedMonth = ref(currentDate.getMonth() + 1);
const selectedDate = ref("");

const teams = ref([]);
const filterTeam = ref("all");

const parseDate = (dateStr) => new Date(`${dateStr}T00:00:00`);

const formatDate = (date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
};

const startOfToday = () => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return today;
};

const fetchTeams = async () => {
    try {
        teams.value = await getTeams();
    } catch (error) {
        console.error("Error fetching teams:", error);
        showAlert("팀을 불러오지 못했습니다.");
    }
};


function metaFor(dateStr) {
    const date = parseDate(dateStr);
    const weekDay = date.getDay();
    const today = startOfToday();
    const holidayName = holidayNames.value[dateStr] || "";
    const isWeekend = weekDay === 0 || weekDay === 6;
    const isHoliday = Boolean(holidayName);
    return {
        date: dateStr,
        day: date.getDate(),
        weekday: weekDay,
        weekLabel: WEEKDAY_LABELS[weekDay],
        holidayName,
        isWeekend,
        isHoliday,
        isOffday: isWeekend || isHoliday,
        isToday: date.getTime() === today.getTime(),
        isFuture: date.getTime() > today.getTime(),
    };
}

const formatDotDate = (dateStr) => {
    const [year, month, day] = String(dateStr).split("-");
    if (!year || !month || !day) return dateStr;
    return `${year}.${month}.${day}`;
};

const canOpenCell = (item) => Boolean(item?.count > 0);

const openCell = async (activity, item) => {
    if (!canOpenCell(item)) return;
    let reportId = item.report_id;
    if (!reportId) {
        try {
            const reports = await getReports();
            const found = (reports || []).find(
                (report) =>
                    String(report.member_id) === String(activity.member_id) &&
                    report.report_date === item.report_date,
            );
            reportId = found?.id;
        } catch (error) {
            console.error("보고서 찾기 실패:", error);
        }
    }
    if (!reportId) return;
    // 어디서 왔는지 남긴다. 달력에서 열었으면 크럼도 "사용자 활동"이어야 한다.
    router.push({
        name: "report-result",
        params: { id: reportId },
        query: { from: "activities" },
    });
};

async function fetchHolidaysForView() {
    const map = {};
    const rows = await getHolidays(selectedYear.value);
    for (const row of rows || []) {
        if (row?.date) map[row.date] = row.name;
    }
    holidayNames.value = map;
}

async function fetchUserActivities() {
    await fetchHolidaysForView();
    userActivities.value = await getUserActivities(
        selectedYear.value,
        selectedMonth.value,
    );
    selectDefaultDay();
}

function selectDefaultDay() {
    const today = formatDate(startOfToday());
    const { start, end } = rangeBounds.value;
    const todayTime = parseDate(today).getTime();
    const todayInView =
        todayTime >= start.getTime() && todayTime <= end.getTime();
    const fallback = todayInView ? today : formatDate(start);
    if (!selectedDate.value) {
        selectedDate.value = fallback;
        return;
    }
    const selectedTime = parseDate(selectedDate.value).getTime();
    if (selectedTime < start.getTime() || selectedTime > end.getTime()) {
        selectedDate.value = fallback;
    }
}

const isThisMonth = computed(
    () =>
        selectedYear.value === currentDate.getFullYear() &&
        selectedMonth.value === currentDate.getMonth() + 1,
);

function prevMonth() {
    if (selectedMonth.value === 1) {
        selectedMonth.value = 12;
        selectedYear.value--;
    } else {
        selectedMonth.value--;
    }
    fetchUserActivities();
}

function nextMonth() {
    if (selectedMonth.value === 12) {
        selectedMonth.value = 1;
        selectedYear.value++;
    } else {
        selectedMonth.value++;
    }
    fetchUserActivities();
}

function goThisMonth() {
    selectedYear.value = currentDate.getFullYear();
    selectedMonth.value = currentDate.getMonth() + 1;
    fetchUserActivities();
}

onMounted(() => {
    fetchUserActivities();
    fetchTeams();
});

const orderedActivities = computed(() =>
    userActivities.value
        .filter(
            (activity) =>
                filterTeam.value === "all" ||
                String(activity.team_id) === String(filterTeam.value),
        )
        .map((activity) => ({
            ...activity,
            activities: [...(activity.activities || [])].sort((left, right) =>
                left.report_date.localeCompare(right.report_date),
            ),
        })),
);

const activityLookup = computed(() => {
    const byMember = new Map();
    for (const activity of orderedActivities.value) {
        const byDate = new Map();
        for (const item of activity.activities || []) {
            byDate.set(item.report_date, item);
        }
        byMember.set(String(activity.member_id), byDate);
    }
    return byMember;
});

const members = computed(() =>
    orderedActivities.value.map((activity) => ({
        member_id: activity.member_id,
        name: activity.name,
    })),
);

const entriesForDate = (dateStr) =>
    members.value.map((member) => {
        const item =
            activityLookup.value
                .get(String(member.member_id))
                ?.get(dateStr) || { report_date: dateStr, count: 0 };
        return {
            ...member,
            item,
            submitted: Boolean(item.count > 0),
        };
    });

const visibleEntries = (cell) =>
    cell.isOffday
        ? cell.entries.filter((entry) => entry.submitted)
        : cell.entries;

/** 인원이 많으면 한 줄로 나열하기 어렵다. 먼저 챙겨야 하는 미제출을 위로 올린다. */
const railGroups = (cell) => {
    const entries = visibleEntries(cell);
    const submitted = entries.filter((entry) => entry.submitted);
    const missed = entries.filter((entry) => !entry.submitted);
    const groups = [];
    if (missed.length) {
        groups.push({ key: "missed", label: "미제출", people: missed });
    }
    if (submitted.length) {
        groups.push({ key: "submitted", label: "제출", people: submitted });
    }
    return groups;
};

const countsOf = (cell) => dayCounts(cell.entries || [], cell.isOffday);

/** 칸에는 숫자만 둔다. 이름은 날짜를 열었을 때 목록으로 본다. */
const dayStatusLabel = (cell) => {
    const { submitted, total } = ratioOf(cell);
    if (cell.isOffday) {
        if (cell.holidayName && submitted) return `${cell.holidayName} ${submitted}`;
        if (cell.holidayName) return cell.holidayName;
        if (submitted) return `휴일 ${submitted}`;
        return "휴일";
    }
    if (cell.isFuture) return "예정";
    if (!total) return "";
    if (submitted === 0) return "제출 없음";
    if (submitted === total) return "전원 제출";
    return `${submitted}/${total}`;
};

/** 셀에 이름을 나열하는 대신 제출률만 막대로 보여준다. */
const ratioOf = (cell) => {
    const { submitted, missed } = countsOf(cell);
    const total = submitted + missed;
    return {
        submitted,
        total,
        pct: total ? Math.round((submitted / total) * 100) : 0,
    };
};

const dotKind = (cell) => {
    if (cell.outside) return "";
    const { submitted, total } = ratioOf(cell);
    if (!submitted) return "";
    if (!cell.isOffday && !cell.isFuture && total && submitted === total) return "full";
    return "partial";
};

const selectDay = (cell) => {
    if (cell.outside) {
        const date = parseDate(cell.date);
        selectedYear.value = date.getFullYear();
        selectedMonth.value = date.getMonth() + 1;
        selectedDate.value = cell.date;
        fetchUserActivities();
        return;
    }
    selectedDate.value = cell.date;
};

const agendaTitle = (cell) => {
    const [, month, day] = String(cell.date).split("-");
    const longWeek = ["일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일"];
    return `${Number(month)}월 ${Number(day)}일 ${longWeek[cell.weekday] || ""}`;
};

const rangeBounds = computed(() => {
    return {
        start: new Date(selectedYear.value, selectedMonth.value - 1, 1),
        end: new Date(selectedYear.value, selectedMonth.value, 0),
    };
});

const calendarWeeks = computed(() => {
    const { start, end } = rangeBounds.value;
    const gridStart = new Date(start);
    gridStart.setDate(gridStart.getDate() - gridStart.getDay());
    const gridEnd = new Date(end);
    gridEnd.setDate(gridEnd.getDate() + (6 - gridEnd.getDay()));

    const weeks = [];
    const cursor = new Date(gridStart);
    while (cursor.getTime() <= gridEnd.getTime()) {
        const week = [];
        for (let i = 0; i < 7; i++) {
            const dateStr = formatDate(cursor);
            const inRange =
                cursor.getTime() >= start.getTime() &&
                cursor.getTime() <= end.getTime();
            week.push({
                ...metaFor(dateStr),
                outside: !inRange,
                entries: inRange ? entriesForDate(dateStr) : [],
            });
            cursor.setDate(cursor.getDate() + 1);
        }
        weeks.push(week);
    }
    return weeks;
});

const inRangeDays = computed(() =>
    calendarWeeks.value.flat().filter((cell) => !cell.outside),
);

const selectedCell = computed(
    () =>
        inRangeDays.value.find((cell) => cell.date === selectedDate.value) ||
        null,
);

const weekdayCount = computed(
    () => inRangeDays.value.filter((cell) => !cell.isOffday).length,
);

const progressOf = (activity) => {
    const submitted = (activity.activities || []).filter(
        (item) => item.count > 0,
    ).length;
    const total = weekdayCount.value || (activity.activities || []).length;
    return {
        submitted,
        total,
        pct: total ? Math.round((submitted / total) * 100) : 0,
    };
};

const calendarCells = computed(() => calendarWeeks.value.flat());

const progressByMember = computed(() => {
    const map = {};
    for (const activity of orderedActivities.value) {
        map[String(activity.member_id)] = progressOf(activity);
    }
    return map;
});
</script>

<template>
    <div class="page calendar-page">
        <header class="ios-head">
            <div class="ios-title-row">
                <h1>{{ selectedMonth }}월</h1>
                <div class="ios-nav">
                    <button
                        v-if="!isThisMonth"
                        type="button"
                        class="ios-today"
                        @click="goThisMonth"
                    >
                        오늘
                    </button>
                    <button type="button" class="ios-arrow" aria-label="이전 달" @click="prevMonth">
                        <ChevronLeft :size="18" />
                    </button>
                    <button type="button" class="ios-arrow" aria-label="다음 달" @click="nextMonth">
                        <ChevronRight :size="18" />
                    </button>
                </div>
            </div>
            <div class="ios-sub">
                <p>{{ selectedYear }}</p>
                <select
                    id="activity-filter-team"
                    class="team-filter"
                    v-model="filterTeam"
                    aria-label="팀"
                    autocomplete="off"
                >
                    <option value="all">전체 팀</option>
                    <option v-for="team in teams" :key="team.id" :value="String(team.id)">
                        {{ team.team_name }}
                    </option>
                </select>
            </div>
        </header>

        <div v-if="orderedActivities.length === 0" class="empty-state">
            표시할 활동 기록이 없습니다
        </div>

        <div v-else class="ios-board">
            <div class="ios-month">
                <div class="ios-weekdays">
                    <span
                        v-for="(label, index) in WEEKDAY_LABELS"
                        :key="label"
                        :class="{ sun: index === 0, sat: index === 6 }"
                    >
                        {{ label }}
                    </span>
                </div>
                <div class="ios-grid">
                    <button
                        v-for="cell in calendarCells"
                        :key="cell.date"
                        type="button"
                        class="ios-cell"
                        :aria-pressed="selectedDate === cell.date"
                        :aria-label="`${formatDotDate(cell.date)} ${dayStatusLabel(cell)}`"
                        @click="selectDay(cell)"
                    >
                        <span
                            class="ios-num"
                            :class="{
                                sun: cell.weekday === 0,
                                sat: cell.weekday === 6,
                                holiday: cell.isHoliday,
                                outside: cell.outside,
                                today: cell.isToday && !cell.outside,
                                selected: selectedDate === cell.date,
                            }"
                        >
                            {{ cell.day }}
                        </span>
                        <span class="ios-dot" :class="dotKind(cell) || 'is-empty'"></span>
                    </button>
                </div>
            </div>

            <section v-if="selectedCell" class="ios-agenda" :aria-label="agendaTitle(selectedCell)">
                <h2>{{ agendaTitle(selectedCell) }}</h2>
                <p v-if="selectedCell.holidayName" class="ios-holiday">{{ selectedCell.holidayName }}</p>
                <p class="ios-agenda-meta">
                    제출 {{ countsOf(selectedCell).submitted }}
                    <template v-if="!selectedCell.isOffday">
                        · 미제출 {{ countsOf(selectedCell).missed }}
                    </template>
                </p>

                <div
                    v-for="group in railGroups(selectedCell)"
                    :key="group.key"
                    class="agenda-group"
                >
                    <h3>{{ group.label }}</h3>
                    <template v-for="entry in group.people" :key="entry.member_id">
                        <button
                            v-if="entry.submitted"
                            type="button"
                            class="agenda-row"
                            @click="openCell({ member_id: entry.member_id, name: entry.name }, entry.item)"
                        >
                            <span class="agenda-mark full"></span>
                            <span class="agenda-name">{{ entry.name }}</span>
                        </button>
                        <div v-else class="agenda-row is-missed">
                            <span class="agenda-mark"></span>
                            <span class="agenda-name">{{ entry.name }}</span>
                        </div>
                    </template>
                </div>
                <p v-if="!railGroups(selectedCell).length" class="ios-empty">
                    이 날 제출한 보고가 없습니다
                </p>
            </section>
        </div>
    </div>
</template>

<style scoped>
.calendar-page {
    max-width: 880px;
}

.ios-head {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.ios-title-row,
.ios-sub {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}

.ios-title-row h1 {
    margin: 0;
    font-size: 34px;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1;
    color: #1c1c1e;
}

.ios-sub p {
    margin: 0;
    font-size: 15px;
    color: rgba(60, 60, 67, 0.6);
}

.ios-nav {
    display: flex;
    align-items: center;
    gap: 4px;
}

.ios-today,
.ios-arrow {
    border: 0;
    background: transparent;
    color: #007aff;
    cursor: pointer;
}

.ios-today {
    min-height: 44px;
    padding: 0 8px;
    font: inherit;
    font-size: 17px;
    font-weight: 400;
}

.ios-arrow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: 50%;
}

.ios-arrow:hover,
.ios-today:hover {
    background: rgba(0, 122, 255, 0.08);
}

.team-filter {
    height: 32px;
    max-width: 160px;
    padding: 0 28px 0 10px;
    border: 0;
    border-radius: 8px;
    background: rgba(120, 120, 128, 0.12);
    color: #1c1c1e;
    font: inherit;
    font-size: 15px;
}

.ios-board {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.ios-weekdays,
.ios-grid {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
}

.ios-weekdays span {
    text-align: center;
    font-size: 13px;
    font-weight: 600;
    color: rgba(60, 60, 67, 0.6);
}

.ios-weekdays .sun,
.ios-num.sun,
.ios-num.holiday,
.ios-holiday {
    color: #ff3b30;
}

.ios-weekdays .sat,
.ios-num.sat {
    color: #007aff;
}

.ios-num.holiday {
    color: #ff3b30;
}

.ios-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    min-height: 48px;
    margin: 0;
    padding: 2px 0 4px;
    border: 0;
    background: transparent;
    cursor: pointer;
}

.ios-num {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    font-size: 17px;
    font-weight: 400;
    line-height: 1;
    color: #1c1c1e;
}

.ios-num.outside {
    color: rgba(60, 60, 67, 0.3);
}

.ios-num.outside.sun,
.ios-num.outside.sat,
.ios-num.outside.holiday {
    color: rgba(60, 60, 67, 0.3);
}

.ios-num.today {
    background: #ff3b30;
    color: #fff;
    font-weight: 600;
}

.ios-num.selected:not(.today) {
    background: #e5e5ea;
}

.ios-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #007aff;
}

.ios-dot.full {
    background: #34c759;
}

.ios-dot.is-empty {
    background: transparent;
}

.ios-agenda {
    min-width: 0;
    padding: 4px 0 8px;
}

.ios-agenda h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #1c1c1e;
}

.ios-holiday,
.ios-agenda-meta,
.ios-empty {
    margin: 4px 0 0;
    font-size: 13px;
}

.ios-agenda-meta,
.ios-empty {
    color: rgba(60, 60, 67, 0.6);
}

.agenda-group {
    margin-top: 16px;
}

.agenda-group h3 {
    margin: 0 0 4px;
    font-size: 13px;
    font-weight: 600;
    color: rgba(60, 60, 67, 0.6);
}

.agenda-row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    min-height: 44px;
    margin: 0;
    padding: 8px 0;
    border: 0;
    border-top: 1px solid rgba(60, 60, 67, 0.12);
    background: transparent;
    font: inherit;
    text-align: left;
    color: #1c1c1e;
}

.agenda-group .agenda-row:first-of-type {
    border-top: 0;
}

button.agenda-row {
    cursor: pointer;
}

.agenda-row.is-missed {
    color: rgba(60, 60, 67, 0.45);
}

.agenda-mark {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgba(60, 60, 67, 0.28);
    flex: 0 0 auto;
}

.agenda-mark.full {
    background: #34c759;
}

.agenda-name {
    font-size: 17px;
}

@media (min-width: 900px) {
    .ios-board {
        flex-direction: row;
        align-items: flex-start;
        gap: 36px;
    }

    .ios-month {
        flex: 0 0 420px;
        width: 420px;
    }

    .ios-agenda {
        flex: 1;
        padding-top: 28px;
    }
}

@media (max-width: 860px) {
    .ios-title-row h1 {
        font-size: 32px;
    }

    .team-filter {
        max-width: 140px;
        font-size: 16px;
    }
}
</style>
