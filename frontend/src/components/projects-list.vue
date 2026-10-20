<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ChevronRight, Trash2 } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import { isAdmin } from "../composables/useSession";
import { selectedUserId } from "../composables/useSelectedUser";
import { weekdayLabelOf } from "../lib/dateScope";
import { reportCounts, reportHeadline } from "../lib/reportSummary";

const router = useRouter();
const { alert: showAlert, confirm: askConfirm } = useDialog();
const { getReports, deleteReport } = useApi();

const reports = ref([]);
const isLoading = ref(false);
const loadError = ref("");
const query = ref("");
const filterProject = ref("");
/** 지금 걸린 조건. 두 개를 같이 걸면 결과가 비는데 무엇이 걸렸는지 안 보여 헷갈렸다. */
const filterSummary = computed(() =>
    [query.value.trim() && `검색 "${query.value.trim()}"`, filterProject.value && `프로젝트 ${filterProject.value}`]
        .filter(Boolean)
        .join(" · "),
);
const clearFilters = () => {
    query.value = "";
    filterProject.value = "";
};

const fetchReports = async () => {
    isLoading.value = true;
    loadError.value = "";
    try {
        reports.value = await getReports();
    } catch (error) {
        console.error("Error fetching reports:", error);
        loadError.value = "보고서를 불러오지 못했습니다.";
    } finally {
        isLoading.value = false;
    }
};

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

const isoToday = () => {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
};

const formatDate = (value) => {
    const [year, month, day] = String(value || "").split("-");
    if (!year || !month || !day) return value || "";
    if (value === isoToday()) return "오늘";
    const thisYear = String(new Date().getFullYear()) === year;
    return thisYear ? `${Number(month)}월 ${Number(day)}일` : `${year}년 ${Number(month)}월 ${Number(day)}일`;
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
        counts.done && { key: "is-done", label: `완료 ${counts.done}` },
        counts.progress && { key: "is-progress", label: `진행 ${counts.progress}` },
        counts.issues && { key: "is-issue", label: `이슈 ${counts.issues}` },
        counts.requests && { key: "is-request", label: `요청 ${counts.requests}` },
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
    const owner = isMine(report) ? "내" : `${report.member_name}님의`;
    const ok = await askConfirm(`${formatDate(report.report_date)} ${owner} 일일보고를 삭제할까요?`, {
        title: "일일보고 삭제",
        confirmLabel: "삭제",
        help: "삭제하면 되돌릴 수 없어요.",
        danger: true,
    });
    if (!ok) return;
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
        <div class="list-toolbar">
            <input
                id="report-query"
                v-model="query"
                class="input"
                type="search"
                placeholder="이름 · 프로젝트 검색"
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

        <p v-if="filterSummary" class="filter-active">
            <span>{{ filterSummary }}</span>
            <button type="button" class="btn btn-small btn-ghost" @click="clearFilters">조건 지우기</button>
        </p>

        <p v-if="isLoading" class="list-status" role="status">보고서를 불러오는 중</p>
        <p v-else-if="loadError" class="list-status is-error" role="alert">{{ loadError }}</p>
        <div v-else-if="groups.length === 0" class="empty-state">
            <p class="empty-title">
                {{ query.trim() || filterProject ? "맞는 보고가 없어요" : "아직 저장된 일일보고가 없어요" }}
            </p>
            <p class="empty-body">
                {{ filterSummary ? `${filterSummary} 조건에 맞는 보고가 없어요.` : "원문을 붙여 넣으면 AI가 프로젝트별로 정리해 줘요." }}
            </p>
            <div v-if="filterSummary" class="empty-actions">
                <button type="button" class="btn" @click="clearFilters">조건 지우기</button>
            </div>
            <div v-else class="empty-actions">
                <router-link class="btn btn-primary" to="/compose?kind=daily">일일보고 쓰기</router-link>
            </div>
        </div>

        <section v-for="group in groups" :key="group.date" class="group-block">
            <header class="group-head">
                <h2>{{ group.label }} <span class="day-weekday">{{ group.weekday }}</span></h2>
                <span class="group-meta">{{ group.point }}</span>
            </header>
            <div class="group has-avatars">
                <div
                    v-for="report in group.reports"
                    :key="report.id"
                    class="row"
                    role="link"
                    tabindex="0"
                    @click="openDetail(report.id)"
                    @keydown="onRowKeydown($event, report.id)"
                >
                    <span class="avatar" :class="{ 'is-me': isMine(report) }">
                        {{ String(report.member_name || "?").slice(0, 1) }}
                    </span>
                    <!-- 누가 · 어느 프로젝트 → 무슨 일 → 건수. 위에서 아래로 한 칸 안에서 읽힌다. -->
                    <span class="report-main">
                        <span class="report-who">
                            <span class="report-name">{{ report.member_name }}</span>
                            <span v-if="isMine(report)" class="me-mark">나</span>
                            <span class="report-projects">
                                {{ projectNamesOf(report).join(" · ") || "프로젝트 없음" }}
                            </span>
                        </span>
                        <span v-if="reportHeadline(report.parsed_json)" class="report-headline">
                            {{ reportHeadline(report.parsed_json) }}
                        </span>
                        <span v-if="badgesOf(report).length" class="badges">
                            <span
                                v-for="badge in badgesOf(report)"
                                :key="badge.key"
                                class="cat-tag"
                                :class="badge.key"
                            >{{ badge.label }}</span>
                        </span>
                    </span>
                    <span class="row-end">
                        <button
                            v-if="canManage(report)"
                            type="button"
                            class="row-icon-btn"
                            :aria-label="`${report.member_name} 보고 삭제`"
                            title="삭제"
                            @click.stop="deleteProjectReport(report.id)"
                            @keydown.stop
                        >
                            <Trash2 :size="16" />
                        </button>
                        <ChevronRight :size="16" class="row-chevron" />
                    </span>
                </div>
            </div>
        </section>
    </div>
</template>

<style scoped src="../styles/components/projects-list.css"></style>
