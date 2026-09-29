<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import { isAdmin } from "../composables/useSession";
import { selectedUserId } from "../composables/useSelectedUser";
import { todayString, weekdayLabelOf } from "../lib/dateScope";
import { daySubmission } from "../lib/weekStatus";
import { reportCounts, reportHeadline } from "../lib/reportSummary";
import { COMPOSE_CHOICES } from "../lib/nav";

const router = useRouter();
const writeChoices = COMPOSE_CHOICES.map((item) =>
    item.id === "daily" ? { ...item, label: "보고서 작성" } : item,
);
const { alert: showAlert, confirm: askConfirm } = useDialog();
const { getReports, deleteReport, getUsers } = useApi();
const members = ref([]);

const reports = ref([]);
const isLoading = ref(false);
const loadError = ref("");
const query = ref("");
const filterProject = ref("");

const fetchReports = async () => {
    isLoading.value = true;
    loadError.value = "";
    try {
        const [rows, users] = await Promise.all([
            getReports(),
            getUsers().catch(() => []),
        ]);
        reports.value = rows;
        members.value = Array.isArray(users) ? users : [];
    } catch (error) {
        console.error("Error fetching reports:", error);
        loadError.value = "보고서를 불러오지 못했습니다.";
    } finally {
        isLoading.value = false;
    }
};

/** 오늘 누가 냈고 누가 안 냈는지. 검색·필터 중에는 숨긴다(부분 목록과 섞이면 헷갈린다). */
const today = todayString();
const todaySummary = computed(() => {
    if (query.value.trim() || filterProject.value || !members.value.length) return null;
    const result = daySubmission(members.value, reports.value, today);
    if (!result.total) return null;
    const weekday = weekdayLabelOf(today);
    const [, month, day] = today.split("-").map(Number);
    return { ...result, label: `${month}월 ${day}일 ${weekday}` };
});

const isMine = (report) =>
    selectedUserId.value != null &&
    String(report.member_id ?? "") === String(selectedUserId.value);

const canManage = (report) => isMine(report) || isAdmin.value;

const projectNamesOf = (report) => {
    const parsed = report?.parsed_json;
    const data = typeof parsed === "string" ? safeJson(parsed) : parsed;
    return (data?.projects || [])
        .map((project) => String(project?.projectName || "").trim())
        .filter(Boolean);
};

const safeJson = (value) => {
    try {
        return JSON.parse(value);
    } catch {
        return null;
    }
};

const projectOptions = computed(() => {
    const names = new Set();
    for (const report of reports.value) {
        for (const name of projectNamesOf(report)) names.add(name);
    }
    return [...names].sort((a, b) => a.localeCompare(b, "ko"));
});

const filteredReports = computed(() => {
    const needle = query.value.trim().toLowerCase();
    return reports.value.filter((report) => {
        if (filterProject.value && !projectNamesOf(report).includes(filterProject.value)) {
            return false;
        }
        if (!needle) return true;
        const haystack = [
            report.member_name,
            reportHeadline(report.parsed_json),
            ...projectNamesOf(report),
        ]
            .join(" ")
            .toLowerCase();
        return haystack.includes(needle);
    });
});

const groups = computed(() => {
    const index = new Map();
    const dates = [];
    for (const report of filteredReports.value) {
        const date = report.report_date ?? "";
        if (!index.has(date)) {
            index.set(date, []);
            dates.push(date);
        }
        index.get(date).push(report);
    }
    dates.sort((a, b) => String(b).localeCompare(String(a)));
    return dates.map((date) => ({
        date,
        label: formatDate(date),
        weekday: weekdayLabelOf(date),
        point: groupPoint(index.get(date)),
        reports: index.get(date).slice().sort((a, b) => {
            if (isMine(a) !== isMine(b)) return isMine(a) ? -1 : 1;
            return String(a.member_name || "").localeCompare(
                String(b.member_name || ""),
                "ko",
            );
        }),
    }));
});

const formatDate = (value) => {
    const [year, month, day] = String(value || "").split("-");
    if (!year || !month || !day) return value || "";
    return `${year}.${Number(month)}.${Number(day)}`;
};

const groupPoint = (rows) => {
    const issues = rows.reduce(
        (sum, report) => sum + reportCounts(report.parsed_json).issues,
        0,
    );
    const bits = [`${rows.length}명`];
    if (issues) bits.push(`이슈 ${issues}`);
    return bits.join(" · ");
};

const badgesOf = (report) => {
    const counts = reportCounts(report.parsed_json);
    return [
        counts.done && { key: "done", label: `완료 ${counts.done}` },
        counts.progress && { key: "progress", label: `진행 ${counts.progress}` },
        counts.issues && { key: "issues", label: `이슈 ${counts.issues}` },
        counts.requests && { key: "requests", label: `요청 ${counts.requests}` },
    ].filter(Boolean);
};

const openDetail = (reportId) => {
    router.push({
        name: "report-result",
        params: { id: reportId },
        query: { from: "list" },
    });
};

const onRowKeydown = (event, reportId) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    openDetail(reportId);
};

const deleteProjectReport = async (reportId) => {
    const report = reports.value.find((row) => String(row.id) === String(reportId));
    if (!report || !canManage(report)) {
        showAlert("자신의 보고만 삭제할 수 있습니다.");
        return;
    }
    if (!(await askConfirm("이 보고서를 삭제할까요?"))) return;
    try {
        await deleteReport(reportId);
        await fetchReports();
    } catch (error) {
        console.error("Error deleting report:", error);
        showAlert("삭제에 실패했습니다.");
    }
};

onMounted(() => {
    document.title = "일일보고";
    fetchReports();
});
</script>

<template>
    <div class="page">
        <nav class="write-kinds" aria-label="작성">
            <router-link
                v-for="item in writeChoices"
                :key="item.id"
                class="btn btn-small"
                :class="{ 'btn-primary': item.id === 'daily' }"
                :to="item.to"
            >{{ item.label }}</router-link>
        </nav>

        <section v-if="todaySummary" class="card today-sum" aria-label="오늘 제출 현황">
            <div class="today-sum-head">
                <h2>오늘 <span>{{ todaySummary.label }}</span></h2>
                <p>{{ todaySummary.total }}명 중 {{ todaySummary.saved }}명 제출</p>
            </div>
            <div
                class="today-sum-bar"
                role="img"
                :aria-label="`제출 ${todaySummary.saved}명, 미제출 ${todaySummary.missing.length}명`"
            >
                <span class="is-saved" :style="{ flexGrow: todaySummary.saved }"></span>
                <span class="is-missing" :style="{ flexGrow: todaySummary.missing.length }"></span>
            </div>
            <p v-if="todaySummary.missing.length" class="today-sum-missing">
                <span class="state-chip is-danger">미제출 {{ todaySummary.missing.length }}</span>
                {{ todaySummary.missing.join(", ") }}
            </p>
            <p v-else class="today-sum-missing is-done">오늘은 모두 제출했어요.</p>
        </section>

        <div class="list-search">
            <input
                id="report-query"
                v-model="query"
                class="input"
                type="search"
                placeholder="이름, 프로젝트, 내용"
                aria-label="검색"
                enterkeyhint="search"
            />
            <select v-model="filterProject" class="input" aria-label="프로젝트">
                <option value="">전체 프로젝트</option>
                <option v-for="name in projectOptions" :key="name" :value="name">
                    {{ name }}
                </option>
            </select>
        </div>

        <p v-if="isLoading" class="list-status" role="status">보고서를 불러오는 중</p>
        <p v-else-if="loadError" class="list-status is-error" role="alert">{{ loadError }}</p>
        <p v-else-if="groups.length === 0" class="list-status">
            {{ query.trim() || filterProject ? "검색 결과가 없습니다." : "보고서가 없습니다." }}
        </p>

        <section v-for="group in groups" :key="group.date" class="day">
            <header class="day-head">
                <h2>{{ group.label }} {{ group.weekday }}</h2>
                <p class="day-point">{{ group.point }}</p>
            </header>
            <div class="reports">
                <article
                    v-for="report in group.reports"
                    :key="report.id"
                    class="report"
                    tabindex="0"
                    @click="openDetail(report.id)"
                    @keydown="onRowKeydown($event, report.id)"
                >
                    <div class="chips">
                        <span
                            v-for="name in projectNamesOf(report)"
                            :key="name"
                            class="chip"
                        >{{ name }}</span>
                        <span v-if="projectNamesOf(report).length === 0" class="chip">프로젝트 없음</span>
                    </div>
                    <p class="person">{{ report.member_name }}</p>
                    <p v-if="badgesOf(report).length" class="badges">
                        <span
                            v-for="badge in badgesOf(report)"
                            :key="badge.key"
                            class="badge"
                            :class="badge.key"
                        >{{ badge.label }}</span>
                    </p>
                    <button
                        v-if="canManage(report)"
                        type="button"
                        class="row-delete"
                        @click.stop="deleteProjectReport(report.id)"
                    >
                        삭제
                    </button>
                </article>
            </div>
        </section>
    </div>
</template>

<style scoped>
.write-kinds {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
}

.list-search {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 220px;
    gap: var(--space-2);
    position: sticky;
    top: var(--space-2);
    z-index: 5;
    padding: var(--space-2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
}

.list-search .input {
    min-width: 0;
    min-height: var(--control-h-lg);
    font-size: var(--fs-16);
}

.list-search .input::placeholder {
    color: var(--text-muted);
    opacity: 1;
}

.today-sum {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
}

.today-sum-head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2);
}

.today-sum-head h2 {
    margin: 0;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.today-sum-head h2 span {
    font-weight: var(--fw-regular);
    color: var(--text-muted);
}

.today-sum-head p {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text-muted);
}

.today-sum-bar {
    display: flex;
    gap: 2px;
    height: 8px;
    overflow: hidden;
    border-radius: var(--radius-pill);
    background: var(--surface-soft);
}

.today-sum-bar .is-saved {
    background: var(--success-fg);
}

.today-sum-bar .is-missing {
    background: var(--danger-border);
}

.today-sum-missing {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    margin: 0;
    font-size: var(--fs-14);
    color: var(--text);
}

.today-sum-missing.is-done {
    color: var(--success-fg);
    font-weight: var(--fw-semibold);
}

.state-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: var(--chip-h);
    padding: 0 var(--space-3);
    border-radius: var(--radius-pill);
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
}

.state-chip::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: var(--radius-pill);
    background: currentColor;
}

.state-chip.is-danger {
    background: var(--danger-bg);
    color: var(--danger-fg);
}

.list-status {
    margin: 0;
    font-size: var(--fs-14);
    color: var(--text);
}

.list-status.is-error {
    color: var(--danger-fg);
}

.day {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
}

.day-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3);
}

.day h2 {
    margin: 0;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.day-point {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text-muted);
    white-space: nowrap;
}

.reports {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-2);
}

.report {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-width: 0;
    padding: var(--space-4) var(--control-h-lg) var(--space-4) var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    cursor: pointer;
}

.report:hover {
    border-color: var(--border-strong);
    background: var(--accent-soft);
}

.chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-3);
    min-width: 0;
}

.chip {
    display: inline-block;
    color: var(--text-strong);
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
    line-height: 1.35;
    white-space: nowrap;
    word-break: keep-all;
}

.person {
    margin: 0;
    font-size: var(--fs-13);
    line-height: 1.4;
    color: var(--text);
}

.badges {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: 0;
}

.badge {
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-pill);
    background: var(--surface-soft);
    color: var(--text);
    font-size: var(--fs-12);
    line-height: 1.4;
}

.badge.done {
    background: var(--success-bg);
    color: var(--success-fg);
}

.badge.progress {
    background: var(--info-bg);
    color: var(--info-fg);
}

.badge.issues {
    background: var(--warning-bg);
    color: var(--warning-fg);
}

.badge.requests {
    background: var(--project-4-bg);
    color: var(--project-4-fg);
}

.row-delete {
    position: absolute;
    top: var(--space-3);
    right: var(--space-2);
    min-width: var(--control-h-sm);
    min-height: var(--control-h-sm);
    padding: 0 var(--space-1);
    border: 0;
    background: transparent;
    color: var(--text-muted);
    font: inherit;
    font-size: var(--fs-13);
    cursor: pointer;
}

.row-delete:hover {
    color: var(--danger-fg);
}

@media (min-width: 721px) {
    .reports {
        grid-template-columns: 1fr 1fr;
    }

    .report:only-child {
        grid-column: 1 / -1;
    }
}

.row-delete:focus-visible,
.report:focus-visible,
.list-search .input:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
}

@media (max-width: 860px) {
    .list-search {
        grid-template-columns: minmax(0, 1fr);
        top: var(--space-2);
    }

    .row-delete {
        min-width: var(--control-h-lg);
        min-height: var(--control-h-lg);
    }
}
</style>
