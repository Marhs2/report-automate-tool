<script setup>
import { onMounted, ref, computed } from "vue";
import useAPI from "../composables/useApi";
import { Search, Trash2 } from "lucide-vue-next";
import { useRouter } from "vue-router";
import { useToast } from "../composables/useToast";

const router = useRouter();
const { success: toastSuccess, error: toastError } = useToast();
const { GetReports, deleteReport } = useAPI();

const reports = ref([]);
const isLoading = ref(false);
const filterMember = ref("");
const filterProject = ref("");
const filterDateFrom = ref("");
const filterDateEnd = ref("");

const formatLocalDate = (value) => {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
};

const getReports = async () => {
    isLoading.value = true;
    try {
        const response = await GetReports();
        reports.value = response;
    } catch (error) {
        console.error("Error fetching reports:", error);
        toastError("보고서를 불러오지 못했습니다.");
    } finally {
        isLoading.value = false;
    }
};

const deleteProjectReport = async (reportId, event) => {
    event?.stopPropagation();
    event?.preventDefault();
    if (!window.confirm("이 보고서를 삭제할까요?")) return;
    try {
        await deleteReport(reportId);
        await getReports();
        toastSuccess("보고서를 삭제했습니다.");
    } catch (error) {
        console.error("Error deleting report:", error);
        toastError("삭제에 실패했습니다.");
    }
};

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

const projectsOf = (report) => toParsed(report.parsed_json)?.projects ?? [];

const matchesProjectFilter = (parsedJson) => {
    if (filterProject.value === "") return true;
    const parsed = toParsed(parsedJson);
    if (!parsed) return false;
    return (parsed.projects ?? []).some((p) =>
        p.projectName?.includes(filterProject.value),
    );
};

const filteredReportsByProject = computed(() => {
    return reports.value.filter((report) => {
        const reportDate = report.report_date ?? "";
        const matchFrom =
            !filterDateFrom.value || reportDate >= filterDateFrom.value;
        const matchEnd =
            !filterDateEnd.value || reportDate <= filterDateEnd.value;
        const matchMember =
            filterMember.value === "" ||
            String(report.member_name).includes(filterMember.value);
        return (
            matchFrom &&
            matchEnd &&
            matchMember &&
            matchesProjectFilter(report.parsed_json)
        );
    });
});

const memberOptions = computed(() =>
    [...new Set(reports.value.map((report) => report.member_name).filter(Boolean))].sort(),
);

const projectOptions = computed(() => {
    const names = new Set();
    for (const report of reports.value) {
        for (const project of projectsOf(report)) {
            if (project.projectName) names.add(project.projectName);
        }
    }
    return [...names].sort();
});

const hasActiveFilter = computed(
    () =>
        Boolean(filterMember.value) ||
        Boolean(filterProject.value) ||
        Boolean(filterDateFrom.value) ||
        Boolean(filterDateEnd.value),
);

const isUnresolved = (value) =>
    value && typeof value === "object" ? value.status !== "해결" : false;

const projectNamesOf = (report) =>
    projectsOf(report)
        .map((project) => project.projectName)
        .filter(Boolean);

const unresolvedIssueCount = (report) =>
    projectsOf(report).reduce((count, project) => {
        const issues = Array.isArray(project.issues) ? project.issues : [];
        return count + issues.filter(isUnresolved).length;
    }, 0);

const openDetail = (reportId) => {
    router.push(`/report/${reportId}`);
};

const onCardKeydown = (event, reportId) => {
    if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDetail(reportId);
    }
};

const formatDate = (value) => {
    if (!value) return "-";
    const [y, m, d] = String(value).split("-");
    if (!y || !m || !d) return value;
    return `${y}.${m}.${d}`;
};

const setPresetToday = () => {
    const today = formatLocalDate(new Date());
    filterDateFrom.value = today;
    filterDateEnd.value = today;
};

const setPresetThisWeek = () => {
    const now = new Date();
    const day = now.getDay();
    const monday = new Date(now);
    monday.setDate(now.getDate() - (day === 0 ? 6 : day - 1));
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    filterDateFrom.value = formatLocalDate(monday);
    filterDateEnd.value = formatLocalDate(sunday);
};

const clearFilters = () => {
    filterMember.value = "";
    filterProject.value = "";
    filterDateFrom.value = "";
    filterDateEnd.value = "";
};

onMounted(() => {
    document.title = "일일보고";
    getReports();
});
</script>

<template>
    <div class="page">
        <div class="page-header">
            <div>
                <h1>일일보고</h1>
                <p class="page-subtitle">
                    제출된 보고서를 날짜, 작성자, 프로젝트로 조회합니다
                </p>
            </div>
            <span class="count-chip">
                {{ filteredReportsByProject.length }}건
            </span>
        </div>

        <div class="filter-presets">
            <button type="button" class="btn btn-small" @click="setPresetToday">
                오늘
            </button>
            <button
                type="button"
                class="btn btn-small"
                @click="setPresetThisWeek"
            >
                이번 주
            </button>
            <button
                type="button"
                class="btn btn-small"
                :disabled="!hasActiveFilter"
                @click="clearFilters"
            >
                초기화
            </button>
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
                    list="member-options"
                    placeholder="이름 검색"
                    v-model="filterMember"
                    class="input"
                    autocomplete="off"
                />
                <datalist id="member-options">
                    <option
                        v-for="name in memberOptions"
                        :key="name"
                        :value="name"
                    />
                </datalist>
            </div>
            <div class="field">
                <label for="filterProject">프로젝트</label>
                <input
                    id="filterProject"
                    type="text"
                    list="project-options"
                    placeholder="프로젝트명 검색"
                    v-model="filterProject"
                    class="input"
                    autocomplete="off"
                />
                <datalist id="project-options">
                    <option
                        v-for="name in projectOptions"
                        :key="name"
                        :value="name"
                    />
                </datalist>
            </div>
        </div>

        <div v-if="isLoading" class="empty-state">보고서를 불러오는 중...</div>
        <div
            v-else-if="filteredReportsByProject.length === 0"
            class="empty-state"
        >
            <Search :size="20" />
            <p>조건에 맞는 보고서가 없습니다</p>
            <button
                v-if="hasActiveFilter"
                type="button"
                class="btn"
                @click="clearFilters"
            >
                필터 초기화
            </button>
        </div>
        <div v-else class="reports-container">
            <article
                v-for="report in filteredReportsByProject"
                :key="report.id"
                class="card report-item"
                tabindex="0"
                @click="openDetail(report.id)"
                @keydown="onCardKeydown($event, report.id)"
            >
                <header class="report-header">
                    <div class="report-identity">
                        <span class="avatar">{{
                            String(report.member_name || "?").slice(0, 1)
                        }}</span>
                        <div class="report-copy">
                            <h3 class="report-name">{{ report.member_name }}</h3>
                            <p class="report-sub">
                                {{ formatDate(report.report_date) }}
                            </p>
                            <div class="report-meta">
                                <span
                                    v-for="name in projectNamesOf(report)"
                                    :key="name"
                                    class="meta-chip"
                                >
                                    {{ name }}
                                </span>
                                <span
                                    v-if="unresolvedIssueCount(report) > 0"
                                    class="meta-chip issue-chip"
                                >
                                    이슈 {{ unresolvedIssueCount(report) }}
                                </span>
                                <span
                                    v-else-if="projectNamesOf(report).length === 0"
                                    class="meta-chip"
                                >
                                    내용 없음
                                </span>
                            </div>
                        </div>
                    </div>
                    <div class="report-actions">
                        <button
                            type="button"
                            class="btn btn-danger btn-icon"
                            aria-label="보고서 삭제"
                            @click="deleteProjectReport(report.id, $event)"
                        >
                            <Trash2 :size="15" />
                        </button>
                    </div>
                </header>
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

.filter-presets {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;
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
    gap: 10px;
}

.report-item {
    padding: 0;
    overflow: hidden;
    cursor: pointer;
}

.report-item:hover {
    border-color: var(--accent-border);
    box-shadow: var(--shadow-raised);
}

.report-item:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
}

.report-header {
    padding: 16px 20px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 12px;
}

.report-identity {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    min-width: 0;
}

.report-copy {
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

.report-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}

.meta-chip {
    display: inline-flex;
    align-items: center;
    max-width: 220px;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--bg-soft);
    color: var(--text-h);
    font-size: 12px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.issue-chip {
    background: var(--danger-bg);
    color: var(--danger);
}

.report-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
}

.btn-icon {
    padding: 8px;
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
}
</style>
