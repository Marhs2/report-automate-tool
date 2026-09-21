<script setup>
import { computed, onMounted, ref, watch } from "vue";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { useDialog } from "../composables/useDialog";
import PizZip from "pizzip";
import Docxtemplater from "docxtemplater";
import { saveAs } from "file-saver";
import { Download } from "lucide-vue-next";
import { useRouter } from "vue-router";
import AppPageHeader from "./ui/AppPageHeader.vue";
import AppListRow from "./ui/AppListRow.vue";
import { formatDeck, projectsFromDeck, toWeeklyDeck } from "../lib/weeklyDeck";
import {
    fromDailyReport,
    weeklyHighlights,
    weeklyRollup,
    weeklyRollupLabel,
} from "../lib/standupInsights";


const router = useRouter();

const { postWeeklyReport, getWeeklyReport, deleteWeeklyReport, downloadWeeklyPptx, getUserActivities, getReports, getTeams } = useApi();
const { alert: showAlert, confirm: askConfirm } = useDialog();

const selects = ref([]);
const weekDays = ref([]);
const userId = ref(selectedUserId.value || "");
const weeklyReport = ref(null);
const isLoading = ref(false);
const dayCounts = ref({});
const weekMembers = ref([]);
const weekDailyReports = ref([]);
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

const shortDay = (dateStr) => {
    const parts = String(dateStr).split("-");
    if (parts.length < 3) return dateStr;
    return `${Number(parts[1])}.${Number(parts[2])}`;
};

const headerTitle = computed(() => {
    if (weekDays.value.length < 5) return "주간 보고서";
    return `${shortDay(weekDays.value[0])} ~ ${shortDay(weekDays.value[4])}`;
});

const isDayOn = (dayDate) => selects.value.includes(dayDate);

const toggleSelectDay = (dayDate) => {
    if (selects.value.includes(dayDate)) {
        selects.value = selects.value.filter((day) => day !== dayDate);
        return;
    }
    selects.value = weekDays.value.filter(
        (day) => day === dayDate || selects.value.includes(day),
    );
};

const reportRange = (report) => {
    const days = [...(report?.selectedDate || [])]
        .map(normalizeDay)
        .filter(Boolean)
        .sort();
    if (!days.length) return "";
    if (days.length === 1) return days[0];
    return `${days[0]} ~ ${days[days.length - 1]}`;
};


const prevWeek = () => loadWeek(weekOffset.value - 1);
const nextWeek = () => loadWeek(weekOffset.value + 1);

const statusRows = computed(() =>
    weekMembers.value
        .filter(
            (member) =>
                filterTeam.value === "all" ||
                String(member.team_id) === String(filterTeam.value),
        )
        .map((member) => {
            const byDate = new Map(
                (member.activities || []).map((item) => [
                    item.report_date,
                    item,
                ]),
            );
            const cells = weekDays.value.map((date) => {
                const item = byDate.get(date);
                return {
                    date,
                    submitted: Boolean(item?.count > 0),
                    report_id: item?.report_id,
                };
            });
            const submitted = cells.filter((cell) => cell.submitted).length;
            return {
                member_id: member.member_id,
                name: member.name,
                cells,
                submitted,
                total: cells.length,
            };
        }),
);

const weekPulse = computed(() => {
    const total = statusRows.value.length;
    const submitted = statusRows.value.filter((row) => row.submitted > 0).length;
    if (!total) return "표시할 팀원이 없습니다";
    return `이번 주 ${submitted}/${total}명 제출`;
});

const submittedRows = computed(() =>
    statusRows.value.filter((row) => row.submitted > 0),
);
const missedRows = computed(() =>
    statusRows.value.filter((row) => row.submitted === 0),
);
const missedNames = computed(() => missedRows.value.map((row) => row.name));
const memberQuery = ref("");

const visibleRows = computed(() => {
    const q = memberQuery.value.trim().toLowerCase();
    const rows = q
        ? statusRows.value.filter((row) =>
              String(row.name || "").toLowerCase().includes(q),
          )
        : statusRows.value;
    return [...rows].sort((a, b) => {
        if (a.submitted !== b.submitted) return a.submitted - b.submitted;
        return String(a.name).localeCompare(String(b.name), "ko");
    });
});

const teamDayCounts = computed(() => {
    const counts = {};
    for (const day of weekDays.value) counts[day] = 0;
    for (const row of statusRows.value) {
        for (const cell of row.cells) {
            if (cell.submitted) counts[cell.date] = (counts[cell.date] || 0) + 1;
        }
    }
    return counts;
});

const weekHighlightSource = computed(() =>
    weekDailyReports.value
        .filter(
            (row) =>
                filterTeam.value === "all" ||
                String(row.member_team_id) === String(filterTeam.value),
        )
        .map(fromDailyReport),
);

const weekHighlights = computed(() =>
    weeklyHighlights(weekHighlightSource.value),
);

const weekRollup = computed(() =>
    weeklyRollup({
        days: weekDays.value,
        dayCounts: teamDayCounts.value,
        submittedNames: submittedRows.value.map((row) => row.name),
        blockerCount: weekHighlights.value.blockers.length,
    }),
);

const rollupLabel = computed(() => weeklyRollupLabel(weekRollup.value));

const headerSubtitle = computed(() =>
    weekOffset.value === 0 ? "이번 주" : weekLabel.value,
);

const weekdayOf = (dateStr) => {
    const index = weekDays.value.indexOf(dateStr);
    return index >= 0 ? weekdayLabels[index] : dateStr;
};

const openDaily = async (row, cell) => {
    if (!cell?.submitted) return;
    let reportId = cell.report_id;
    if (!reportId) {
        try {
            const reports = await getReports();
            const found = (reports || []).find(
                (report) =>
                    String(report.member_id) === String(row.member_id) &&
                    report.report_date === cell.date,
            );
            reportId = found?.id;
        } catch (error) {
            console.error("보고서 찾기 실패:", error);
        }
    }
    if (reportId) router.push(`/report-result/${reportId}`);
};

weekDays.value = getWeekDays(0);
selects.value = [...weekDays.value];

const deleteWeekly = async (reportId) => {
    if (!(await askConfirm("이 주간 보고서를 삭제할까요?"))) return;
    isLoading.value = true;
    try {
        await deleteWeeklyReport(reportId);
        showAlert("주간 보고서를 삭제했습니다.");
        await fetchWeeklyReport();
    } catch (error) {
        const detail = error.response?.data?.detail;
        console.error("주간 보고서 삭제 실패:", error);
        showAlert(detail || "주간 보고서 삭제에 실패했습니다. 다시 시도해주세요.");
    } finally {
        isLoading.value = false;
    }
};

const sendDates = async () => {
    if (!userId.value) {
        showAlert("사용자를 먼저 선택해주세요.");
        return;
    }
    if (selects.value.length === 0) {
        showAlert("기간(날짜)을 최소 1개 선택해주세요.");
        return;
    }
    isLoading.value = true;
    try {
        await postWeeklyReport(userId.value, selects.value);
        await fetchWeeklyReport();
        showAlert("주간 보고서를 만들었습니다.");
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
        showAlert(detail || "주간 보고서 생성에 실패했습니다. 다시 시도해주세요.");
    } finally {
        isLoading.value = false;
    }
};

const loadDayCounts = async () => {
    dayCounts.value = {};
    weekMembers.value = [];
    if (weekDays.value.length < 5) return;
    try {
        const rows = await getUserActivities(
            Number(weekDays.value[0].slice(0, 4)),
            Number(weekDays.value[0].slice(5, 7)),
            weekDays.value[0],
            weekDays.value[4],
        );
        weekMembers.value = rows || [];
        const mine = (rows || []).find(
            (row) => String(row.member_id) === String(userId.value),
        );
        const next = {};
        for (const item of mine?.activities || []) {
            next[item.report_date] = item.count || 0;
        }
        dayCounts.value = next;
        if (userId.value) {
            selects.value = weekDays.value.filter(
                (day) => (next[day] || 0) > 0,
            );
        }
        loadWeekDailies();
    } catch (error) {
        console.error("날짜별 보고 수 조회 실패:", error);
    }
};

const loadWeekDailies = async () => {
    weekDailyReports.value = [];
    if (weekDays.value.length < 1) return;
    try {
        const rows = await getReports();
        const days = new Set(weekDays.value);
        weekDailyReports.value = (rows || []).filter((row) =>
            days.has(normalizeDay(row.report_date)),
        );
    } catch (error) {
        console.error("주간 일일보고 조회 실패:", error);
        weekDailyReports.value = [];
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

        const mapped = projectsFromDeck(toWeeklyDeck(report.report));
        const projectsList = (mapped.length ? mapped : report.report?.projects || []).map((p) => {
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
        showAlert("보고서 다운로드 중 오류가 발생했습니다: " + error.message);
    } finally {
        isLoading.value = false;
    }
};

const periodEndOf = (report) => {
    const sortedDates = [...(report.selectedDate || [])]
        .map((d) => formatLocalDate(new Date(d)))
        .sort();
    return sortedDates[sortedDates.length - 1] || "";
};

const downloadPptx = async (report) => {
    if (!report?.id) {
        showAlert("저장된 주간 보고서만 PPT로 받을 수 있습니다.");
        return;
    }
    isLoading.value = true;
    try {
        const blob = await downloadWeeklyPptx(report.id);
        const memberName = report.memberName || `사용자_${report.memberId}`;
        const filename = `주간_보고서_${memberName}_${periodEndOf(report)}.pptx`;
        saveAs(blob, filename);
    } catch (error) {
        console.error("PPT 다운로드 실패:", error);
        showAlert("PPT 다운로드 중 오류가 발생했습니다.");
    } finally {
        isLoading.value = false;
    }
};


const projectNamesOf = (report) => {
    const deck = toWeeklyDeck(report?.report);
    const names = [...(deck.done || []), ...(deck.next || [])]
        .map((section) => String(section.title || "").trim())
        .filter(Boolean);
    if (names.length) return [...new Set(names)];
    return (report?.report?.projects || [])
        .map((project) => project.projectName)
        .filter(Boolean);
};

const formatReport = (report) => {
    const deck = toWeeklyDeck(report);
    const text = formatDeck(deck);
    if (text) return text;
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
        showAlert("보고서를 복사했습니다.");
    } catch (error) {
        console.error("복사 실패:", error);
        showAlert("복사에 실패했습니다.");
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
        showAlert("팀을 불러오지 못했습니다.");
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
        <AppPageHeader :title="headerTitle" :subtitle="headerSubtitle">
            <template #filters>
                <div class="week-nav">
                    <button class="btn btn-small" aria-label="이전 주" @click="prevWeek" :disabled="isLoading">
                        &lt;
                    </button>
                    <button class="btn btn-small" aria-label="다음 주" @click="nextWeek" :disabled="isLoading">
                        &gt;
                    </button>
                    <button v-if="weekOffset !== 0" class="btn btn-small" @click="loadWeek(0)" :disabled="isLoading">
                        이번 주로
                    </button>
                </div>
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
            </template>
            <template #actions>
                <button class="btn btn-primary" @click="sendDates()" :disabled="isLoading || selects.length === 0">
                    {{ isLoading ? "로딩 중..." : "주간 보고서 생성" }}
                </button>
            </template>
        </AppPageHeader>

        <section class="card week-board" aria-label="이번 주">
            <div class="section-head">
                <h2>날짜 선택</h2>
                <p>{{ selects.length }}일 · 제출 {{ submittedRows.length }}/{{ statusRows.length }} · 미제출 {{ missedRows.length }}</p>
            </div>
            <div class="day-chips" role="group" aria-label="넣을 날짜">
                <button
                    v-for="(dayDate, index) in weekDays"
                    :key="dayDate"
                    type="button"
                    class="day-chip"
                    :class="{
                        on: isDayOn(dayDate),
                        has: Boolean(dayCounts[dayDate]),
                    }"
                    :aria-pressed="isDayOn(dayDate)"
                    @click="toggleSelectDay(dayDate)"
                >
                    {{ weekdayLabels[index] }} {{ shortDay(dayDate) }}
                </button>
            </div>
            <div v-if="statusRows.length === 0" class="empty-state">표시할 제출 현황이 없습니다</div>
            <template v-else>
                <input
                    class="input member-search"
                    v-model="memberQuery"
                    type="search"
                    placeholder="이름 찾기"
                    aria-label="이름 찾기"
                    autocomplete="off"
                />
                <div v-if="visibleRows.length === 0" class="week-empty-in">검색 결과가 없습니다</div>
                <div v-else class="week-table-wrap">
                    <table class="week-table">
                        <thead>
                            <tr>
                                <th>이름</th>
                                <th v-for="(dayDate, index) in weekDays" :key="dayDate">
                                    {{ weekdayLabels[index] }}
                                    <small>{{ shortDay(dayDate) }}</small>
                                </th>
                                <th>합</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="row in visibleRows" :key="row.member_id">
                                <th>{{ row.name }}</th>
                                <td v-for="cell in row.cells" :key="cell.date">
                                    <button
                                        v-if="cell.submitted"
                                        type="button"
                                        class="week-cell is-in"
                                        :aria-label="row.name + ' ' + cell.date + ' 제출'"
                                        @click="openDaily(row, cell)"
                                    >
                                        {{ weekdayOf(cell.date) }}
                                    </button>
                                    <span v-else class="week-cell is-out">—</span>
                                </td>
                                <td class="week-sum">{{ row.submitted }}/{{ row.total }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </template>
        </section>

        <section class="card week-files" aria-label="생성된 주간 보고서">
            <div class="section-head">
                <h2>생성된 보고서</h2>
                <p>{{ weeklyReport?.length || 0 }}건</p>
            </div>
            <div v-if="!weeklyReport || weeklyReport.length === 0" class="empty-state">
                생성된 주간 보고서가 없습니다
            </div>
            <ul v-else class="report-list">
                <li v-for="(report, index) in weeklyReport" :key="report.id || index" class="report-item">
                    <button type="button" class="report-main" :disabled="isLoading" @click="viewReport(report)">
                        <strong>{{ report.memberName || report.memberId }}</strong>
                        <span>{{ reportRange(report) }}</span>
                        <em v-if="projectNamesOf(report).length">{{ projectNamesOf(report).join(" · ") }}</em>
                    </button>
                    <div class="report-list-actions">
                        <button type="button" class="btn btn-small btn-primary" @click="viewReport(report)" :disabled="isLoading">보기</button>
                        <button type="button" class="btn btn-small" @click="copyReport(report)" :disabled="isLoading">복사</button>
                        <button type="button" class="btn btn-small" @click="downloadReport(report)" :disabled="isLoading">Word</button>
                        <button type="button" class="btn btn-small" @click="downloadPptx(report)" :disabled="isLoading">PPT</button>
                        <button type="button" class="btn btn-small" @click="deleteWeekly(report.id)" :disabled="isLoading">삭제</button>
                    </div>
                </li>
            </ul>
        </section>
    </div>
</template>

<style scoped>
.week-nav {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
}

.team-filter {
    height: 32px;
    width: auto;
    min-width: 108px;
    padding: 0 var(--space-6) 0 var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--text-strong);
    font: inherit;
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    cursor: pointer;
}

.team-filter:hover {
    border-color: var(--text);
}

.team-filter:focus {
    outline: none;
    border-color: var(--text-strong);
}

.weekly-report-page > .card {
    margin-bottom: var(--space-5);
}

.week-status .missing-banner {
    margin-bottom: var(--space-3);
}

.section-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
}

.section-head h2 {
    margin: 0;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.section-head p {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text);
}

.day-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: var(--space-2);
}

.day-tile {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    min-height: 76px;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--text);
    font: inherit;
    text-align: left;
    cursor: pointer;
}

.day-tile:hover {
    border-color: var(--text);
}

.day-tile.on {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--text-strong);
}

.day-tile-name {
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
}

.day-tile-date {
    font-size: var(--fs-16);
    font-weight: var(--fw-bold);
    color: var(--text-strong);
}

.day-tile-st {
    font-size: 11px;
    font-weight: var(--fw-semibold);
}

.day-tile.has .day-tile-st {
    color: var(--success-fg);
}

.day-tile:not(.has) .day-tile-st {
    color: var(--text-muted);
}

.member-search {
    width: 100%;
    max-width: 220px;
    height: 32px;
    margin-bottom: var(--space-3);
}

.week-table-wrap {
    max-height: 420px;
    overflow: auto;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
}

.week-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--fs-13);
}

.week-table th,
.week-table td {
    border-bottom: 1px solid var(--border);
    padding: 6px 8px;
    text-align: center;
    vertical-align: middle;
}

.week-table thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--surface-soft);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.week-table thead small {
    display: block;
    margin-top: 2px;
    font-size: 10px;
    font-weight: var(--fw-medium);
    color: var(--text-muted);
}

.week-table tbody th {
    position: sticky;
    left: 0;
    z-index: 1;
    background: var(--surface);
    text-align: left;
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    white-space: nowrap;
}

.week-table thead th:first-child {
    position: sticky;
    left: 0;
    z-index: 2;
    text-align: left;
}

.week-cell {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 28px;
    min-height: 24px;
    padding: 0 6px;
    border-radius: 4px;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
}

.week-cell.is-in {
    border: none;
    background: var(--success-bg);
    color: var(--success-fg);
    cursor: pointer;
    font: inherit;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
}

.week-cell.is-in:hover,
.week-cell.is-in:focus-visible {
    background: var(--success-border);
}

.week-cell.is-out {
    color: var(--text-muted);
}

.week-sum {
    color: var(--text);
    font-weight: var(--fw-medium);
    white-space: nowrap;
}

.week-empty-in,
.week-missed-count {
    margin: var(--space-3) 0 0;
    font-size: var(--fs-13);
    color: var(--text);
}

.report-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.report-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
}

.report-main {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    min-width: 0;
    margin: 0;
    padding: 0;
    border: none;
    background: transparent;
    font: inherit;
    text-align: left;
    cursor: pointer;
}

.report-main strong {
    color: var(--text-strong);
}

.report-main span,
.report-main em {
    font-size: var(--fs-12);
    font-style: normal;
    color: var(--text);
}

.report-list-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    flex-shrink: 0;
}

@media (max-width: 860px) {
    .day-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .report-row {
        flex-direction: column;
        align-items: stretch;
    }
}

.day-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
}

.day-chip {
    height: 32px;
    padding: 0 var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    background: var(--surface);
    color: var(--text);
    font: inherit;
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    cursor: pointer;
}

.day-chip:hover {
    border-color: var(--text);
}

.day-chip.on {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--text-strong);
}

.day-chip.has {
    font-weight: var(--fw-semibold);
}

.in-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.in-list li {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    min-width: 0;
}

.in-list strong {
    min-width: 4.5em;
    color: var(--text-strong);
    font-size: var(--fs-13);
}

.in-days {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
}

.in-day {
    height: 28px;
    padding: 0 var(--space-3);
    border: none;
    border-radius: 4px;
    background: var(--success-bg);
    color: var(--success-fg);
    font: inherit;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    cursor: pointer;
}

.in-day:hover,
.in-day:focus-visible {
    background: var(--success-border);
}

.in-sum {
    font-size: var(--fs-12);
    color: var(--text);
    white-space: nowrap;
}

.week-missed-count,
.week-empty-in {
    margin: var(--space-3) 0 0;
    font-size: var(--fs-13);
    color: var(--text);
}

.report-item {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
}

.report-main {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    min-width: 0;
    margin: 0;
    padding: 0;
    border: none;
    background: transparent;
    font: inherit;
    text-align: left;
    cursor: pointer;
}

.report-main strong {
    color: var(--text-strong);
}

.report-main span,
.report-main em {
    font-size: var(--fs-12);
    font-style: normal;
    color: var(--text);
}

.report-list-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-left: 0;
}
</style>
