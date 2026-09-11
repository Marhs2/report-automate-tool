<script setup>
import { onMounted, ref, reactive, computed, watch } from "vue";
import { useRouter } from "vue-router";
import useApi from "../composables/useApi";

const router = useRouter();
const { GetUserActivities, GetReports } = useApi();

const props = defineProps({
    startDate: { type: String, default: "" },
    endDate: { type: String, default: "" },
    embedded: { type: Boolean, default: false },
});

const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

const userActivities = ref([]);

const currentDate = new Date();
const selectedYear = ref(currentDate.getFullYear());
const selectedMonth = ref(currentDate.getMonth() + 1);
const weekDays = ref([]);

const tooltip = reactive({
    visible: false,
    x: 0,
    y: 0,
    content: "",
});

let hideTimer = null;

const parseDate = (dateStr) => new Date(`${dateStr}T00:00:00`);

const startOfToday = () => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return today;
};

const getWeekDays = () => {
    const now = new Date();
    const day = now.getDay();
    const diffToMonday = now.getDate() - (day === 0 ? 7 : day) + 1;
    const monday = new Date(now.setDate(diffToMonday));
    const formatDate = (d) => {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    };
    const days = [];
    for (let i = 0; i < 5; i++) {
        const d = new Date(monday);
        d.setDate(monday.getDate() + i);
        days.push(formatDate(d));
    }
    return days;
};

function metaFor(dateStr) {
    const date = parseDate(dateStr);
    const weekDay = date.getDay();
    const today = startOfToday();
    return {
        date: dateStr,
        day: date.getDate(),
        weekLabel: WEEKDAY_LABELS[weekDay],
        isWeekend: weekDay === 0 || weekDay === 6,
        isToday: date.getTime() === today.getTime(),
        isFuture: date.getTime() > today.getTime(),
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
    if (meta.isFuture) return "예정";
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
            const reports = await GetReports();
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

async function fetchUserActivities() {
    const activities = await GetUserActivities(
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
    weekDays.value = getWeekDays();
    fetchUserActivities();
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

const totalCountOf = (activity) =>
    activity.total_count ??
    activity.activities.reduce((total, item) => total + (item.count || 0), 0);

const orderedActivities = computed(() =>
    userActivities.value.map((activity) => ({
        ...activity,
        activities: [...(activity.activities || [])].sort((left, right) =>
            left.report_date.localeCompare(right.report_date),
        ),
    })),
);

const hasFutureDates = computed(() => dateMeta.value.some((item) => item.isFuture));
const hasToday = computed(() => dateMeta.value.some((item) => item.isToday));

const displayDates = computed(
    () =>
        orderedActivities.value[0]?.activities.map(
            (item) => item.report_date,
        ) || [],
);

const dateMeta = computed(() => displayDates.value.map(metaFor));

const weekdayCount = computed(
    () => dateMeta.value.filter((item) => !item.isWeekend).length,
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
    <div :class="embedded ? 'activity-section' : 'page'">
        <div class="page-header">
            <div>
                <h1>
                    {{ periodLabel }}
                </h1>
                <p class="page-subtitle">
                    팀원별 보고서 제출 현황을 한눈에 확인하세요
                </p>
            </div>
        </div>

        <div class="view-controls">
            <div v-if="!embedded" class="month-nav">
                <button
                    class="btn btn-small"
                    aria-label="이전 달"
                    @click="prevMonth"
                >
                    &lt;
                </button>
                <span class="current-period"
                    >{{ selectedYear }}년 {{ selectedMonth }}월</span
                >
                <button
                    class="btn btn-small"
                    aria-label="다음 달"
                    @click="nextMonth"
                >
                    &gt;
                </button>
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
                <span v-if="hasToday" class="legend-item">
                    <span class="swatch today"></span> 오늘
                </span>
                <span v-if="hasFutureDates" class="legend-item">
                    <span class="swatch future"></span> 예정
                </span>
            </div>
        </div>

        <div v-if="orderedActivities.length === 0" class="empty-state">
            표시할 활동 기록이 없습니다
        </div>
        <div
            v-else
            class="card activity-card"
            :style="{ '--day-count': Math.max(displayDates.length, 1) }"
        >
            <div class="activity-date-header">
                <span class="activity-name-cell activity-date-spacer"
                    >팀원</span
                >
                <span
                    v-for="meta in dateMeta"
                    :key="meta.date"
                    class="date-head"
                    :class="{
                        weekend: meta.isWeekend,
                        today: meta.isToday,
                    }"
                >
                    <span class="date-weekday">{{ meta.weekLabel }}</span>
                    <span class="date-day">{{ meta.day }}</span>
                </span>
            </div>
            <div
                v-for="activity in orderedActivities"
                :key="activity.member_id"
                class="activity-row"
            >
                <div class="activity-name-cell">
                    <h4 class="activity-name">{{ activity.name }}</h4>
                    <div class="activity-meta">
                        <span class="activity-total"
                            >{{ progressOf(activity).submitted }}/{{ progressOf(activity).total }} 평일</span
                        >
                        <div
                            class="progress-track"
                            :title="`${progressOf(activity).submitted}/${progressOf(activity).total} 평일`"
                        >
                            <span
                                class="progress-fill"
                                :style="{
                                    width: progressOf(activity).pct + '%',
                                }"
                            ></span>
                        </div>
                    </div>
                </div>
                <div
                    v-for="item in activity.activities"
                    :key="item.report_date"
                    class="log"
                    :class="{
                        committed: item.count > 0,
                        weekend: metaFor(item.report_date).isWeekend,
                        today: metaFor(item.report_date).isToday,
                        future: metaFor(item.report_date).isFuture,
                        clickable: canOpenCell(item),
                    }"
                    role="button"
                    :tabindex="canOpenCell(item) ? 0 : -1"
                    :aria-label="cellLabel(activity.name, item)"
                    @click="openCell(activity, item)"
                    @keydown.enter.prevent="openCell(activity, item)"
                    @keydown.space.prevent="openCell(activity, item)"
                    @mouseenter="showTooltip($event, activity.name, item)"
                    @mousemove="moveTooltip"
                    @mouseleave="hideTooltip"
                ></div>
            </div>
        </div>

        <transition name="tooltip-fade">
            <div
                v-if="tooltip.visible"
                class="tooltip"
                :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
            >
                {{ tooltip.content }}
            </div>
        </transition>
    </div>
</template>

<style scoped>
.activity-section {
    margin-bottom: 32px;
}

.view-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}

.month-nav {
    display: flex;
    align-items: center;
    gap: 8px;
}

.current-period {
    font-weight: 600;
    color: var(--text-h);
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

.swatch.today {
    box-shadow: 0 0 0 2px var(--accent);
    background: color-mix(in srgb, var(--text) 18%, transparent);
}

.activity-card {
    overflow-x: auto;
    padding: 16px;
}

.activity-date-header,
.activity-row {
    display: grid;
    grid-template-columns: 148px repeat(var(--day-count), minmax(18px, 1fr));
    column-gap: 4px;
    align-items: center;
}

.activity-date-header {
    margin-bottom: 8px;
    position: sticky;
    top: 0;
    z-index: 2;
}

.date-head {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    color: var(--text);
    min-width: 0;
}

.date-weekday {
    font-size: 9px;
    font-weight: 500;
    letter-spacing: 0;
    opacity: 0.7;
}

.date-day {
    font-size: 11px;
    font-weight: 700;
    line-height: 1.1;
}

.date-head.weekend {
    color: color-mix(in srgb, var(--text) 70%, transparent);
}

.date-head.today {
    color: var(--accent);
}

.activity-row {
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
}

.activity-row:last-child {
    border-bottom: none;
    padding-bottom: 0;
}

.activity-name-cell {
    position: sticky;
    left: 0;
    z-index: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
    padding-right: 10px;
    background: var(--bg);
}

.activity-date-spacer {
    font-size: 11px;
    font-weight: 600;
    color: var(--text);
}

.activity-name {
    min-width: 0;
    margin: 0;
    color: var(--text-h);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.activity-meta {
    display: flex;
    align-items: center;
    gap: 6px;
}

.activity-total {
    color: var(--text);
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
}

.progress-track {
    flex: 1;
    height: 4px;
    border-radius: 99px;
    background: var(--border);
    overflow: hidden;
    min-width: 36px;
}

.progress-fill {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: var(--success);
}

.log {
    width: 100%;
    aspect-ratio: 1;
    max-height: 22px;
    justify-self: center;
    border-radius: 4px;
    background: color-mix(in srgb, var(--text) 16%, transparent);
    cursor: pointer;
    transition:
        transform 0.12s ease,
        background 0.12s ease,
        opacity 0.12s ease;
}

.log.weekend {
    background: color-mix(in srgb, var(--text) 7%, transparent);
}

.log.committed {
    background: var(--success);
}

.log.future:not(.committed) {
    opacity: 0.28;
    cursor: default;
}

.log.today {
    box-shadow: inset 0 0 0 1.5px var(--accent);
}

.log:hover {
    transform: scale(1.18);
}

/* Tooltip */
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
</style>
