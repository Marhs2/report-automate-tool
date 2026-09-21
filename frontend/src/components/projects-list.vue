<script setup>
import { onMounted, ref, computed, watch } from "vue";
import { ChevronDown, ChevronRight, Search, X } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { useRouter } from "vue-router";
import { useDialog } from "../composables/useDialog";
import { missingOnDate } from "../lib/dayStatus";
import { missingBanner } from "../lib/standupInsights";
import AppPageHeader from "./ui/AppPageHeader.vue";
import AppFilterBar from "./ui/AppFilterBar.vue";

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

const NO_PROJECT = "내용 없음";

const byKoreanName = (a, b) =>
    String(a.name).localeCompare(String(b.name), "ko");

const peopleOf = (reports) =>
    reports
        .map((report) => ({
            id: report.id,
            name: report.member_name,
            projects: projectNamesOf(report),
            issues: issueCount(report),
        }))
        .sort(byKoreanName);

const bucketsByProject = (people) => {
    const buckets = [];
    const index = new Map();
    for (const person of people) {
        for (const name of person.projects.length
            ? person.projects
            : [NO_PROJECT]) {
            let bucket = index.get(name);
            if (!bucket) {
                bucket = { name, people: [] };
                index.set(name, bucket);
                buckets.push(bucket);
            }
            bucket.people.push(person);
        }
    }
    return buckets.sort((a, b) => {
        if (a.name === NO_PROJECT) return 1;
        if (b.name === NO_PROJECT) return -1;
        return b.people.length - a.people.length;
    });
};

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
        const people = peopleOf(group.reports);
        return {
            date: group.date,
            reports: group.reports,
            people,
            buckets: bucketsByProject(people),
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

const openDates = ref(new Set());
const hasManualToggle = ref(false);

watch(
    reportsByDate,
    (groups) => {
        if (hasManualToggle.value) return;
        openDates.value = new Set(groups.slice(0, 1).map((group) => group.date));
    },
    { immediate: true },
);

const isDateOpen = (date) => openDates.value.has(date);

const toggleDate = (date) => {
    hasManualToggle.value = true;
    const next = new Set(openDates.value);
    if (next.has(date)) next.delete(date);
    else next.add(date);
    openDates.value = next;
};

const allOpen = computed(
    () =>
        reportsByDate.value.length > 0 &&
        reportsByDate.value.every((group) => openDates.value.has(group.date)),
);

const toggleAllDates = () => {
    hasManualToggle.value = true;
    openDates.value = allOpen.value
        ? new Set()
        : new Set(reportsByDate.value.map((group) => group.date));
};

const GROUP_MODE_KEY = "dxel.reports.groupBy";

const groupMode = ref(
    localStorage.getItem(GROUP_MODE_KEY) === "project" ? "project" : "person",
);

watch(groupMode, (mode) => localStorage.setItem(GROUP_MODE_KEY, mode));

const MISSING_PREVIEW = 6;

const missingPreview = (names) => names.slice(0, MISSING_PREVIEW).join(" · ");

const missingRest = (names) => Math.max(0, names.length - MISSING_PREVIEW);

const openDetail = (reportId) => {
    router.push(`/report-result/${reportId}`);
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
        <AppPageHeader subtitle="이름순으로 나열하고 이슈는 빨갛게 표시합니다" />

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
            <button
                type="button"
                class="btn btn-small"
                :disabled="reportsByDate.length === 0"
                @click="toggleAllDates"
            >
                {{ allOpen ? "모두 접기" : "모두 펼치기" }}
            </button>
            <span class="group-switch" role="group" aria-label="묶는 기준">
                <button
                    type="button"
                    class="btn btn-small"
                    :class="{ 'is-active': groupMode === 'person' }"
                    :aria-pressed="groupMode === 'person'"
                    @click="groupMode = 'person'"
                >
                    사람별
                </button>
                <button
                    type="button"
                    class="btn btn-small"
                    :class="{ 'is-active': groupMode === 'project' }"
                    :aria-pressed="groupMode === 'project'"
                    @click="groupMode = 'project'"
                >
                    프로젝트별
                </button>
            </span>
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
                <button
                    type="button"
                    class="date-head"
                    :aria-expanded="isDateOpen(group.date)"
                    @click="toggleDate(group.date)"
                >
                    <ChevronDown v-if="isDateOpen(group.date)" :size="16" />
                    <ChevronRight v-else :size="16" />
                    <strong>
                        {{ formatDate(group.date) }}
                        <b>{{ weekdayOf(group.date) }}</b>
                    </strong>
                    <em>
                        {{ group.reports.length }}명
                        <template v-if="group.issueTotal"> · 이슈 {{ group.issueTotal }}</template>
                        <template v-if="group.missing.length"> · 미제출 {{ group.missing.length }}</template>
                    </em>
                </button>
                <div v-if="isDateOpen(group.date)" class="date-body">
                    <p v-if="group.missing.length" class="missing-row">
                        미제출 {{ missingPreview(group.missing) }}
                        <template v-if="missingRest(group.missing)">
                            외 {{ missingRest(group.missing) }}명
                        </template>
                    </p>
                    <div v-if="groupMode === 'person'" class="people-rows">
                        <span
                            v-for="person in group.people"
                            :key="person.id"
                            class="person-line"
                            :class="{ 'has-issue': person.issues > 0 }"
                        >
                            <button
                                type="button"
                                class="person-open"
                                @click="openDetail(person.id)"
                            >
                                <strong class="person-name">{{ person.name }}</strong>
                                <span class="person-tags">
                                    <em
                                        v-for="project in person.projects"
                                        :key="project"
                                        class="tag"
                                    >
                                        {{ project }}
                                    </em>
                                    <em v-if="!person.projects.length" class="tag is-empty">
                                        내용 없음
                                    </em>
                                </span>
                                <b v-if="person.issues" class="person-issue">
                                    이슈 {{ person.issues }}
                                </b>
                            </button>
                            <button
                                type="button"
                                class="person-del"
                                :aria-label="person.name + ' 보고서 삭제'"
                                @click="deleteProjectReport(person.id, $event)"
                            >
                                <X :size="13" />
                            </button>
                        </span>
                    </div>
                    <div
                        v-for="bucket in groupMode === 'project' ? group.buckets : []"
                        :key="bucket.name"
                        class="project-bucket"
                    >
                        <h3 class="bucket-head">
                            {{ bucket.name }}
                            <span class="bucket-count">{{ bucket.people.length }}</span>
                        </h3>
                        <div class="people-chips">
                            <button
                                v-for="person in bucket.people"
                                :key="person.id"
                                type="button"
                                class="person-chip"
                                :class="{ 'has-issue': person.issues > 0 }"
                                @click="openDetail(person.id)"
                            >
                                {{ person.name }}
                                <em v-if="person.issues">이슈 {{ person.issues }}</em>
                            </button>
                        </div>
                    </div>
                </div>
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
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-3) var(--space-4);
    border: none;
    background: transparent;
    font: inherit;
    color: inherit;
    text-align: left;
    cursor: pointer;
}

.date-head:hover {
    background: var(--surface-soft);
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

.date-body {
    border-top: 1px solid var(--border);
    padding: var(--space-3) var(--space-4) var(--space-4);
}

.project-bucket + .project-bucket {
    margin-top: var(--space-4);
}

.bucket-head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: 0 0 var(--space-2);
    font-family: var(--sans);
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    letter-spacing: 0.04em;
    color: var(--text);
}

.bucket-count {
    padding: 0 6px;
    border-radius: var(--radius-pill);
    background: var(--surface-soft);
    font-size: var(--fs-11);
    color: var(--text);
}

.group-switch {
    display: inline-flex;
    gap: var(--space-1);
    margin-left: var(--space-2);
}

.people-rows {
    columns: 330px;
    column-gap: var(--space-6);
}

.person-line {
    display: flex;
    align-items: center;
    border-bottom: 1px solid var(--border);
    break-inside: avoid;
}

.person-line:hover {
    background: var(--accent-soft);
}

.person-open {
    display: grid;
    grid-template-columns: 72px minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-2);
    flex: 1;
    min-width: 0;
    padding: 5px 0;
    border: none;
    background: transparent;
    font: inherit;
    text-align: left;
    cursor: pointer;
}

.person-name {
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.person-tags {
    display: flex;
    gap: var(--space-1);
    min-width: 0;
    overflow: hidden;
}

.tag {
    padding: 1px 6px;
    border-radius: var(--radius-pill);
    background: var(--surface-soft);
    font-style: normal;
    font-size: var(--fs-11);
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.tag.is-empty {
    background: transparent;
    color: var(--text-muted);
}

.person-issue {
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
    color: var(--danger-fg);
    white-space: nowrap;
}

.person-del {
    display: inline-flex;
    align-items: center;
    padding: 2px 4px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    opacity: 0;
}

.person-line:hover .person-del,
.person-del:focus-visible {
    opacity: 1;
}

.person-del:hover {
    color: var(--danger-fg);
}

.people-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
}

.person-chip {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: 3px var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    background: var(--surface);
    font: inherit;
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    color: var(--text-strong);
    cursor: pointer;
}

.person-chip:hover {
    border-color: var(--accent-border);
    background: var(--accent-soft);
}

.person-chip.has-issue {
    border-color: var(--danger-border);
    background: var(--danger-bg);
}

.person-chip em {
    font-style: normal;
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
    color: var(--danger-fg);
}

.missing-row {
    margin: 0 0 var(--space-3);
    font-size: var(--fs-12);
    color: var(--text);
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
