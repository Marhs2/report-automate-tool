<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import { isAdmin } from "../composables/useSession";
import { selectedUserId } from "../composables/useSelectedUser";
import { weekdayLabelOf } from "../lib/dateScope";
import { reportHeadline } from "../lib/reportSummary";
import AppListRow from "./ui/AppListRow.vue";

const router = useRouter();
const { alert: showAlert, confirm: askConfirm } = useDialog();
const { getReports, deleteReport } = useApi();

const reports = ref([]);
const isLoading = ref(false);
const loadError = ref("");
const query = ref("");
const filterProject = ref("");

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

        <section v-for="group in groups" :key="group.date" class="card day">
            <h2>{{ group.label }} {{ group.weekday }}</h2>
            <AppListRow
                v-for="report in group.reports"
                :key="report.id"
                clickable
                tabindex="0"
                @click="openDetail(report.id)"
                @keydown="onRowKeydown($event, report.id)"
            >
                <div class="who">
                    <strong>{{ report.member_name }}</strong>
                    <span v-if="reportHeadline(report.parsed_json)">
                        {{ reportHeadline(report.parsed_json) }}
                    </span>
                </div>
                <template v-if="canManage(report)" #actions>
                    <button
                        type="button"
                        class="row-delete"
                        @click="deleteProjectReport(report.id)"
                    >
                        삭제
                    </button>
                </template>
            </AppListRow>
        </section>
    </div>
</template>

<style scoped>
.list-search {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 220px;
    gap: 8px;
    position: sticky;
    top: 8px;
    z-index: 5;
    padding: 8px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
}

.list-search .input {
    min-width: 0;
    min-height: 44px;
    font-size: 16px;
}

.list-search .input::placeholder {
    color: var(--text-muted);
    opacity: 1;
}

.list-status {
    margin: 0;
    font-size: 14px;
    color: var(--text);
}

.list-status.is-error {
    color: var(--danger-fg);
}

.day {
    margin-top: 0;
}

.day h2 {
    margin: 0 0 4px;
    font-size: 14px;
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.who {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
}

.who strong {
    font-size: 15px;
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.who span {
    font-size: 14px;
    color: var(--text);
    word-break: keep-all;
}

.row-delete {
    min-width: 44px;
    min-height: 44px;
    padding: 0 8px;
    border: 0;
    background: transparent;
    color: var(--danger-fg);
    font: inherit;
    font-size: 14px;
    cursor: pointer;
}

.row-delete:focus-visible,
.app-list-row:focus-visible,
.list-search .input:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
}

@media (max-width: 860px) {
    .list-search {
        grid-template-columns: minmax(0, 1fr);
        top: 8px;
    }
}
</style>
