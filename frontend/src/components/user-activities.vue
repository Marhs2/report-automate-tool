<script setup>
import { onMounted, ref, reactive, computed, watch } from "vue";
import useApi from "../composables/useApi";
import { Check, Minus } from "lucide-vue-next";

const { GetUserActivities } = useApi();

const props = defineProps({
    startDate: { type: String, default: "" },
    endDate: { type: String, default: "" },
    embedded: { type: Boolean, default: false },
});

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

function showTooltip(e, dateStr, count) {
    clearTimeout(hideTimer);
    tooltip.content =
        count > 0
            ? `${dateStr} - 제출함 (${count}건)`
            : `${dateStr} - 제출 안 함`;
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

const orderedActivities = computed(() =>
    userActivities.value.map((activity) => ({
        ...activity,
        activities: [...(activity.activities || [])].sort((left, right) =>
            left.report_date.localeCompare(right.report_date),
        ),
    })),
);

const displayDates = computed(
    () =>
        orderedActivities.value[0]?.activities.map(
            (item) => item.report_date,
        ) || [],
);

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

        <div v-if="!embedded" class="view-controls">
            <div class="month-nav">
                <button class="btn btn-small" @click="prevMonth">&lt;</button>
                <span class="current-period"
                    >{{ selectedYear }}년 {{ selectedMonth }}월</span
                >
                <button class="btn btn-small" @click="nextMonth">&gt;</button>
            </div>
        </div>

        <div v-if="orderedActivities.length === 0" class="empty-state">
            표시할 활동 기록이 없습니다
        </div>
        <template v-else>
            <div class="legend">
                <span class="legend-item"
                    ><Check :size="12" class="legend-icon done" /> 제출함</span
                >
                <span class="legend-item"
                    ><Minus :size="12" class="legend-icon none" /> 제출 안
                    함</span
                >
            </div>
            <div
                class="card activity-card"
                :style="{ '--day-count': Math.max(displayDates.length, 1) }"
            >
                <div class="activity-date-header">
                    <span class="activity-date-spacer"></span>
                    <span v-for="date in displayDates" :key="date">
                        {{ date.slice(5).replace("-", "/") }}
                    </span>
                </div>
                <div
                    v-for="activity in orderedActivities"
                    :key="activity.member_id"
                    class="activity-row"
                >
                    <h4 class="activity-name">{{ activity.name }}</h4>
                    <div
                        v-for="item in activity.activities"
                        :key="item.report_date"
                        class="log"
                        :class="item.count > 0 ? 'committed' : ''"
                        @mouseenter="
                            showTooltip($event, item.report_date, item.count)
                        "
                        @mousemove="moveTooltip"
                        @mouseleave="hideTooltip"
                    >
                        <Check v-if="item.count > 0" :size="12" />
                        <Minus v-else :size="12" />
                    </div>
                </div>
            </div>
        </template>

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

.legend {
    display: flex;
    gap: 16px;
    margin-bottom: 12px;
    font-size: 12px;
    color: var(--text);
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 5px;
}

.legend-icon.done {
    color: var(--success);
}

.legend-icon.none {
    color: var(--text);
    opacity: 0.5;
}

.view-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
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

.view-toggle {
    display: flex;
    gap: 4px;
}

.view-toggle .btn.active {
    background: var(--accent-bg);
    border-color: var(--accent-border);
    color: var(--text-h);
}

.activity-card {
    overflow-x: auto;
}

.activity-date-header,
.activity-row {
    display: grid;
    grid-template-columns:
        84px
        repeat(var(--day-count), 32px);
    column-gap: 8px;
    justify-content: space-evenly;
    min-width: max-content;
}

.activity-row {
    align-items: center;
    padding: 16px 0;
    border-bottom: 1px solid var(--border);
    gap: 15px;
}

.activity-date-header {
    margin-bottom: 10px;
    color: var(--text);
    font-size: 11px;
    gap: 15px;
    font-weight: bold;
}

.activity-date-header span:not(.activity-date-spacer) {
    text-align: center;
    white-space: nowrap;
}

.activity-date-spacer {
    display: block;
}

.activity-row:last-child {
    border-bottom: none;
    padding-bottom: 0;
}

.activity-row:first-child {
    padding-top: 0;
}

.activity-name {
    min-width: 0;
    margin: 0;
    color: var(--text-h);
    white-space: nowrap;
}

.log {
    display: flex;
    align-items: center;
    justify-content: center;
    width: min(100%, 32px);
    height: 28px;
    justify-self: center;
    border-radius: 6px;
    border: 1.5px solid var(--border);
    background: var(--bg-soft);
    color: var(--text);
    opacity: 0.5;
    cursor: pointer;
    transition: opacity 0.15s ease;
}

.log:hover {
    opacity: 1;
}

.committed {
    background-color: color-mix(in srgb, var(--success) 15%, transparent);
    border-color: var(--success);
    color: var(--success);
    opacity: 1;
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
