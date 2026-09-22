<script setup>
import { onMounted, ref, computed, watch } from "vue";
import { ChevronDown, ChevronRight, Search, Trash2 } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { useRouter } from "vue-router";
import { useDialog } from "../composables/useDialog";
import { selectedUserId } from "../composables/useSelectedUser";
import { isAdmin } from "../composables/useSession";
import { missingOnDate } from "../lib/dayStatus";
import { projectAccentIndex } from "../lib/projectAccent";
import { sortByIssuesFirst } from "../lib/standupInsights";
import {
    isFutureDate,
    todayString,
    weekRange,
    weekdayLabelOf,
} from "../lib/dateScope";
import { reportCountLabel, reportHeadline } from "../lib/reportSummary";
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
const onlyIssues = ref(false);

/** 오늘은 시계에서 읽는다. 저장된 가장 최근 날짜(미래 시드일 수 있음)를 쓰지 않는다. */
const today = ref(todayString());

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
    const report = reports.value.find((row) => String(row.id) === String(reportId));
    if (!report || !canManage(report)) {
        showAlert("자신의 보고만 삭제할 수 있습니다.");
        return;
    }
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

/** 카드에 "무엇을 했는지" 한 줄을 붙인다. 열어보기 전에 스캔할 수 있어야 한다. */
const headlineOf = (report) => reportHeadline(report.parsed_json);
const countLabelOf = (report) => reportCountLabel(report.parsed_json);

/** 프로젝트는 목록에서 골라 쓰므로 부분 일치가 아니라 정확히 맞춘다. */
const matchesProjectFilter = (report) => {
    if (filterProject.value === "") return true;
    return projectNamesOf(report).includes(filterProject.value);
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
        const matchIssue = !onlyIssues.value || issueCount(report) > 0;
        return (
            matchFrom &&
            matchEnd &&
            matchMember &&
            matchTeam &&
            matchIssue &&
            matchesProjectFilter(report)
        );
    });
});

/** 필터와 무관하게 전체 프로젝트를 보여줘야 다른 프로젝트로 바로 옮길 수 있다. */
const projectOptions = computed(() => {
    const names = new Set();
    for (const report of reports.value) {
        for (const name of projectNamesOf(report)) names.add(name);
    }
    return [...names].sort((a, b) => String(a).localeCompare(String(b), "ko"));
});

/** 프로젝트마다 같은 색을 유지해 이름이 반복돼도 눈으로 구분되게 한다. */
const projectAccents = computed(() => {
    const map = {};
    projectOptions.value.forEach((name, index) => {
        map[name] = projectAccentIndex(index);
    });
    return map;
});

const accentOf = (name) => projectAccents.value[name] ?? 0;

const hasActiveFilter = computed(
    () =>
        Boolean(filterMember.value) ||
        Boolean(filterProject.value) ||
        Boolean(filterDateFrom.value) ||
        Boolean(filterDateEnd.value) ||
        onlyIssues.value ||
        filterTeam.value !== "all",
);

/** 기본 상태(이번 주 스코프 + 필터 없음)에서는 되돌릴 게 없다. */
const isDefaultView = computed(
    () =>
        activeScope.value === DEFAULT_SCOPE &&
        !filterMember.value &&
        !filterProject.value &&
        filterTeam.value === "all",
);

/* 오늘, 이번 주, 이슈, 전체는 하나만 켠다.
   이슈를 날짜 위에 겹치면 오늘 제출 수가 1건으로 줄어든다. */
const SCOPES = [
    { id: "today", label: "오늘" },
    { id: "week", label: "이번 주" },
    { id: "issues", label: "이슈" },
    { id: "all", label: "전체" },
];

const setScope = (id) => {
    if (id === "today") {
        filterDateFrom.value = today.value;
        filterDateEnd.value = today.value;
        onlyIssues.value = false;
        return;
    }
    if (id === "week") {
        // 주 전체(월~일)를 연다. 오늘까지만 자르면 이번 주 흐름이 반만 보인다.
        const { start, end } = weekRange();
        filterDateFrom.value = start;
        filterDateEnd.value = end;
        onlyIssues.value = false;
        return;
    }
    if (id === "issues") {
        filterDateFrom.value = "";
        filterDateEnd.value = "";
        onlyIssues.value = true;
        return;
    }
    filterDateFrom.value = "";
    filterDateEnd.value = "";
    onlyIssues.value = false;
};

const activeScope = computed(() => {
    const from = filterDateFrom.value;
    const end = filterDateEnd.value;
    if (onlyIssues.value) return !from && !end ? "issues" : "custom";
    if (from === today.value && end === today.value) return "today";
    const week = weekRange();
    if (from === week.start && end === week.end) return "week";
    if (!from && !end) return "all";
    return "custom";
});

const scopeCounts = computed(() => {
    const week = weekRange();
    const counts = { today: 0, week: 0, issues: 0, all: reports.value.length };
    for (const report of reports.value) {
        const date = report.report_date ?? "";
        if (date === today.value) counts.today += 1;
        if (date >= week.start && date <= week.end) counts.week += 1;
        if (issueCount(report) > 0) counts.issues += 1;
    }
    return counts;
});

const scopeCountOf = (id) => scopeCounts.value[id] ?? 0;

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

const weekdayOf = (value) => weekdayLabelOf(value);

/** 부서가 하나뿐이면 고를 게 없다. 장식으로 남기지 않고 숨긴다. */
const showTeamFilter = computed(() => teams.value.length > 1);

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
            isFuture: isFutureDate(group.date),
            holidayName: holidayNames.value[group.date] || "",
            reports: sortByIssuesFirst(group.reports, issueCount, {
                pinMemberId: selectedUserId.value,
            }),
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

const isMine = (report) =>
    selectedUserId.value != null &&
    String(report.member_id ?? "") === String(selectedUserId.value);

const canManage = (report) => isMine(report) || isAdmin.value;

const openDetail = (reportId) => {
    router.push({
        name: "report-result",
        params: { id: reportId },
        query: { from: "list" },
    });
};

/* 날짜별 접기: 사람이 많으면 하루만 펼쳐도 화면이 꽉 찬다.
   기본은 오늘을 펼친다. 오늘 보고가 없으면 가장 최근 과거 날짜를 펼친다. */
const openDates = ref(new Set());
const hasManualToggle = ref(false);

const defaultOpenDate = (groups) => {
    if (!groups.length) return null;
    const todayGroup = groups.find((group) => group.date === today.value);
    if (todayGroup) return todayGroup.date;
    const past = groups.filter((group) => !group.isFuture);
    return (past[0] || groups[0]).date;
};

watch(
    reportsByDate,
    (groups) => {
        if (hasManualToggle.value) return;
        const date = defaultOpenDate(groups);
        openDates.value = new Set(date ? [date] : []);
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

/* 하루 안에서도 인원이 많으면 앞쪽만 보여준다.
   내 보고와 이슈가 있는 사람이 먼저 정렬되므로 잘리는 쪽은 덜 급한 사람이다. */
const ROW_LIMIT = 10;

const expandedDates = ref(new Set());

const isDateExpanded = (date) => expandedDates.value.has(date);

const toggleExpandDate = (date) => {
    const next = new Set(expandedDates.value);
    if (next.has(date)) next.delete(date);
    else next.add(date);
    expandedDates.value = next;
};

const visibleReports = (group) =>
    isDateExpanded(group.date)
        ? group.reports
        : group.reports.slice(0, ROW_LIMIT);

const hiddenCount = (group) =>
    Math.max(0, group.reports.length - ROW_LIMIT);

/* 미제출이 많으면 배너 줄도 길어진다. 앞 6명만 적고 나머지는 수로 표시한다. */
const MISSING_PREVIEW = 6;

const missingPreview = (names) => names.slice(0, MISSING_PREVIEW).join(" · ");

const missingRest = (names) => Math.max(0, names.length - MISSING_PREVIEW);

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

const pickProject = (name) => {
    filterProject.value = filterProject.value === name ? "" : name;
};

/** 출근하면 오늘부터 본다. 이번 주는 스코프에서 연다. */
const DEFAULT_SCOPE = "today";

const clearFilters = () => {
    filterMember.value = "";
    filterProject.value = "";
    filterTeam.value = "all";
    setScope(DEFAULT_SCOPE);
};

/** 배너는 필터와 무관하게 "오늘 미제출"만 말한다.
 *  전체 보기에서 예전 날짜의 미제출이 위에 붙으면 오늘 상황을 읽을 수 없다. */
const todayMissing = computed(() => {
    const submitted = new Set(
        reports.value
            .filter((report) => report.report_date === today.value)
            .map((report) => report.member_name),
    );
    return missingOnDate(
        today.value,
        memberRoster.value.filter((name) => !submitted.has(name)),
        holidayNames.value,
    );
});

const todayLabel = computed(
    () => `${formatDate(today.value)} (${weekdayOf(today.value)})`,
);

const todayHolidayName = computed(() => holidayNames.value[today.value] || "");

onMounted(() => {
    document.title = "일일보고";
    setScope(DEFAULT_SCOPE);
    fetchReports();
    fetchTeams();
    fetchMembers();
});
</script>

<template>
    <div class="page">

        <p class="today-banner" :class="{ 'is-clear': todayMissing.length === 0 }" role="status">
            <strong>{{ todayLabel }}</strong>
            <template v-if="todayHolidayName">
                {{ todayHolidayName }} · 제출 대상 아님
            </template>
            <template v-else-if="todayMissing.length">
                오늘 미제출 {{ todayMissing.length }}명 ·
                {{ missingPreview(todayMissing) }}
                <template v-if="missingRest(todayMissing)">
                    외 {{ missingRest(todayMissing) }}명
                </template>
            </template>
            <template v-else>오늘 미제출 없음</template>
        </p>

        <div class="stat-grid" role="tablist" aria-label="기간 스코프">
            <button
                v-for="item in SCOPES"
                :key="item.id"
                type="button"
                role="tab"
                class="stat-card"
                :class="{ 'is-active': activeScope === item.id }"
                :aria-selected="activeScope === item.id"
                @click="setScope(item.id)"
            >
                <span class="stat-label">{{ item.label }}</span>
                <strong class="stat-value">{{ scopeCountOf(item.id) }}</strong>
            </button>
        </div>

        <div class="filter-presets">
            <span v-if="activeScope === 'custom'" class="scope-note">직접 고른 기간</span>
            <button type="button" class="btn btn-small" :disabled="isDefaultView" @click="clearFilters">
                오늘로 되돌리기
            </button>
            <button
                type="button"
                class="btn btn-small"
                :disabled="reportsByDate.length === 0"
                @click="toggleAllDates"
            >
                {{ allOpen ? "모두 접기" : "모두 펼치기" }}
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
            <template v-if="showTeamFilter">
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
            </template>
            <span class="filter-divider" aria-hidden="true"></span>
            <input
                id="filterMember"
                type="text"
                placeholder="이름 검색"
                v-model="filterMember"
                class="input"
                autocomplete="off"
                aria-label="작성자"
            />
            <span class="filter-divider" aria-hidden="true"></span>
            <select
                id="filterProject"
                v-model="filterProject"
                class="input"
                aria-label="프로젝트"
            >
                <option value="">전체 프로젝트</option>
                <option v-for="name in projectOptions" :key="name" :value="name">
                    {{ name }}
                </option>
            </select>
        </AppFilterBar>

        <div v-if="isLoading" class="empty-state">보고서를 불러오는 중...</div>
        <div v-else-if="filteredReportsByProject.length === 0" class="empty-state">
            <Search :size="20" />
            <p>조건에 맞는 보고서가 없습니다</p>
            <button v-if="hasActiveFilter" type="button" class="btn" @click="clearFilters">
                오늘로 되돌리기
            </button>
        </div>
        <div v-else class="reports-container">
            <section
                v-for="group in reportsByDate"
                :key="group.date"
                class="card date-group"
                :class="{ 'is-future': group.isFuture }"
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
                    <span v-if="group.date === today" class="date-tag is-today">오늘</span>
                    <span v-else-if="group.isFuture" class="date-tag is-future">예정</span>
                    <span v-if="group.holidayName" class="date-tag is-holiday">
                        {{ group.holidayName }}
                    </span>
                    <em>
                        {{ group.reports.length }}명
                        <template v-if="group.issueTotal"> · 이슈 {{ group.issueTotal }}</template>
                        <template v-if="group.missing.length"> · 미제출 {{ group.missing.length }}</template>
                    </em>
                </button>
                <template v-if="isDateOpen(group.date)">
                <AppListRow
                    v-for="report in visibleReports(group)"
                    :key="report.id"
                    clickable
                    class="person-row"
                    :class="{ 'is-mine': isMine(report) }"
                    tabindex="0"
                    @click="openDetail(report.id)"
                    @keydown="onCardKeydown($event, report.id)"
                >
                    <div class="report-identity">
                        <span class="avatar">{{
                            String(report.member_name || "?").slice(0, 1)
                        }}</span>
                        <div class="report-copy">
                            <h3 class="report-name">
                                {{ report.member_name }}
                                <span v-if="showTeamFilter" class="report-sub">{{ teamNameOf(report) }}</span>
                                <span v-if="isMine(report)" class="mine-tag">내 보고</span>
                            </h3>
                            <p class="report-line">
                                <span v-if="headlineOf(report)" class="report-headline">
                                    {{ headlineOf(report) }}
                                </span>
                                <span v-else class="report-headline is-empty">
                                    추출된 업무가 없습니다
                                </span>
                                <span v-if="countLabelOf(report)" class="report-counts">
                                    {{ countLabelOf(report) }}
                                </span>
                            </p>
                        </div>
                    </div>
                    <template #meta>
                        <button
                            v-for="name in projectNamesOf(report)"
                            :key="name"
                            type="button"
                            class="meta-chip project-chip"
                            :class="{ 'is-on': filterProject === name }"
                            :data-accent="accentOf(name)"
                            :title="filterProject === name ? '프로젝트 필터 해제' : name + '만 보기'"
                            @click.stop="pickProject(name)"
                        >
                            <i class="project-dot" aria-hidden="true"></i>
                            {{ name }}
                        </button>
                        <span v-if="issueCount(report) > 0" class="meta-chip issue-chip">
                            이슈 {{ issueCount(report) }}
                        </span>
                    </template>
                    <template v-if="canManage(report)" #actions>
                        <button type="button" class="btn btn-danger btn-icon" aria-label="보고서 삭제"
                            @click="deleteProjectReport(report.id, $event)">
                            <Trash2 :size="15" />
                        </button>
                    </template>
                </AppListRow>
                <button
                    v-if="hiddenCount(group)"
                    type="button"
                    class="more-rows"
                    @click="toggleExpandDate(group.date)"
                >
                    {{ isDateExpanded(group.date) ? "앞쪽 10명만 보기" : `+${hiddenCount(group)}명 더 보기` }}
                </button>
                </template>
            </section>
        </div>
    </div>
</template>

<style scoped>
/* 오늘 배너: 필터와 무관하게 오늘 상황만 말한다.
   미제출이 없으면 경고색을 쓰지 않는다. */
.today-banner {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
    margin: 0 0 var(--space-4);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--warning-border);
    border-radius: var(--radius);
    background: var(--warning-bg);
    color: var(--warning-fg);
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    word-break: keep-all;
}

.today-banner strong {
    font-weight: var(--fw-semibold);
}

.today-banner.is-clear {
    border-color: var(--border);
    background: var(--surface);
    color: var(--text);
}

.scope-note {
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.date-tag {
    flex-shrink: 0;
    padding: 1px var(--space-2);
    border-radius: var(--radius-pill);
    background: var(--surface-soft);
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.date-tag.is-today {
    background: var(--accent-soft);
    color: var(--accent-hover);
}

.date-tag.is-holiday {
    background: var(--danger-bg);
    color: var(--danger-fg);
}

/* 미래 날짜는 아직 일어나지 않은 하루다. 끝난 주처럼 보이지 않게 흐리게 둔다. */
.date-group.is-future {
    opacity: 0.72;
}

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

.date-head svg {
    flex-shrink: 0;
    color: var(--text-muted);
}

.more-rows {
    display: block;
    width: 100%;
    padding: var(--space-3) var(--space-4);
    border: none;
    border-top: 1px solid var(--border);
    background: transparent;
    font: inherit;
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    color: var(--text);
    text-align: center;
    cursor: pointer;
}

.more-rows:hover {
    background: var(--surface-soft);
    color: var(--text-strong);
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
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
    font-size: var(--fs-14);
    font-weight: var(--fw-medium);
}

.mine-tag {
    padding: 0 6px;
    border-radius: var(--radius-pill);
    background: var(--accent-soft);
    color: var(--accent-hover);
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
}

/* 내 보고는 항상 맨 위에 오고 왼쪽 띠로 표시한다. */
.person-row.is-mine {
    box-shadow: inset 2px 0 0 var(--accent);
}

/* 이름 아래 한 줄 요약. 열어보기 전에 "뭘 했는지"를 읽게 한다. */
.report-line {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
    margin: 2px 0 0;
    min-width: 0;
}

.report-headline {
    min-width: 0;
    max-width: 52ch;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--fs-13);
    color: var(--text-strong);
}

.report-headline.is-empty {
    color: var(--text);
    opacity: 0.7;
}

.report-counts {
    flex-shrink: 0;
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.report-sub {
    font-size: var(--fs-11);
    color: var(--text);
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

/* 프로젝트 칩: report-doc의 6색 팔레트를 재사용해 같은 프로젝트는 항상 같은 색. */
.project-chip {
    --project-accent: var(--accent);
    gap: var(--space-2);
    border: 1px solid transparent;
    font: inherit;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    cursor: pointer;
}

.project-chip[data-accent="1"] {
    --project-accent: var(--info-fg);
}

.project-chip[data-accent="2"] {
    --project-accent: var(--warning-fg);
}

.project-chip[data-accent="3"] {
    --project-accent: var(--success-fg);
}

.project-chip[data-accent="4"] {
    --project-accent: var(--project-4-fg);
}

.project-chip[data-accent="5"] {
    --project-accent: var(--project-5-fg);
}

.project-dot {
    flex-shrink: 0;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--project-accent);
}

.project-chip:hover {
    border-color: var(--project-accent);
}

.project-chip.is-on {
    border-color: var(--project-accent);
    background: var(--surface);
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
    .filter-divider {
        display: none;
    }
}

@media (max-width: 860px) {
    .stat-grid {
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-bottom: 12px;
    }

    .stat-card {
        padding: 12px 12px 10px;
        gap: 4px;
    }

    .stat-value {
        font-size: 22px;
    }

    .list-count {
        margin-left: 0;
        width: 100%;
    }

    .filter-presets {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
    }

    .filter-presets .btn,
    .list-count,
    .scope-note {
        width: 100%;
        min-height: 44px;
    }

    .list-count,
    .scope-note {
        grid-column: 1 / -1;
        display: flex;
        align-items: center;
    }

    .today-banner {
        padding: 10px 12px;
        font-size: 13px;
    }

    .date-head {
        flex-wrap: wrap;
        min-height: 48px;
    }

    .date-head em {
        width: 100%;
        margin-left: 28px;
    }

    .avatar {
        width: 36px;
        height: 36px;
        font-size: 13px;
    }

    .report-headline {
        white-space: normal;
        max-width: none;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
    }

    .person-row {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: 8px 10px;
        padding-right: 12px;
    }

    .person-row :deep(.app-list-row-main) {
        grid-column: 1;
        grid-row: 1;
        min-width: 0;
    }

    .person-row :deep(.app-list-row-meta) {
        grid-column: 1 / -1;
        grid-row: 2;
    }

    .person-row :deep(.app-list-row-actions) {
        grid-column: 2;
        grid-row: 1;
        align-self: center;
        justify-content: flex-end;
    }

    .person-row :deep(.btn-icon) {
        width: 44px;
        height: 44px;
        min-height: 44px;
        padding: 0;
    }
}
</style>
