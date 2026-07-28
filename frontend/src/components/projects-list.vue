<script setup>
import { onMounted, ref, computed } from "vue";
import useAPI from "../composables/useApi";
import {
    CheckCircle2,
    CircleDot,
    AlertTriangle,
    MessageSquare,
    ArrowRightCircle,
} from "lucide-vue-next";

const { GetReports } = useAPI();

const reports = ref([]);
const isLoading = ref(false);
const filterDate = ref("");
const filterMember = ref("");
const filterProject = ref("");
const filterDateFrom = ref("");
const filterDateTo = ref("");

const sections = [
    {
        key: "completedTasks",
        label: "완료된 업무",
        icon: CheckCircle2,
        tone: "completed",
    },
    {
        key: "inProgressTasks",
        label: "진행 중인 업무",
        icon: CircleDot,
        tone: "in-progress",
    },
    { key: "issues", label: "이슈", icon: AlertTriangle, tone: "issues" },
    {
        key: "requests",
        label: "요청사항",
        icon: MessageSquare,
        tone: "request",
    },
    {
        key: "nextPlans",
        label: "다음 계획",
        icon: ArrowRightCircle,
        tone: "next-plans",
    },
];

const getReports = async () => {
    isLoading.value = true;
    try {
        const response = await GetReports();
        reports.value = response;
        console.log("Reports:", response);
    } catch (error) {
        console.error("Error fetching reports:", error);
    } finally {
        isLoading.value = false;
        console.log(isLoading.value);
    }
};

const filteredReports = computed(() => {
    return reports.value.filter((report) => {
        const matchDate =
            filterDate.value === "" ||
            report.report_date?.includes(filterDate.value);
        const matchRange =
            (!filterDateFrom.value && !filterDateTo.value) ||
            (filterDateFrom.value &&
                report.report_date >= filterDateFrom.value &&
                filterDateTo.value &&
                report.report_date <= filterDateTo.value);
        const matchMember =
            filterMember.value === "" ||
            String(report.member_id).includes(filterMember.value);
        return (matchDate || matchRange) && matchMember;
    });
});

const matchesProjectFilter = (parsedJson) => {
    if (filterProject.value === "") return true;
    let parsed;
    try {
        parsed = JSON.parse(parsedJson);
    } catch {
        return false;
    }
    return (parsed.projects ?? []).some((p) =>
        p.projectName?.includes(filterProject.value),
    );
};

const filteredReportsByProject = computed(() => {
    return filteredReports.value.filter((report) =>
        matchesProjectFilter(report.parsed_json),
    );
});

onMounted(() => {
    getReports();
});
</script>

<template>
    <div class="page">
        <div class="page-header">
            <div>
                <h1>프로젝트 목록</h1>
                <p class="page-subtitle">
                    제출된 보고서를 날짜, 작성자, 프로젝트로 조회합니다
                </p>
            </div>
        </div>

        <div class="toolbar">
            <input
                type="date"
                v-model="filterDateFrom"
                class="input filter-input"
                placeholder="시작일"
            />
            <input
                type="date"
                v-model="filterDateTo"
                class="input filter-input"
                placeholder="종료일"
            />
            <input
                type="text"
                placeholder="사람별로"
                v-model="filterMember"
                class="input filter-input"
            />
            <input
                type="text"
                placeholder="프로젝트"
                v-model="filterProject"
                class="input filter-input"
            />
        </div>

        <div v-if="isLoading" class="empty-state">Loading reports...</div>
        <div
            v-else-if="filteredReportsByProject.length === 0"
            class="empty-state"
        >
            조건에 맞는 보고서가 없습니다
        </div>
        <div v-else class="reports-container">
            <div
                v-for="report in filteredReportsByProject"
                :key="report.id"
                class="card report-item"
            >
                <div class="report-header">
                    <h3 class="report-id">Report ID: {{ report.id }}</h3>
                    <div class="report-meta">
                        <span class="meta-item"
                            ><strong>Member ID:</strong>
                            {{ report.member_id }}</span
                        >
                        <span class="meta-item"
                            ><strong>Report Date:</strong>
                            {{ report.report_date }}</span
                        >
                    </div>
                </div>
                <div class="projects-list">
                    <div
                        v-for="(item, index) in report.parsed_json.projects"
                        :key="index"
                        class="project-block"
                    >
                        <div class="project-name">
                            <span class="project-name-label">Project</span>
                            <span class="project-name-value">{{
                                item.projectName
                            }}</span>
                        </div>

                        <div class="detail-list">
                            <div
                                v-for="section in sections"
                                :key="section.key"
                                class="detail-row"
                                :class="'tone-' + section.tone"
                            >
                                <div class="detail-label">
                                    <component :is="section.icon" :size="15" />
                                    <span>{{ section.label }}</span>
                                </div>
                                <div class="detail-content">
                                    <ul
                                        v-if="
                                            item[section.key] &&
                                            item[section.key].length > 0
                                        "
                                    >
                                        <li
                                            v-for="(task, idx) in item[
                                                section.key
                                            ]"
                                            :key="idx"
                                        >
                                            {{ task }}
                                        </li>
                                    </ul>
                                    <p v-else class="empty-msg">해당 없음</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.filter-input {
    width: auto;
    min-width: 160px;
}

.reports-container {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.report-item {
    padding: 0;
    overflow: hidden;
}

.report-header {
    background: var(--bg-soft);
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
}

.report-id {
    margin: 0;
    font-size: 15px;
    color: var(--accent);
}

.report-meta {
    display: flex;
    align-items: center;
    gap: 20px;
    font-size: 13px;
    color: var(--text);
}

.projects-list {
    padding: 4px 20px 20px;
}

.project-block {
    padding: 20px 0;
    border-bottom: 1px solid var(--border);
}

.project-block:last-child {
    border-bottom: none;
    padding-bottom: 4px;
}

.project-name {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 14px;
}

.project-name-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text);
    opacity: 0.7;
}

.project-name-value {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-h);
}

.detail-list {
    display: flex;
    flex-direction: column;
}

.detail-row {
    display: flex;
    gap: 16px;
    padding: 10px 0;
    border-top: 1px solid var(--border);
}

.detail-row:first-child {
    border-top: none;
}

.detail-label {
    flex: 0 0 150px;
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-h);
}

.detail-label svg {
    flex-shrink: 0;
}

.tone-completed .detail-label svg {
    color: var(--success);
}
.tone-in-progress .detail-label svg {
    color: var(--accent);
}
.tone-issues .detail-label svg {
    color: var(--danger);
}
.tone-request .detail-label svg {
    color: var(--warning);
}
.tone-next-plans .detail-label svg {
    color: #14b8a6;
}

.detail-content {
    flex: 1;
    min-width: 0;
}

.detail-content ul {
    margin: 0;
    padding-left: 18px;
    font-size: 13px;
    line-height: 1.6;
    color: var(--text);
}

.detail-content li {
    list-style: disc;
}

.empty-msg {
    margin: 0;
    font-size: 13px;
    color: var(--text);
    font-style: italic;
    opacity: 0.6;
}
</style>
