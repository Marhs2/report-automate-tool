<script setup>
import { onMounted, ref, reactive, computed, watch } from "vue";
import { useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useToast } from "../composables/useToast";

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
    router.push(`/report/${reportId}`);
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
    <div :class="embedded ? 'activity-section' : 'page calendar-page'">
        <div v-if="!embedded" class="page-header">
            <div>
                <h1>
                    {{ periodLabel }}
                </h1>

            </div>
        </div>

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
    margin-bottom: 8px;
}

.activity-section .cal-day {
    min-height: 96px;
    padding: 6px;
}

.activity-section .cal-chip {
    font-size: 11px;
    padding: 2px 6px;
}

.activity-section .member-summary {
    margin-bottom: 10px;
}

.activity-section .view-controls {
    margin-bottom: 8px;
}

.calendar-page {
    max-width: 1200px;
}

.view-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}

.month-tools {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    min-width: 0;
}

.month-nav {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}

.current-period {
    font-weight: 600;
    color: var(--text-h);
    white-space: nowrap;
}

.month-team-select {
    height: 32px;
    width: auto;
    min-width: 108px;
    padding: 0 28px 0 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    background: var(--bg);
    color: var(--text-h);
    font: inherit;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
}

.month-team-select:hover {
    border-color: var(--text);
}

.month-team-select:focus {
    outline: none;
    border-color: var(--text-h);
}

.legend {
    display: flex;
    gap: 14px;
    font-size: 12px;
    color: var(--text);
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
}

.swatch {
    width: 10px;
    height: 10px;
    border-radius: 3px;
    display: inline-block;
}

.swatch.submitted {
    background: var(--success);
}

.swatch.missed {
    background: color-mix(in srgb, var(--text) 18%, transparent);
}

.swatch.weekend {
    background: color-mix(in srgb, var(--text) 8%, transparent);
    box-shadow: inset 0 0 0 1px var(--border);
}

.swatch.holiday {
    background: var(--danger-bg);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--danger) 35%, var(--border));
}

.swatch.today {
    box-shadow: 0 0 0 2px var(--accent);
    background: color-mix(in srgb, var(--text) 18%, transparent);
}

.member-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
    margin-bottom: 14px;
}

.summary-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--bg-elevated);
}

.summary-top {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
}

.summary-name {
    font-weight: 650;
    color: var(--text-h);
    font-size: 13px;
}

.summary-count {
    color: var(--text);
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
}

.progress-track {
    height: 4px;
    border-radius: 99px;
    background: var(--border);
    overflow: hidden;
}

.progress-fill {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: var(--success);
}

.calendar-card {
    padding: 16px;
}

.cal-weekdays {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: 6px;
    margin-bottom: 6px;
}

.cal-weekdays span {
    text-align: center;
    font-size: 12px;
    font-weight: 650;
    color: var(--text);
    padding: 6px 0;
}

.cal-weekdays .weekend {
    opacity: 0.7;
}

.cal-weeks {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.cal-week {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: 6px;
}

.cal-day {
    min-height: 128px;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 8px;
    background: var(--bg-elevated);
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.cal-day.weekend,
.cal-day.holiday {
    background: color-mix(in srgb, var(--text) 5%, var(--bg));
}

.cal-day.holiday {
    background: color-mix(in srgb, var(--danger) 6%, var(--bg-elevated));
}

.cal-day.outside {
    opacity: 0.38;
    background: transparent;
}

.cal-day.today {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
}

.cal-day-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 4px;
    min-width: 0;
}

.cal-day-num {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-h);
    line-height: 1;
}

.cal-day.weekend .cal-day-num,
.cal-day.outside .cal-day-num {
    color: var(--text);
}

.cal-day.holiday .cal-day-num,
.cal-holiday {
    color: var(--danger);
}

.cal-holiday {
    font-size: 10px;
    font-weight: 650;
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
    gap: 4px;
}

.cal-chip {
    display: block;
    width: 100%;
    text-align: left;
    border: none;
    border-radius: 6px;
    padding: 3px 6px;
    font: inherit;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
    color: color-mix(in srgb, var(--text) 55%, transparent);
    cursor: default;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.cal-chip.submitted {
    background: color-mix(in srgb, var(--success) 22%, transparent);
    color: var(--success);
    cursor: pointer;
}

.cal-chip.submitted:hover {
    background: color-mix(in srgb, var(--success) 34%, transparent);
}

.cal-chip.missed {
    background: color-mix(in srgb, var(--text) 10%, transparent);
    color: var(--text);
}

.cal-chip:disabled {
    cursor: default;
}

.tooltip {
    position: fixed;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text-h);
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    font-size: 12px;
    white-space: nowrap;
    z-index: 100;
    box-shadow: var(--shadow);
    pointer-events: none;
    transform: translate(-50%, -50%);
}

.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
    transition:
        opacity 0.15s ease,
        transform 0.15s ease;
}

.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
    opacity: 0;
    transform: translate(-50%, -60%) scale(0.9);
}

@media (max-width: 860px) {
    .cal-day {
        min-height: 96px;
        padding: 6px;
    }

    .cal-chip {
        font-size: 10px;
        padding: 2px 4px;
    }
}
</style>
