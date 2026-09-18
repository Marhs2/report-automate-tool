<script setup>
import { onMounted, ref, computed } from "vue";
import { Search, Trash2 } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { useRouter } from "vue-router";
import { useDialog } from "../composables/useDialog";
import { missingOnDate } from "../lib/dayStatus";
import { missingBanner, sortByIssuesFirst } from "../lib/standupInsights";
import AppPageHeader from "./ui/AppPageHeader.vue";
import AppFilterBar from "./ui/AppFilterBar.vue";
import AppListRow from "./ui/AppListRow.vue";

const router = useRouter();
const { alert: showAlert, confirm: askConfirm } = useDialog();
const { getReports, deleteReport, getTeams, getHolidays, getUsers } = useApi();

const reports = ref([]);
const members = ref([]);
const teams = ref([]);
const holidayNames = ref({});
const isLoading = ref(false);
const filterMember = ref("");
const filterProject = ref("");
const filterDateFrom = ref("");
const filterDateEnd = ref("");
const filterTeam = ref("all");

const formatLocalDate = (value) => {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
};

const fetchHolidays = async (rows) => {
    const years = new Set([new Date().getFullYear()]);
    for (const report of rows || []) {
        const year = Number(String(report.report_date || "").slice(0, 4));
        if (year) years.add(year);
    }
    const map = {};
    await Promise.all(
        [...years].map(async (year) => {
            const rowsForYear = await getHolidays(year);
            for (const row of rowsForYear || []) {
                if (row?.date) map[row.date] = row.name;
            }
        }),
    );
    holidayNames.value = map;
};

const fetchReports = async () => {
    isLoading.value = true;
    try {
        const response = await getReports();
        reports.value = response;
        fetchHolidays(response).catch((error) => {
            console.error("Error fetching holidays:", error);
        });
    } catch (error) {
        console.error("Error fetching reports:", error);
        showAlert("보고서를 불러오지 못했습니다.");
    } finally {
        isLoading.value = false;
    }
};

const fetchTeams = async () => {
    try {
        teams.value = await getTeams();
    } catch (error) {
        console.error("Error fetching teams:", error);
        showAlert("팀을 불러오지 못했습니다.");
    }
};

const fetchMembers = async () => {
    try {
        members.value = await getUsers();
    } catch (error) {
        console.error("Error fetching users:", error);
    }
};

const deleteProjectReport = async (reportId, event) => {
    event?.stopPropagation();
    event?.preventDefault();
    if (!(await askConfirm("이 보고서를 삭제할까요?"))) return;
    try {
        await deleteReport(reportId);
        await fetchReports();
        showAlert("보고서를 삭제했습니다.");
    } catch (error) {
        console.error("Error deleting report:", error);
        showAlert("삭제에 실패했습니다.");
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

const issueCount = (report) =>
    projectsOf(report).reduce((sum, project) => {
        const issues = project?.issues;
        return sum + (Array.isArray(issues) ? issues.length : 0);
    }, 0);

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
        const matchTeam =
            filterTeam.value === "all" ||
            String(report.member_team_id) === String(filterTeam.value);
        return (
            matchFrom &&
            matchEnd &&
            matchMember &&
            matchTeam &&
            matchesProjectFilter(report.parsed_json)
        );
    });
});

const memberOptions = computed(() => {
    const source =
        filterTeam.value === "all"
            ? reports.value
            : reports.value.filter(
                  (report) =>
                      String(report.member_team_id) === String(filterTeam.value),
              );
    return [
        ...new Set(source.map((report) => report.member_name).filter(Boolean)),
    ].sort();
});

const projectOptions = computed(() => {
    const names = new Set();
    for (const report of filteredReportsByProject.value) {
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
        Boolean(filterDateEnd.value) ||
        filterTeam.value !== "all",
);

const weekRange = () => {
    const now = new Date();
    const day = now.getDay();
    const monday = new Date(now);
    monday.setDate(now.getDate() - (day === 0 ? 6 : day - 1));
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return {
        start: formatLocalDate(monday),
        end: formatLocalDate(sunday),
    };
};

const isTodayPreset = computed(() => {
    const today = formatLocalDate(new Date());
    return filterDateFrom.value === today && filterDateEnd.value === today;
});

const isWeekPreset = computed(() => {
    const { start, end } = weekRange();
    return filterDateFrom.value === start && filterDateEnd.value === end;
});

const dashboardStats = computed(() => {
    const today = formatLocalDate(new Date());
    const now = new Date();
    const day = now.getDay();
    const monday = new Date(now);
    monday.setDate(now.getDate() - (day === 0 ? 6 : day - 1));
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    const weekStart = formatLocalDate(monday);
    const weekEnd = formatLocalDate(sunday);
    const todayCount = reports.value.filter(
        (report) => report.report_date === today,
    ).length;
    const weekCount = reports.value.filter((report) => {
        const date = report.report_date ?? "";
        return date >= weekStart && date <= weekEnd;
    }).length;
    const issueReports = reports.value.filter(
        (report) => issueCount(report) > 0,
    ).length;
    return {
        today: todayCount,
        week: weekCount,
        issues: issueReports,
        total: reports.value.length,
    };
});

const projectNamesOf = (report) =>
    projectsOf(report)
        .map((project) => project.projectName)
        .filter(Boolean);

const teamNameOf = (report) => {
    const found = teams.value.find(
        (team) => String(team.id) === String(report.member_team_id),
    );
    return found?.team_name || "미지정";
};

const weekdayOf = (value) => {
    if (!value) return "";
    const [year, month, day] = String(value).split("-").map(Number);
    if (!year || !month || !day) return "";
    return ["일", "월", "화", "수", "목", "금", "토"][
        new Date(year, month - 1, day).getDay()
    ];
};

const memberRoster = computed(() => {
    const fromMembers = members.value.filter((member) => {
        if (!member?.name) return false;
        if (filterTeam.value === "all") return true;
        return String(member.team_id) === String(filterTeam.value);
    });
    if (fromMembers.length) {
        return fromMembers.map((member) => member.name);
    }
    const names = [];
    const seen = new Set();
    for (const report of filteredReportsByProject.value) {
        const name = report.member_name;
        if (!name || seen.has(name)) continue;
        seen.add(name);
        names.push(name);
    }
    return names;
});

const reportsByDate = computed(() => {
    const groups = [];
    const index = new Map();
    for (const report of filteredReportsByProject.value) {
        const date = report.report_date ?? "";
        let group = index.get(date);
        if (!group) {
            group = { date, reports: [] };
            index.set(date, group);
            groups.push(group);
        }
        group.reports.push(report);
    }
    return groups.map((group) => {
        const submitted = new Set(
            group.reports.map((report) => report.member_name),
        );
        return {
            date: group.date,
            reports: sortByIssuesFirst(group.reports, issueCount),
            issueTotal: group.reports.reduce(
                (sum, report) => sum + issueCount(report),
                0,
            ),
            missing: missingOnDate(
                group.date,
                memberRoster.value.filter((name) => !submitted.has(name)),
                holidayNames.value,
            ),
        };
    });
});

const openDetail = (reportId) => {
    router.push(`/report-result/${reportId}`);
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
    const { start, end } = weekRange();
    filterDateFrom.value = start;
    filterDateEnd.value = end;
};

const clearFilters = () => {
    filterMember.value = "";
    filterProject.value = "";
    filterDateFrom.value = "";
    filterDateEnd.value = "";
    filterTeam.value = "all";
};

const outstandingMissing = computed(() => missingBanner(reportsByDate.value));

onMounted(() => {
    document.title = "일일보고";
    fetchReports();
    fetchTeams();
    fetchMembers();
});
</script>

<template>
    <div class="page">
        <AppPageHeader subtitle="미제출과 이슈가 위에 옵니다" />

        <p v-if="outstandingMissing.length" class="missing-banner" role="status">
            아직 제출하지 않음 · {{ outstandingMissing.join(" · ") }}
        </p>

        <div class="stat-grid">
            <button type="button" class="stat-card" :class="{ 'is-active': isTodayPreset }" @click="setPresetToday">
                <span class="stat-label">오늘 제출</span>
                <strong class="stat-value">{{ dashboardStats.today }}</strong>
            </button>
            <button type="button" class="stat-card" :class="{ 'is-active': isWeekPreset }" @click="setPresetThisWeek">
                <span class="stat-label">이번 주</span>
                <strong class="stat-value">{{ dashboardStats.week }}</strong>
            </button>
            <div class="stat-card">
                <span class="stat-label">이슈 보고</span>
                <strong class="stat-value">{{ dashboardStats.issues }}</strong>
            </div>
            <div class="stat-card">
                <span class="stat-label">전체</span>
                <strong class="stat-value">{{ dashboardStats.total }}</strong>
            </div>
        </div>

        <div class="filter-presets">
            <button type="button" class="btn btn-small" :class="{ 'is-active': isTodayPreset }" @click="setPresetToday">
                오늘
            </button>
            <button type="button" class="btn btn-small" :class="{ 'is-active': isWeekPreset }" @click="setPresetThisWeek">
                이번 주
            </button>
            <button type="button" class="btn btn-small" :disabled="!hasActiveFilter" @click="clearFilters">
                초기화
            </button>
            <span v-if="!isLoading" class="list-count">{{ filteredReportsByProject.length }}건</span>
        </div>

        <AppFilterBar>
            <input
                type="date"
                v-model="filterDateFrom"
                id="filterDateFrom"
                class="input"
                aria-label="시작일"
            />
            <span class="filter-divider" aria-hidden="true"></span>
            <input
                type="date"
                v-model="filterDateEnd"
                id="filterDateEnd"
                class="input"
                aria-label="종료일"
            />
            <span class="filter-divider" aria-hidden="true"></span>
            <select
                id="filterTeam"
                v-model="filterTeam"
                class="input"
                aria-label="팀"
            >
                <option value="all">전체 팀</option>
                <option
                    v-for="team in teams"
                    :key="team.id"
                    :value="String(team.id)"
                >
                    {{ team.team_name }}
                </option>
            </select>
            <span class="filter-divider" aria-hidden="true"></span>
            <input
                id="filterMember"
                type="text"
                list="member-options"
                placeholder="이름 검색"
                v-model="filterMember"
                class="input"
                autocomplete="off"
                aria-label="작성자"
            />
            <datalist id="member-options">
                <option v-for="name in memberOptions" :key="name" :value="name" />
            </datalist>
            <span class="filter-divider" aria-hidden="true"></span>
            <input
                id="filterProject"
                type="text"
                list="project-options"
                placeholder="프로젝트명 검색"
                v-model="filterProject"
                class="input"
                autocomplete="off"
                aria-label="프로젝트"
            />
            <datalist id="project-options">
                <option v-for="name in projectOptions" :key="name" :value="name" />
            </datalist>
        </AppFilterBar>

        <div v-if="isLoading" class="empty-state">보고서를 불러오는 중...</div>
        <div v-else-if="filteredReportsByProject.length === 0" class="empty-state">
            <Search :size="20" />
            <p>조건에 맞는 보고서가 없습니다</p>
            <button v-if="hasActiveFilter" type="button" class="btn" @click="clearFilters">
                필터 초기화
            </button>
        </div>
        <div v-else class="reports-container">
            <section
                v-for="group in reportsByDate"
                :key="group.date"
                class="card date-group"
            >
                <header class="date-head">
                    <strong>
                        {{ formatDate(group.date) }}
                        <b>{{ weekdayOf(group.date) }}</b>
                    </strong>
                    <em>
                        {{ group.reports.length }}명
                        <template v-if="group.issueTotal"> · 이슈 {{ group.issueTotal }}</template>
                    </em>
                </header>
                <p v-if="group.missing.length" class="missing-row">
                    미제출 {{ group.missing.join(" · ") }}
                </p>
                <AppListRow
                    v-for="report in group.reports"
                    :key="report.id"
                    clickable
                    class="person-row"
                    tabindex="0"
                    @click="openDetail(report.id)"
                    @keydown="onCardKeydown($event, report.id)"
                >
                    <div class="report-identity">
                        <span class="avatar">{{
                            String(report.member_name || "?").slice(0, 1)
                        }}</span>
                        <div class="report-copy">
                            <h3 class="report-name">{{ report.member_name }}</h3>
                            <p class="report-sub">{{ teamNameOf(report) }}</p>
                        </div>
                    </div>
                    <template #meta>
                        <span v-for="name in projectNamesOf(report)" :key="name" class="meta-chip">
                            {{ name }}
                        </span>
                        <span v-if="issueCount(report) > 0" class="meta-chip issue-chip">
                            이슈 {{ issueCount(report) }}
                        </span>
                        <span v-else-if="projectNamesOf(report).length === 0" class="empty-copy">
                            내용 없음
                        </span>
                    </template>
                    <template #actions>
                        <button type="button" class="btn btn-danger btn-icon" aria-label="보고서 삭제"
                            @click="deleteProjectReport(report.id, $event)">
                            <Trash2 :size="15" />
                        </button>
                    </template>
                </AppListRow>
            </section>
        </div>
    </div>
</template>

<style scoped>
.stat-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--space-3);
    margin-bottom: var(--space-5);
}

.stat-card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
    padding: var(--space-5) var(--space-5) var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    text-align: left;
    cursor: default;
    font: inherit;
    color: inherit;
}

button.stat-card {
    cursor: pointer;
}

button.stat-card:hover,
.stat-card.is-active {
    border-color: var(--accent-border);
    background: var(--accent-soft);
}

.stat-label {
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
    letter-spacing: 0.88px;
    text-transform: uppercase;
    color: var(--text);
}

.stat-value {
    font-size: 28px;
    letter-spacing: -0.5px;
    line-height: 1.1;
    color: var(--text-strong);
    font-family: var(--heading);
}

.filter-presets {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
}

.filter-presets .btn.is-active {
    border-color: var(--accent-border);
    background: var(--accent-soft);
}

.list-count {
    margin-left: auto;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.filter-toolbar {
    display: flex;
    align-items: center;
    gap: 0;
    margin-bottom: var(--space-5);
    padding: var(--space-1) var(--space-2);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
}

.filter-toolbar .input {
    flex: 1;
    min-width: 0;
    height: 32px;
    padding: var(--space-1) var(--space-3);
    border: none;
    background: transparent;
    border-radius: 0;
}

.filter-toolbar .input:hover,
.filter-toolbar .input:focus,
.filter-toolbar .input:focus-visible {
    border-color: transparent;
}

.filter-divider {
    flex-shrink: 0;
    width: 1px;
    height: 16px;
    background: var(--border);
}

.reports-container {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
}

.date-group {
    padding: 0;
    overflow: hidden;
}

.date-head {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4) var(--space-2);
}

.date-head strong {
    color: var(--text-strong);
    font-size: 15px;
    font-weight: var(--fw-semibold);
    letter-spacing: -0.2px;
}

.date-head b {
    font-weight: var(--fw-semibold);
    margin-left: var(--space-1);
}

.date-head em {
    font-style: normal;
    font-size: var(--fs-12);
    margin-left: auto;
    color: var(--text);
}

.person-row:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
}

.report-identity {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
}

.report-copy {
    min-width: 0;
}

.avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--surface-soft);
    color: var(--text-strong);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    flex-shrink: 0;
}

.report-name {
    margin: 0;
    font-size: var(--fs-14);
    font-weight: var(--fw-medium);
}

.report-sub {
    margin-top: 1px;
    font-size: var(--fs-11);
    color: var(--text);
}

.report-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    min-width: 0;
}

.empty-copy {
    font-size: var(--fs-12);
    color: var(--text);
    opacity: 0.75;
}

.missing-row {
    margin: 0;
    padding: var(--space-2) var(--space-4) var(--space-3);
    font-size: var(--fs-12);
    color: var(--text);
    border-top: 1px dashed var(--border);
}

.meta-chip {
    display: inline-flex;
    align-items: center;
    max-width: 220px;
    padding: 2px var(--space-2);
    border-radius: var(--radius-pill);
    background: var(--surface-soft);
    color: var(--text-strong);
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.issue-chip {
    background: var(--danger-bg);
    color: var(--danger-fg);
}

.report-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
}

.btn-icon {
    padding: var(--space-2);
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
}

@media (max-width: 1100px) {
    .filter-toolbar {
        flex-wrap: wrap;
        gap: var(--space-1);
        border-radius: var(--radius);
        padding: var(--space-2);
    }

    .filter-toolbar .input {
        flex: 1 1 140px;
    }

    .filter-divider {
        display: none;
    }
}

@media (max-width: 860px) {
    .stat-grid {
        grid-template-columns: 1fr 1fr;
    }

    .filter-toolbar {
        border-radius: var(--radius);
    }

    .list-count {
        margin-left: 0;
        width: 100%;
    }
}

@media (max-width: 480px) {
    .stat-grid {
        grid-template-columns: 1fr;
    }

    .filter-toolbar .input {
        flex: 1 1 100%;
    }
}
</style>
