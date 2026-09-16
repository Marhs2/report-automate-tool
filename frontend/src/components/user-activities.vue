<script setup>
import { onMounted, ref, reactive, computed, watch } from "vue";
import { useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useToast } from "../composables/useToast";
import AppPageHeader from "./ui/AppPageHeader.vue";

const router = useRouter();
const { error: toastError } = useToast();
const { getUserActivities, getReports, getHolidays, getTeams } = useApi();

const props = defineProps({
    startDate: { type: String, default: "" },
    endDate: { type: String, default: "" },
    embedded: { type: Boolean, default: false },
    filterTeam: { type: String, default: "all" },
});

const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

const userActivities = ref([]);
const holidayNames = ref({});

const currentDate = new Date();
const selectedYear = ref(currentDate.getFullYear());
const selectedMonth = ref(currentDate.getMonth() + 1);

const tooltip = reactive({
    visible: false,
    x: 0,
    y: 0,
    content: "",
});

let hideTimer = null;

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
        toastError("팀을 불러오지 못했습니다.");
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
        weekLabel: WEEKDAY_LABELS[weekDay],
        holidayName,
        isWeekend,
        isHoliday,
        isOffday: isWeekend || isHoliday,
        isToday: date.getTime() === today.getTime(),
    };
}

const formatDotDate = (dateStr) => {
    const [year, month, day] = String(dateStr).split("-");
    if (!year || !month || !day) return dateStr;
    return `${year}.${month}.${day}`;
};

const cellStatus = (dateStr, count) => {
    const meta = metaFor(dateStr);
    if (count > 0) return "제출";
    if (meta.isHoliday) return meta.holidayName;
    if (meta.isWeekend) return "주말";
    return "미제출";
};

const canOpenCell = (item) => Boolean(item?.count > 0);

const openCell = async (activity, item) => {
    if (!canOpenCell(item)) return;
    hideTooltip();
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
    router.push(`/report-result/${reportId}`);
};

const cellLabel = (name, item) => {
    const meta = metaFor(item.report_date);
    return `${name} ${formatDotDate(item.report_date)} (${meta.weekLabel}) ${cellStatus(item.report_date, item.count)}`;
};

function showTooltip(e, name, item) {
    clearTimeout(hideTimer);
    const meta = metaFor(item.report_date);
    tooltip.content = `${name} · ${meta.weekLabel} ${formatDotDate(item.report_date)} · ${cellStatus(item.report_date, item.count)}`;
    tooltip.x = e.clientX + 16;
    tooltip.y = e.clientY - 16;
    tooltip.visible = true;
}

function moveTooltip(e) {
    tooltip.x = e.clientX + 16;
    tooltip.y = e.clientY - 16;
}

function hideTooltip() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
        tooltip.visible = false;
    }, 60);
}

async function fetchHolidaysForView() {
    const years = new Set();
    if (props.startDate && props.endDate) {
        years.add(Number(props.startDate.slice(0, 4)));
        years.add(Number(props.endDate.slice(0, 4)));
    } else {
        years.add(selectedYear.value);
    }
    const map = {};
    await Promise.all(
        [...years].map(async (year) => {
            const rows = await getHolidays(year);
            for (const row of rows || []) {
                if (row?.date) map[row.date] = row.name;
            }
        }),
    );
    holidayNames.value = map;
}

async function fetchUserActivities() {
    await fetchHolidaysForView();
    const activities = await getUserActivities(
        selectedYear.value,
        selectedMonth.value,
        props.startDate,
        props.endDate,
    );
    userActivities.value = activities;
}

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

onMounted(() => {
    fetchUserActivities();
    fetchTeams();
});

watch(
    () => [props.startDate, props.endDate],
    ([startDate, endDate], [previousStartDate, previousEndDate] = []) => {
        if (
            startDate &&
            endDate &&
            (startDate !== previousStartDate || endDate !== previousEndDate)
        ) {
            fetchUserActivities();
        }
    },
);

const activeFilterTeam = computed(() =>
    props.embedded ? String(props.filterTeam ?? "all") : filterTeam.value,
);

const orderedActivities = computed(() =>
    userActivities.value
        .filter(
            (activity) =>
                activeFilterTeam.value === "all" ||
                String(activity.team_id) === String(activeFilterTeam.value),
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

const rangeBounds = computed(() => {
    if (props.startDate && props.endDate) {
        return {
            start: parseDate(props.startDate),
            end: parseDate(props.endDate),
        };
    }
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

const hasToday = computed(() =>
    inRangeDays.value.some((cell) => cell.isToday),
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

const periodLabel = computed(() =>
    props.startDate && props.endDate
        ? `${props.startDate} ~ ${props.endDate} 제출 현황`
        : `${selectedYear.value}년 ${selectedMonth.value}월 활동 기록`,
);
</script>

<template>
    <div :class="embedded ? 'activity-section' : 'page calendar-page is-wide'">
        <AppPageHeader v-if="!embedded" :title="periodLabel" />

        <div class="view-controls">
            <div v-if="!embedded" class="month-tools">
                <div class="month-nav">
                    <button class="btn btn-small" aria-label="이전 달" @click="prevMonth">
                        &lt;
                    </button>
                    <span class="current-period">{{ selectedYear }}년 {{ selectedMonth }}월</span>
                    <button class="btn btn-small" aria-label="다음 달" @click="nextMonth">
                        &gt;
                    </button>
                </div>
                <select
                    id="activity-filter-team"
                    class="month-team-select"
                    v-model="filterTeam"
                    aria-label="팀"
                    autocomplete="off"
                >
                    <option value="all">전체</option>
                    <option v-for="team in teams" :key="team.id" :value="String(team.id)">
                        {{ team.team_name }}
                    </option>
                </select>
            </div>
            <div v-if="orderedActivities.length" class="legend">
                <span class="legend-item">
                    <span class="swatch submitted"></span> 제출
                </span>
                <span class="legend-item">
                    <span class="swatch missed"></span> 미제출
                </span>
                <span class="legend-item">
                    <span class="swatch weekend"></span> 주말
                </span>
                <span class="legend-item">
                    <span class="swatch holiday"></span> 공휴일
                </span>
                <span v-if="hasToday" class="legend-item">
                    <span class="swatch today"></span> 오늘
                </span>
            </div>
        </div>

        <div v-if="orderedActivities.length === 0" class="empty-state">
            표시할 활동 기록이 없습니다
        </div>
        <template v-else>
            <div class="member-summary">
                <div v-for="activity in orderedActivities" :key="activity.member_id" class="summary-item">
                    <div class="summary-top">
                        <span class="summary-name">{{ activity.name }}</span>
                        <span class="summary-count">{{ progressOf(activity).submitted }}/{{
                            progressOf(activity).total
                        }}
                            평일</span>
                    </div>
                    <div class="progress-track"
                        :title="`${progressOf(activity).submitted}/${progressOf(activity).total} 평일`">
                        <span class="progress-fill" :style="{
                            width: progressOf(activity).pct + '%',
                        }"></span>
                    </div>
                </div>
            </div>

            <div class="card calendar-card">
                <div class="cal-weekdays">
                    <span v-for="label in WEEKDAY_LABELS" :key="label" :class="{
                        weekend: label === '일' || label === '토',
                    }">
                        {{ label }}
                    </span>
                </div>
                <div class="cal-weeks">
                    <div v-for="(week, weekIndex) in calendarWeeks" :key="weekIndex" class="cal-week">
                        <div v-for="cell in week" :key="cell.date" class="cal-day" :class="{
                            outside: cell.outside,
                            weekend: cell.isWeekend,
                            holiday: cell.isHoliday,
                            today: cell.isToday && !cell.outside,
                        }">
                            <div class="cal-day-head">
                                <span class="cal-day-num">{{ cell.day }}</span>
                                <span v-if="cell.holidayName && !cell.outside" class="cal-holiday"
                                    :title="cell.holidayName">{{ cell.holidayName }}</span>
                            </div>
                            <div v-if="!cell.outside" class="cal-entries">
                                <button v-for="entry in visibleEntries(cell)" :key="entry.member_id" class="cal-chip"
                                    :class="{
                                        submitted: entry.submitted,
                                        missed:
                                            !entry.submitted &&
                                            !cell.isOffday,
                                    }" :disabled="!entry.submitted" :aria-label="cellLabel(entry.name, entry.item)
                                        " @click="
                                            openCell(
                                                {
                                                    member_id: entry.member_id,
                                                    name: entry.name,
                                                },
                                                entry.item,
                                            )
                                            " @mouseenter="
                                                showTooltip(
                                                    $event,
                                                    entry.name,
                                                    entry.item,
                                                )
                                                " @mousemove="moveTooltip" @mouseleave="hideTooltip">
                                    {{ entry.name }}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>

        <transition name="tooltip-fade">
            <div v-if="tooltip.visible" class="tooltip" :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
                {{ tooltip.content }}
            </div>
        </transition>
    </div>
</template>

<style scoped>
.activity-section {
    margin-bottom: var(--space-2);
}

.activity-section .cal-day {
    min-height: 96px;
    padding: var(--space-2);
}

.activity-section .cal-chip {
    font-size: var(--fs-11);
    padding: 2px var(--space-2);
}

.activity-section .member-summary {
    margin-bottom: var(--space-2);
}

.activity-section .view-controls {
    margin-bottom: var(--space-2);
}

.calendar-page {
    max-width: 1200px;
}

.view-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-4);
    flex-wrap: wrap;
    margin-bottom: var(--space-3);
}

.month-tools {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
    min-width: 0;
}

.month-nav {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
}

.current-period {
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    white-space: nowrap;
}

.month-team-select {
    height: 32px;
    width: auto;
    min-width: 108px;
    padding: 0 var(--space-6) 0 var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--text-strong);
    font: inherit;
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    cursor: pointer;
}

.month-team-select:hover {
    border-color: var(--text);
}

.month-team-select:focus {
    outline: none;
    border-color: var(--text-strong);
}

.legend {
    display: flex;
    gap: var(--space-3);
    font-size: var(--fs-12);
    color: var(--text);
}

.legend-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
}

/* 범례 스와치는 달력 셀/칩과 같은 상태 토큰을 쓴다. 테두리는 box-shadow 대신 border. */
.swatch {
    box-sizing: border-box;
    width: 10px;
    height: 10px;
    border-radius: 3px;
    display: inline-block;
}

.swatch.submitted {
    background: var(--success-fg);
}

.swatch.missed {
    background: var(--border-strong);
}

.swatch.weekend {
    background: var(--surface-soft);
    border: 1px solid var(--border);
}

.swatch.holiday {
    background: var(--danger-bg);
    border: 1px solid var(--danger-border);
}

.swatch.today {
    background: var(--surface);
    outline: 2px solid var(--accent);
}

.member-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--space-2);
    margin-bottom: var(--space-3);
}

.summary-item {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
}

.summary-top {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--space-2);
}

.summary-name {
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    font-size: var(--fs-13);
}

.summary-count {
    color: var(--text);
    font-size: var(--fs-11);
    font-weight: var(--fw-medium);
    white-space: nowrap;
}

.progress-track {
    height: 4px;
    border-radius: var(--radius-pill);
    background: var(--border);
    overflow: hidden;
}

.progress-fill {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: var(--success-fg);
}

.calendar-card {
    padding: var(--space-4);
}

.cal-weekdays {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: var(--space-2);
    margin-bottom: var(--space-2);
}

.cal-weekdays span {
    text-align: center;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
    padding: var(--space-2) 0;
}

.cal-weekdays .weekend {
    opacity: 0.7;
}

.cal-weeks {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.cal-week {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: var(--space-2);
}

.cal-day {
    min-height: 128px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: var(--space-2);
    background: var(--surface);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

/* 주말은 중립 톤(--surface-soft), 공휴일은 위험 톤(--danger-bg)으로 구분한다. */
.cal-day.weekend,
.cal-day.holiday {
    background: var(--surface-soft);
}

.cal-day.holiday {
    background: var(--danger-bg);
}

.cal-day.outside {
    opacity: 0.38;
    background: transparent;
}

/* 오늘 강조: 기존 1px 테두리 + 1px box-shadow 링을 border + outline으로 대체(레이아웃 변화 없음). */
.cal-day.today {
    border-color: var(--accent);
    outline: 1px solid var(--accent);
}

.cal-day-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-1);
    min-width: 0;
}

.cal-day-num {
    font-size: var(--fs-13);
    font-weight: var(--fw-bold);
    color: var(--text-strong);
    line-height: 1;
}

.cal-day.weekend .cal-day-num,
.cal-day.outside .cal-day-num {
    color: var(--text);
}

.cal-day.holiday .cal-day-num,
.cal-holiday {
    color: var(--danger-fg);
}

.cal-holiday {
    font-size: 10px;
    font-weight: var(--fw-semibold);
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
    word-break: keep-all;
}

.cal-day.today .cal-day-num {
    color: var(--accent);
}

.cal-entries {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
}

.cal-chip {
    display: block;
    width: 100%;
    text-align: left;
    border: none;
    border-radius: var(--radius-sm);
    padding: 3px var(--space-2);
    font: inherit;
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
    background: transparent;
    color: var(--text-muted);
    cursor: default;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.cal-chip.submitted {
    background: var(--success-bg);
    color: var(--success-fg);
    cursor: pointer;
}

.cal-chip.submitted:hover {
    background: var(--success-border);
}

.cal-chip.missed {
    background: var(--surface-soft);
    color: var(--text);
}

.cal-chip:disabled {
    cursor: default;
}

.tooltip {
    position: fixed;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text-strong);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-sm);
    font-size: var(--fs-12);
    white-space: nowrap;
    z-index: 100;
    pointer-events: none;
    transform: translate(-50%, -50%);
}

.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
    transition:
        opacity var(--dur-fast) var(--ease),
        transform var(--dur-fast) var(--ease);
}

.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
    opacity: 0;
    transform: translate(-50%, -60%) scale(0.9);
}

@media (max-width: 860px) {
    .cal-day {
        min-height: 96px;
        padding: var(--space-2);
    }

    .cal-chip {
        font-size: 10px;
        padding: 2px var(--space-1);
    }
}
</style>
