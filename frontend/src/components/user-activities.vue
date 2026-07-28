<script setup>
import { onMounted, ref, reactive } from "vue";
import useApi from "../composables/useApi";
import { Check, Minus } from "lucide-vue-next";

const { GetUserActivities } = useApi();

const userActivities = ref([]);

const currentDate = new Date();
const selectedYear = ref(currentDate.getFullYear());
const selectedMonth = ref(currentDate.getMonth() + 1);
const viewMode = ref("month");
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
    const formatDate = (d) => d.toISOString().split("T")[0];
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
</script>

<template>
    <div class="page">
        <div class="page-header">
            <div>
                <h1>
                    {{ currentDate.getFullYear() }}년
                    {{ currentDate.getMonth() + 1 }}월 활동 기록
                </h1>
                <p class="page-subtitle">
                    팀원별 보고서 제출 현황을 한눈에 확인하세요
                </p>
            </div>
        </div>

        <div class="view-controls">
            <div class="month-nav">
                <button class="btn btn-small" @click="prevMonth">&lt;</button>
                <span class="current-period"
                    >{{ selectedYear }}년 {{ selectedMonth }}월</span
                >
                <button class="btn btn-small" @click="nextMonth">&gt;</button>
            </div>
            <div class="view-toggle">
                <button
                    class="btn btn-small"
                    :class="{ active: viewMode === 'month' }"
                    @click="viewMode = 'month'"
                >
                    월별
                </button>
                <button
                    class="btn btn-small"
                    :class="{ active: viewMode === 'week' }"
                    @click="viewMode = 'week'"
                >
                    주간
                </button>
            </div>
        </div>

        <div v-if="userActivities.length === 0" class="empty-state">
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
            <div class="card">
                <div
                    v-for="activity in userActivities"
                    :key="activity.report_date"
                    class="activity-row"
                >
                    <h4 class="activity-name">{{ activity.name }}</h4>
                    <div class="activity-days">
                        <div
                            v-for="item in viewMode === 'week'
                                ? activity.activities.filter((a) =>
                                      weekDays.includes(a.report_date),
                                  )
                                : activity.activities"
                            :key="item.id"
                            class="log"
                            :class="item.count > 0 ? 'committed' : ''"
                            @mouseenter="
                                showTooltip(
                                    $event,
                                    item.report_date,
                                    item.count,
                                )
                            "
                            @mousemove="moveTooltip"
                            @mouseleave="hideTooltip"
                        >
                            <Check v-if="item.count > 0" :size="10" />
                            <Minus v-else :size="10" />
                        </div>
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

.activity-row {
    display: flex;
    align-items: center;
    gap: 20px;
    padding: 12px 0;
    border-bottom: 1px solid var(--border);
}

.activity-row:last-child {
    border-bottom: none;
    padding-bottom: 0;
}

.activity-row:first-child {
    padding-top: 0;
}

.activity-name {
    flex: 0 0 40px;
    margin: 0;
    color: var(--text-h);
}

.activity-days {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
}

.log {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 4px;
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
