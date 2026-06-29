<script setup>
import { onMounted, ref } from "vue";
import useAPI from "../composables/useAPI";

const { GetReports } = useAPI();
const reports = ref([]);
const isLoading = ref(false);
const filterDate = ref("");
const filterMember = ref("");
const filterProject = ref("");

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
    }
};

const applyFilter = () => {};

onMounted(() => {
    getReports();
});
</script>

<template>
    <div class="reports-wrapper">
        <h2 class="page-title">Reports List</h2>
        <div v-if="isLoading" class="loading-state">Loading reports...</div>
        <div v-else class="reports-container">
            <div class="filter-btns">
                <input type="date" v-model="filterDate" />
                <input
                    type="text"
                    placeholder="사람별로"
                    v-model="filterMember"
                />
                <input
                    type="text"
                    placeholder="프로젝트"
                    v-model="filterProject"
                />
                <button>필터 확인</button>
            </div>
            <div v-for="report in reports" :key="report.id" class="report-item">
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
                        v-for="(item, index) in JSON.parse(report.parsed_json)
                            .projects"
                        :key="index"
                        class="project-card"
                    >
                        <div class="project-name">
                            <strong>Project Name:</strong>
                            <span>{{ item.projectName }}</span>
                        </div>

                        <div class="project-grid">
                            <div class="project-section project-completed">
                                <h4>Completed Tasks</h4>
                                <ul
                                    v-if="
                                        item.completedTasks &&
                                        item.completedTasks.length > 0
                                    "
                                >
                                    <li
                                        v-for="(
                                            task, idx
                                        ) in item.completedTasks"
                                        :key="idx"
                                    >
                                        {{ task }}
                                    </li>
                                </ul>
                                <p v-else class="empty-msg">
                                    No completed tasks
                                </p>
                            </div>

                            <div class="project-section project-in-progress">
                                <h4>In-Progress Tasks</h4>
                                <ul
                                    v-if="
                                        item.inProgressTasks &&
                                        item.inProgressTasks.length > 0
                                    "
                                >
                                    <li
                                        v-for="(
                                            task, idx
                                        ) in item.inProgressTasks"
                                        :key="idx"
                                    >
                                        {{ task }}
                                    </li>
                                </ul>
                                <p v-else class="empty-msg">
                                    No in-progress tasks
                                </p>
                            </div>

                            <div class="project-section project-issues">
                                <h4>Issues</h4>
                                <ul
                                    v-if="item.issues && item.issues.length > 0"
                                >
                                    <li
                                        v-for="(task, idx) in item.issues"
                                        :key="idx"
                                    >
                                        {{ task }}
                                    </li>
                                </ul>
                                <p v-else class="empty-msg">No issues</p>
                            </div>

                            <div class="project-section project-request">
                                <h4>Requests</h4>
                                <ul
                                    v-if="
                                        item.requests &&
                                        item.requests.length > 0
                                    "
                                >
                                    <li
                                        v-for="(task, idx) in item.requests"
                                        :key="idx"
                                    >
                                        {{ task }}
                                    </li>
                                </ul>
                                <p v-else class="empty-msg">No requests</p>
                            </div>

                            <div class="project-section project-next-plans">
                                <h4>Next Plans</h4>
                                <ul
                                    v-if="
                                        item.nextPlans &&
                                        item.nextPlans.length > 0
                                    "
                                >
                                    <li
                                        v-for="(task, idx) in item.nextPlans"
                                        :key="idx"
                                    >
                                        {{ task }}
                                    </li>
                                </ul>
                                <p v-else class="empty-msg">No next plans</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.reports-wrapper {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    font-family:
        -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial,
        sans-serif;
    color: #e2e8f0;
    background-color: #0f172a;
    min-height: 100vh;
}

.page-title {
    font-size: 24px;
    margin-bottom: 24px;
    font-weight: 700;
    border-bottom: 2px solid #334155;
    padding-bottom: 10px;
    color: #f8fafc;
}

.loading-state {
    text-align: center;
    font-size: 18px;
    color: #94a3b8;
    padding: 40px;
}

.reports-container {
    display: flex;
    flex-direction: column;
    gap: 30px;
}

.report-item {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    box-shadow:
        0 4px 6px -1px rgba(0, 0, 0, 0.2),
        0 2px 4px -1px rgba(0, 0, 0, 0.1);
    overflow: hidden;
}

.report-header {
    background-color: #1e293b;
    padding: 16px 20px;
    border-bottom: 1px solid #334155;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
}

.report-id {
    margin: 0;
    font-size: 18px;
    color: #38bdf8;
}

.report-meta {
    display: flex;
    gap: 20px;
    font-size: 14px;
    color: #94a3b8;
}

.projects-list {
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.project-card {
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 16px;
    background: #0f172a;
}

.project-name {
    font-size: 16px;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px dashed #334155;
    color: #f1f5f9;
}

.project-name strong {
    color: #94a3b8;
}

.project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
}

.project-section {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 12px;
}

.project-section h4 {
    margin-top: 0;
    margin-bottom: 10px;
    font-size: 14px;
    font-weight: 600;
    padding-bottom: 6px;
    border-bottom: 2px solid #334155;
}

/* Section specific heading colors optimized for dark mode */
.project-completed h4 {
    color: #4ade80;
    border-bottom-color: #4ade80;
}
.project-in-progress h4 {
    color: #60a5fa;
    border-bottom-color: #60a5fa;
}
.project-issues h4 {
    color: #f87171;
    border-bottom-color: #f87171;
}
.project-request h4 {
    color: #fbbf24;
    border-bottom-color: #fbbf24;
}
.project-next-plans h4 {
    color: #2dd4bf;
    border-bottom-color: #2dd4bf;
}

.project-section ul {
    margin: 0;
    padding-left: 20px;
    font-size: 13px;
    line-height: 1.5;
    color: #cbd5e1;
}

.project-section li {
    margin-bottom: 6px;
}

.empty-msg {
    margin: 0;
    font-size: 13px;
    color: #64748b;
    font-style: italic;
}
</style>
