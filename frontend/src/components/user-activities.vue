<script setup>
import { onMounted, ref } from "vue";
import useApi from "../composables/useApi";
import { Check, Minus } from "lucide-vue-next";

const { GetUserActivities } = useApi();

const userActivities = ref([]);

const date = new Date();


async function fetchUserActivities() {
    const activities = await GetUserActivities(date.getFullYear(), date.getMonth() + 1);
    userActivities.value = activities;
}

onMounted(() => {
    fetchUserActivities();
});
</script>

<template>
    <div class="page">
        <div class="page-header">
            <div>
                <h1>{{ date.getFullYear() }}년 {{ date.getMonth() + 1 }}월 활동 기록</h1>
                <p class="page-subtitle">팀원별 보고서 제출 현황을 한눈에 확인하세요</p>
            </div>
        </div>

        <div v-if="userActivities.length === 0" class="empty-state">
            표시할 활동 기록이 없습니다
        </div>
        <template v-else>
            <div class="legend">
                <span class="legend-item"><Check :size="12" class="legend-icon done" /> 제출함</span>
                <span class="legend-item"><Minus :size="12" class="legend-icon none" /> 제출 안 함</span>
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
                            v-for="item in activity.activities"
                            :key="item.id"
                            class="log"
                            :class="item.count > 0 ? 'committed' : ''"
                            :title="item.count > 0 ? `제출함 (${item.count}건)` : '제출 안 함'"
                        >
                            <Check v-if="item.count > 0" :size="10" />
                            <Minus v-else :size="10" />
                        </div>
                    </div>
                </div>
            </div>
        </template>
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
    flex: 0 0 140px;
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
}

.committed {
    background-color: color-mix(in srgb, var(--success) 15%, transparent);
    border-color: var(--success);
    color: var(--success);
    opacity: 1;
}
</style>
