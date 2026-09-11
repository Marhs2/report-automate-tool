<script setup>
import { onMounted, ref, computed } from "vue";
import useAPI from "../composables/useApi";
import {
    CheckCircle2,
    CircleDot,
    AlertTriangle,
    MessageSquare,
    ArrowRightCircle,
    Search,
} from "lucide-vue-next";
import { useRouter } from "vue-router";

const route = useRouter();

const { GetReports, deleteReport } = useAPI();

const reports = ref([]);
const isLoading = ref(false);
const filterMember = ref("");
const filterProject = ref("");
const filterDateFrom = ref("");
const filterDateEnd = ref("");

const getReports = async () => {
    isLoading.value = true;
    try {
        const response = await GetReports();
        reports.value = response;
    } catch (error) {
        console.error("Error fetching reports:", error);
    } finally {
        isLoading.value = false;
    }
};

const deleteProjectReport = async (reportId) => {
    if (!window.confirm("이 보고서를 삭제할까요?")) return;
    try {
        await deleteReport(reportId);
        getReports();
        alert("삭제완료");
    } catch (error) {
        console.error("Error deleting report:", error);
        alert("삭제실패");
    }
};

const filteredReports = computed(() => {
    return reports.value.filter((report) => {
        const reportDate = report.report_date ?? "";
        const matchFrom =
            !filterDateFrom.value || reportDate >= filterDateFrom.value;
        const matchEnd =
            !filterDateEnd.value || reportDate <= filterDateEnd.value;

        const matchMember =
            filterMember.value === "" ||
            String(report.member_name).includes(filterMember.value);
        return matchFrom && matchEnd && matchMember;
    });
});

const toParsed = (parsedJson) => {
    if (!parsedJson) return null;
    if (typeof parsedJson === "string") {
        try {
            return JSON.parse(parsedJson);
        } catch {
            return null;
        }
    }
    return parsedJson;
};

const matchesProjectFilter = (parsedJson) => {
    if (filterProject.value === "") return true;
    const parsed = toParsed(parsedJson);
    if (!parsed) return false;
    return (parsed.projects ?? []).some((p) =>
        p.projectName?.includes(filterProject.value),
    );
};

const filteredReportsByProject = computed(() => {
    return filteredReports.value.filter((report) =>
        matchesProjectFilter(report.parsed_json),
    );
});

const reportDetail = (report) => {
    route.push(`/report/${report}`);
};

const itemText = (value) =>
    value && typeof value === "object"
        ? (value.content ?? "")
        : String(value ?? "");

const isUnresolved = (value) =>
    value && typeof value === "object" ? value.status !== "해결" : false;

const projectsOf = (report) => toParsed(report.parsed_json)?.projects ?? [];

const formatDate = (value) => {
    if (!value) return "-";
    const [y, m, d] = String(value).split("-");
    if (!y || !m || !d) return value;
    return `${y}.${m}.${d}`;
};

const hasItems = (list) => Array.isArray(list) && list.length > 0;

const visibleSections = (item) => {
    const sections = [
        {
            key: "completed",
            label: "완료된 업무",
            tone: "tone-completed",
            icon: CheckCircle2,
            items: item.completedTasks,
        },
        {
            key: "progress",
            label: "진행 중인 업무",
            tone: "tone-in-progress",
            icon: CircleDot,
            items: item.inProgressTasks,
        },
        {
            key: "issues",
            label: "이슈",
            tone: "tone-issues",
            icon: AlertTriangle,
            items: item.issues,
        },
        {
            key: "requests",
            label: "요청사항",
            tone: "tone-request",
            icon: MessageSquare,
            items: item.requests,
        },
        {
            key: "plans",
            label: "다음 계획",
            tone: "tone-next-plans",
            icon: ArrowRightCircle,
            items: item.nextPlans,
        },
    ];
    return sections.filter((section) => hasItems(section.items));
};

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
            <span class="count-chip">
                {{ filteredReportsByProject.length }}건
            </span>
        </div>

        <div class="filter-card">
            <div class="field">
                <label for="filterDateFrom">시작일</label>
                <input
                    type="date"
                    v-model="filterDateFrom"
                    id="filterDateFrom"
                    class="input"
                />
            </div>
            <div class="field">
                <label for="filterDateEnd">종료일</label>
                <input
                    type="date"
                    v-model="filterDateEnd"
                    id="filterDateEnd"
                    class="input"
                />
            </div>
            <div class="field">
                <label for="filterMember">작성자</label>
                <input
                    id="filterMember"
                    type="text"
                    placeholder="이름 검색"
                    v-model="filterMember"
                    class="input"
                />
            </div>
            <div class="field">
                <label for="filterProject">프로젝트</label>
                <input
                    id="filterProject"
                    type="text"
                    placeholder="프로젝트명 검색"
                    v-model="filterProject"
                    class="input"
                />
            </div>
        </div>

        <div v-if="isLoading" class="empty-state">보고서를 불러오는 중...</div>
        <div
            v-else-if="filteredReportsByProject.length === 0"
            class="empty-state"
        >
            <Search :size="20" />
            <p>조건에 맞는 보고서가 없습니다</p>
        </div>
        <div v-else class="reports-container">
            <article
                v-for="report in filteredReportsByProject"
                :key="report.id"
                class="card report-item"
            >
                <header class="report-header">
                    <div class="report-identity">
                        <span class="avatar">{{
                            String(report.member_name || "?").slice(0, 1)
                        }}</span>
                        <div>
                            <h3 class="report-name">{{ report.member_name }}</h3>
                            <p class="report-sub">
                                {{ formatDate(report.report_date) }}
                                · 프로젝트 {{ projectsOf(report).length }}개
                            </p>
                        </div>
                    </div>
                    <div class="report-actions">
                        <button
                            class="btn btn-primary"
                            v-on:click="() => reportDetail(report.id)"
                        >
                            자세히 보기
                        </button>
                        <button
                            class="btn btn-danger"
                            v-on:click="() => deleteProjectReport(report.id)"
                        >
                            삭제
                        </button>
                    </div>
                </header>

                <div class="projects-list">
                    <section
                        v-for="(item, index) in projectsOf(report)"
                        :key="index"
                        class="project-block"
                    >
                        <div class="project-name">
                            <span class="project-name-value">{{
                                item.projectName
                            }}</span>
                            <span
                                v-if="visibleSections(item).length === 0"
                                class="empty-chip"
                                >내용 없음</span
                            >
                        </div>

                        <div class="detail-list">
                            <div
                                v-for="section in visibleSections(item)"
                                :key="section.key"
                                class="detail-row"
                                :class="section.tone"
                            >
                                <div class="detail-label">
                                    <component :is="section.icon" :size="15" />
                                    <span>{{ section.label }}</span>
                                </div>
                                <div class="detail-content">
                                    <ul>
                                        <li
                                            v-for="(entry, entryIndex) in section.items"
                                            :key="entryIndex"
                                        >
                                            {{ itemText(entry) }}
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </section>
                </div>
            </article>
        </div>
    </div>
</template>

<style scoped>
.count-chip {
    display: inline-flex;
    align-items: center;
    height: 32px;
    padding: 0 12px;
    border-radius: 999px;
    background: var(--accent-bg);
    color: var(--accent);
    font-size: 13px;
    font-weight: 700;
}

.filter-card {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 22px;
    padding: 16px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
}

.reports-container {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.report-item {
    padding: 0;
    overflow: hidden;
}

.report-item:hover {
    border-color: var(--accent-border);
    box-shadow: var(--shadow-raised);
}

.report-header .btn {
    white-space: nowrap;
}

.report-header {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
}

.report-identity {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
}

.avatar {
    width: 38px;
    height: 38px;
    border-radius: 12px;
    background: var(--bg-soft);
    color: var(--text-h);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    flex-shrink: 0;
}

.report-name {
    margin: 0;
    font-size: 16px;
}

.report-sub {
    margin-top: 2px;
    font-size: 12px;
    color: var(--text);
}

.report-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
}

.projects-list {
    padding: 8px 20px 16px;
    display: grid;
    gap: 10px;
}

.project-block {
    padding: 14px 16px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--bg);
}

.project-name {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}

.project-name-value {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-h);
}

.empty-chip {
    font-size: 11px;
    color: var(--text);
    opacity: 0.7;
}

.detail-list {
    display: flex;
    flex-direction: column;
}

.detail-row {
    display: flex;
    gap: 16px;
    padding: 10px 0 2px;
}

.detail-label {
    flex: 0 0 132px;
    display: flex;
    align-items: flex-start;
    gap: 7px;
    font-size: 13px;
    font-weight: 650;
    color: var(--text-h);
    padding-top: 1px;
}

.detail-label svg {
    flex-shrink: 0;
    margin-top: 2px;
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
    padding-left: 16px;
    font-size: 13px;
    line-height: 1.65;
    color: var(--text);
}

.detail-content li {
    list-style: disc;
}

.badge-unresolved {
    display: inline-block;
    margin-left: 6px;
    padding: 1px 6px;
    border-radius: 999px;
    border: 1px solid var(--danger);
    color: var(--danger);
    font-size: 11px;
    font-weight: 600;
    vertical-align: middle;
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
}

@media (max-width: 860px) {
    .filter-card {
        grid-template-columns: 1fr 1fr;
    }
    .detail-row {
        flex-direction: column;
        gap: 6px;
    }
    .detail-label {
        flex: none;
    }
}
</style>
