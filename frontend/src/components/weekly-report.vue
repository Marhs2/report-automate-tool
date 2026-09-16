<script setup>
import { computed, onMounted, ref, watch } from "vue";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { useToast } from "../composables/useToast";
import { useDialog } from "../composables/useDialog";
import PizZip from "pizzip";
import Docxtemplater from "docxtemplater";
import { saveAs } from "file-saver";
import { Download } from "lucide-vue-next";
import { useRouter } from "vue-router";
import userActivities from "./user-activities.vue";

const router = useRouter();

const { postWeeklyReport, getWeeklyReport, deleteWeeklyReport, getUserActivities, getTeams } = useApi();
const { success: toastSuccess, error: toastError } = useToast();
const { confirm: askConfirm } = useDialog();

const selects = ref([]);
const weekDays = ref([]);
const userId = ref(selectedUserId.value || "");
const weeklyReport = ref(null);
const isLoading = ref(false);
const dayCounts = ref({});
const weekdayLabels = ["월", "화", "수", "목", "금"];
const teams = ref([]);
const filterTeam = ref("all");

const formatLocalDate = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const normalizeDay = (value) => {
    if (!value) return "";
    const text = String(value);
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
    const parsed = new Date(text);
    if (Number.isNaN(parsed.getTime())) return text.slice(0, 10);
    return formatLocalDate(parsed);
};

const dateKey = (dates) =>
    [...(dates || [])].map(normalizeDay).filter(Boolean).sort().join("|");

const weekOffset = ref(0);

const getWeekDays = (offset) => {
    const now = new Date();
    const day = now.getDay();
    const monday = new Date(now);
    monday.setDate(now.getDate() - (day === 0 ? 7 : day) + 1 + offset * 7);

    const days = [];
    for (let i = 0; i < 5; i++) {
        const d = new Date(monday);
        d.setDate(monday.getDate() + i);
        days.push(formatLocalDate(d));
    }
    return days;
};

const loadWeek = async (offset) => {
    weekOffset.value = offset;
    weekDays.value = getWeekDays(offset);
    selects.value = [...weekDays.value];
    await loadDayCounts();
};

const weekLabel = computed(() => {
    if (weekDays.value.length < 5) return "";
    const start = weekDays.value[0];
    const end = weekDays.value[4];
    const suffix = weekOffset.value === 0 ? " (이번 주)" : "";
    return `${start} ~ ${end}${suffix}`;
});

const prevWeek = () => loadWeek(weekOffset.value - 1);
const nextWeek = () => loadWeek(weekOffset.value + 1);

weekDays.value = getWeekDays(0);
selects.value = [...weekDays.value];

const deleteWeekly = async (reportId) => {
    if (!(await askConfirm("이 주간 보고서를 삭제할까요?"))) return;
    isLoading.value = true;
    try {
        await deleteWeeklyReport(reportId);
        toastSuccess("주간 보고서를 삭제했습니다.");
        await fetchWeeklyReport();
    } catch (error) {
        const detail = error.response?.data?.detail;
        console.error("주간 보고서 삭제 실패:", error);
        toastError(detail || "주간 보고서 삭제에 실패했습니다. 다시 시도해주세요.");
    } finally {
        isLoading.value = false;
    }
};

const sendDates = async () => {
    if (!userId.value) {
        toastError("사용자를 먼저 선택해주세요.");
        return;
    }
    if (selects.value.length === 0) {
        toastError("기간(날짜)을 최소 1개 선택해주세요.");
        return;
    }
    isLoading.value = true;
    try {
        await postWeeklyReport(userId.value, selects.value);
        await fetchWeeklyReport();
        toastSuccess("주간 보고서를 만들었습니다.");
        const wanted = dateKey(selects.value);
        const reports = [...(weeklyReport.value || [])];
        const created =
            reports
                .filter((report) => dateKey(report.selectedDate) === wanted)
                .sort((a, b) => Number(b.id) - Number(a.id))[0] ||
            reports.sort((a, b) => Number(b.id) - Number(a.id))[0];
        if (created?.id) {
            router.push(`/weekly-detail/${created.id}`);
            return;
        }
    } catch (error) {
        const detail = error.response?.data?.detail;
        console.error("주간 보고서 생성 실패:", error);
        toastError(detail || "주간 보고서 생성에 실패했습니다. 다시 시도해주세요.");
    } finally {
        isLoading.value = false;
    }
};

const loadDayCounts = async () => {
    dayCounts.value = {};
    if (!userId.value || weekDays.value.length < 5) return;
    try {
        const rows = await getUserActivities(
            Number(weekDays.value[0].slice(0, 4)),
            Number(weekDays.value[0].slice(5, 7)),
            weekDays.value[0],
            weekDays.value[4],
        );
        const mine = (rows || []).find(
            (row) => String(row.member_id) === String(userId.value),
        );
        const next = {};
        for (const item of mine?.activities || []) {
            next[item.report_date] = item.count || 0;
        }
        dayCounts.value = next;
        const withReports = weekDays.value.filter(
            (day) => (next[day] || 0) > 0,
        );
        selects.value = withReports;
    } catch (error) {
        console.error("날짜별 보고 수 조회 실패:", error);
    }
};

const fetchWeeklyReport = async () => {
    if (!userId.value) {
        weeklyReport.value = [];
        return;
    }
    isLoading.value = true;
    try {
        weeklyReport.value = await getWeeklyReport(userId.value);
    } catch (error) {
        console.error("주간 보고서 조회 실패:", error);
        weeklyReport.value = [];
    } finally {
        isLoading.value = false;
    }
};

const viewReport = (report) => {
    router.push(`/weekly-detail/${report.id}`);
};

const downloadReport = async (report) => {
    try {
        isLoading.value = true;

        const response = await fetch("/asset/weekly-report-template.docx");
        if (!response.ok) {
            throw new Error("템플릿 파일을 찾을 수 없습니다.");
        }
        const arrayBuffer = await response.arrayBuffer();
        const header = new Uint8Array(arrayBuffer, 0, 2);
        if (header.length < 2 || header[0] !== 0x50 || header[1] !== 0x4b) {
            throw new Error("템플릿 파일이 올바른 Word 문서가 아닙니다.");
        }

        const zip = new PizZip(arrayBuffer);
        const doc = new Docxtemplater(zip, {
            paragraphLoop: true,
            linebreaks: true,
        });

        const sortedDates = [...(report.selectedDate || [])]
            .map((d) => formatLocalDate(new Date(d)))
            .sort();
        const period_start = sortedDates[0] || "";
        const period_end = sortedDates[sortedDates.length - 1] || "";
        const selectedDateRange = period_start
            ? [`${period_start} ~ ${period_end}`]
            : [];

        const createdDateRaw =
            report.createdAt || report.created_at || new Date().toISOString();
        const created_date = formatLocalDate(new Date(createdDateRaw));

        const asReportItems = (items) => {
            const values = Array.isArray(items)
                ? items.filter((item) => {
                    if (item === null || item === undefined) return false;
                    return typeof item !== "string" || item.trim().length > 0;
                })
                : [];
            return values.length > 0 ? values : ["없음"];
        };

        const projectsList = (report.report?.projects || []).map((p) => {
            const nextPlans =
                Array.isArray(p.nextWeekPlans) && p.nextWeekPlans.length > 0
                    ? p.nextWeekPlans
                    : p.nextPlans;

            return {
                project_name: p.projectName || "",
                completed: asReportItems(p.completedTasks),
                inProgress: asReportItems(p.inProgressTasks),
                issues: asReportItems(p.issues).map((issue) => {
                    const content =
                        typeof issue === "string"
                            ? issue
                            : issue.content || "없음";
                    return { content };
                }),
                nextPlans: asReportItems(nextPlans),
            };
        });

        const project_count = projectsList.length;
        const missing = [];
        const missing_count = missing.length;



        const data = {
            selectedDate: selectedDateRange,
            created_date,
            project_count,
            missing_count,
            projects: projectsList,
            missing,
        };

        doc.render(data);

        const out = doc.getZip().generate({
            type: "blob",
            mimeType:
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        });

        const memberName = report.memberName || `사용자_${report.memberId}`;
        const filename = `주간_보고서_${memberName}_${period_end}.docx`;

        saveAs(out, filename);
    } catch (error) {
        console.error("보고서 다운로드 실패:", error);
        toastError("보고서 다운로드 중 오류가 발생했습니다: " + error.message);
    } finally {
        isLoading.value = false;
    }
};


const formatReport = (report) => {
    if (!report?.projects) return "";
    const lines = [];
    for (const project of report.projects) {
        lines.push(`[${project.projectName}]`);

        if (project.completedTasks?.length) {
            lines.push("완료된 업무:");
            for (const task of project.completedTasks) {
                lines.push(`- ${task}`);
            }
        }

        if (project.inProgressTasks?.length) {
            lines.push("진행 중인 업무:");
            for (const task of project.inProgressTasks) {
                lines.push(`- ${task}`);
            }
        }

        if (project.issues?.length) {
            lines.push("이슈:");
            for (const issue of project.issues) {
                const content =
                    typeof issue === "string" ? issue : issue.content || "";
                lines.push(`- ${content}`);
            }
        }

        if (project.nextPlans?.length) {
            lines.push("다음 계획:");
            for (const plan of project.nextPlans) {
                lines.push(`- ${plan}`);
            }
        }

        lines.push("");
    }
    return lines.join("\n").trim();
};

const copyReport = async (report) => {
    if (!report?.report) return;
    try {
        const text = formatReport(report.report);
        await navigator.clipboard.writeText(text);
        toastSuccess("보고서를 복사했습니다.");
    } catch (error) {
        console.error("복사 실패:", error);
        toastError("복사에 실패했습니다.");
    }
};


watch(
    selectedUserId,
    async (id) => {
        userId.value = id || "";
        await loadDayCounts();
        await fetchWeeklyReport();
    },
);

const fetchTeams = async () => {
    try {
        teams.value = await getTeams();
    } catch (error) {
        console.error("Error fetching teams:", error);
        toastError("팀을 불러오지 못했습니다.");
    }
};


onMounted(async () => {
    userId.value = selectedUserId.value || "";
    await loadDayCounts();
    await fetchWeeklyReport();
    await fetchTeams();
});
</script>

<template>
    <div class="page weekly-report-page">
        <div class="page-header">
            <div>
                <h1>주간 보고서</h1>
    
            </div>
        </div>

        <div class="card">
            <h2>이번 주 보고서 생성</h2>
            <div class="week-nav">
                <button class="btn btn-small" @click="prevWeek" :disabled="isLoading">
                    &lt; 이전 주
                </button>
                <span class="week-label">{{ weekLabel }}</span>
                <button class="btn btn-small" @click="nextWeek" :disabled="isLoading">
                    다음 주 &gt;
                </button>
                <button v-if="weekOffset !== 0" class="btn btn-small" @click="loadWeek(0)" :disabled="isLoading">
                    이번 주로
                </button>
            </div>
            <div class="day-grid">
                <label v-for="(dayDate, index) in weekDays" :key="index" class="day-chip">
                    <input type="checkbox" v-model="selects" :value="dayDate" />
                    <span>{{ weekdayLabels[index] }} {{ dayDate }}</span>
                    <span class="day-status" :class="dayCounts[dayDate] ? 'has-report' : 'no-report'">
                        {{ dayCounts[dayDate] ? "보고 있음" : "보고 없음" }}
                    </span>
                </label>
            </div>

            <div class="generate-bar">
                <button class="btn btn-primary" v-on:click="() => sendDates()" :disabled="isLoading">
                    {{ isLoading ? "로딩 중..." : "주간 보고서 생성" }}
                </button>
            </div>
        </div>

        <div class="week-status">
            <div class="week-status-head">
                <h2>이번 주 제출 현황</h2>
                <select
                    id="weekly-report-filter-team"
                    class="team-filter"
                    v-model="filterTeam"
                    aria-label="팀"
                    autocomplete="off"
                >
                    <option value="all">전체</option>
                    <option
                        v-for="team in teams"
                        :key="team.id"
                        :value="String(team.id)"
                    >
                        {{ team.team_name }}
                    </option>
                </select>
            </div>

            <userActivities
                :embedded="true"
                :start-date="weekDays[0] || ''"
                :end-date="weekDays[weekDays.length - 1] || ''"
                :filter-team="filterTeam"
            />
        </div>

        <div class="card">
            <h2>주간 보고서 다운로드</h2>
            <div v-if="!weeklyReport || weeklyReport.length === 0" class="empty-state">
                생성된 주간 보고서가 없습니다
            </div>
            <ul v-else class="report-list">
                <li v-for="(report, index) in weeklyReport" :key="index" class="report-list-item">
                    <div class="report-list-header">
                        <div>
                            <div class="report-user">
                                {{ report.memberName || report.memberId }}
                            </div>
                            <div class="report-dates">
                                {{ report.selectedDate?.join(", ") }}
                            </div>
                        </div>

                        <div class="report-list-actions">
                            <button type="button" class="btn" @click="() => deleteWeekly(report.id)" :disabled="isLoading">
                                삭제
                            </button>
                            <button class="btn" :disabled="isLoading" @click="viewReport(report)">
                                보기
                            </button>

                            <button class="btn" @click="() => copyReport(report)" :disabled="isLoading">
                                복사
                            </button>

                            <button class="btn" v-on:click="() => downloadReport(report)" :disabled="isLoading">
                                <Download :size="14" /> 다운로드
                            </button>
                        </div>



                    </div>
                    <ul class="report-projects">
                        <li v-for="data in report.report?.projects" :key="data.projectName">
                            {{ data.projectName }}
                        </li>
                    </ul>
                </li>
            </ul>
        </div>
    </div>
</template>

<style scoped>
.day-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 16px 0;
}

.week-nav {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 16px 0 4px;
    flex-wrap: wrap;
}

.week-label {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-h);
}

.day-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-soft);
    font-size: 13px;
    cursor: pointer;
}

.day-chip:has(input:checked) {
    border-color: var(--accent-border);
    background: var(--accent-bg);
    color: var(--text-h);
}

.day-status {
    margin-left: 4px;
    font-size: 11px;
    font-weight: 650;
}

.day-status.has-report {
    color: var(--success);
}

.day-status.no-report {
    color: var(--warning);
}

.generate-bar {
    display: flex;
    gap: 10px;
    align-items: center;
    padding-top: 16px;
    border-top: 1px solid var(--border);
}

.report-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.week-status {
    margin: 24px 0;
}

.week-status-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
}

.week-status-head h2 {
    margin: 0;
}

.team-filter {
    height: 32px;
    width: auto;
    min-width: 108px;
    max-width: 180px;
    margin-left: auto;
    padding: 0 28px 0 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    background: var(--bg);
    color: var(--text-h);
    font: inherit;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
}

.team-filter:hover {
    border-color: var(--text);
}

.team-filter:focus {
    outline: none;
    border-color: var(--text-h);
}
.report-list-item {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px 16px;
    background: var(--bg);
}
.report-list-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.day-chip {
    border-radius: var(--radius-pill);
}

.report-list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
}

.report-user {
    font-weight: 600;
    color: var(--text-h);
}

.report-dates {
    font-size: 13px;
    color: var(--text);
    margin-top: 2px;
}

.report-projects {
    list-style: disc;
    margin: 10px 0 0;
    padding-left: 20px;
    font-size: 13px;
    color: var(--text);
}
</style>
