<script setup>
import { computed, onMounted, ref } from "vue";
import useAPI from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import PizZip from "pizzip";
import Docxtemplater from "docxtemplater";
import { saveAs } from "file-saver";
import { Download } from "lucide-vue-next";
import { useRouter } from "vue-router";
import userActivities from "./user-activities.vue";

const router = useRouter();

const { postWeekly, GetWeeklyReport, deleteWeeklyReport } = useAPI();

const selects = ref([]);
const weekDays = ref([]);
const userId = ref(selectedUserId.value || "");
const weeklyReport = ref(null);
const isLoading = ref(false);

const formatLocalDate = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

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

const loadWeek = (offset) => {
    weekOffset.value = offset;
    weekDays.value = getWeekDays(offset);
    selects.value = [...weekDays.value];
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

loadWeek(0);

const deleteWeekly = async (reportId) => {
    isLoading.value = true;
    try {
        await deleteWeeklyReport(reportId);
        alert("삭제완료");

        await fetchWeeklyReport();
        
    } catch (error) {
        const detail = error.response?.data?.detail;
        console.error("주간 보고서 삭제 실패:", error);
        alert(detail || "주간 보고서 삭제에 실패했습니다. 다시 시도해주세요.");
    } finally {
        isLoading.value = false;
    }
};

const sendDates = async () => {
    if (!userId.value) {
        alert("사용자를 먼저 선택해주세요.");
        return;
    }
    if (selects.value.length === 0) {
        alert("기간(날짜)을 최소 1개 선택해주세요.");
        return;
    }
    isLoading.value = true;
    try {
        await postWeekly(userId.value, selects.value);
        await fetchWeeklyReport();
        alert("생성완료");
    } catch (error) {
        const detail = error.response?.data?.detail;
        console.error("주간 보고서 생성 실패:", error);
        alert(detail || "주간 보고서 생성에 실패했습니다. 다시 시도해주세요.");
    } finally {
        isLoading.value = false;
    }
};

const fetchWeeklyReport = async () => {
    isLoading.value = true;
    const response = await GetWeeklyReport(userId.value);
    weeklyReport.value = response;
    isLoading.value = false;
};

const viewReport = (report) => {
    router.push(`/weekly-detail/${report.id}`);
};

const downloadReport = async (report) => {
    try {
        isLoading.value = true;

        const response = await fetch("/asset/주간_보고서_템플릿.docx");
        if (!response.ok) {
            throw new Error("템플릿 파일을 찾을 수 없습니다.");
        }
        const arrayBuffer = await response.arrayBuffer();

        const zip = new PizZip(arrayBuffer);
        const doc = new Docxtemplater(zip, {
            paragraphLoop: true,
            linebreaks: true,
        });

        const sortedDates = [...(report.selectedDate || [])].sort();
        const period_end = sortedDates[sortedDates.length - 1] || "";

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
                    if (typeof issue === "string") {
                        return {
                            content: issue,
                            resolved: false,
                        };
                    }
                    return {
                        content: issue.content || "없음",
                        resolved: issue.status === "해결",
                    };
                }),
                nextPlans: asReportItems(nextPlans),
            };
        });

        const project_count = projectsList.length;
        const missing = [];
        const missing_count = missing.length;

        const data = {
            selectedDate: report.selectedDate,
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
        alert("보고서 다운로드 중 오류가 발생했습니다: " + error.message);
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
                const status =
                    typeof issue === "string"
                        ? "미해결"
                        : issue.status || "미해결";
                lines.push(`- ${content} (${status})`);
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
        alert("보고서가 클립보드에 복사되었습니다.");
    } catch (error) {
        console.error("복사 실패:", error);
        alert("복사에 실패했습니다.");
    }
};


onMounted(() => {
    userId.value = selectedUserId.value || "";
    fetchWeeklyReport();
});
</script>

<template>
    <div class="page weekly-report-page">
        <userActivities
            :embedded="true"
            :start-date="weekDays[0] || ''"
            :end-date="weekDays[weekDays.length - 1] || ''"
        ></userActivities>
        <div class="page-header">
            <div>
                <h1>주간 보고서</h1>
                <p class="page-subtitle">
                    이번 주 보고서를 생성하고, 완료된 보고서를 다운로드하세요
                </p>
            </div>
        </div>

        <div class="card">
            <h2>이번 주 보고서 생성</h2>
            <div class="week-nav">
                <button
                    class="btn btn-small"
                    @click="prevWeek"
                    :disabled="isLoading"
                >
                    &lt; 이전 주
                </button>
                <span class="week-label">{{ weekLabel }}</span>
                <button
                    class="btn btn-small"
                    @click="nextWeek"
                    :disabled="isLoading"
                >
                    다음 주 &gt;
                </button>
                <button
                    v-if="weekOffset !== 0"
                    class="btn btn-small"
                    @click="loadWeek(0)"
                    :disabled="isLoading"
                >
                    이번 주로
                </button>
            </div>
            <div class="day-grid">
                <label
                    v-for="(dayDate, index) in weekDays"
                    :key="index"
                    class="day-chip"
                >
                    <input type="checkbox" v-model="selects" :value="dayDate" />
                    <span>{{ dayDate }}</span>
                </label>
            </div>

            <div class="generate-bar">
                <button
                    class="btn btn-primary"
                    v-on:click="() => sendDates()"
                    :disabled="isLoading"
                >
                    {{ isLoading ? "로딩 중..." : "주간 보고서 생성" }}
                </button>
            </div>
        </div>

        <div class="card">
            <h2>주간 보고서 다운로드</h2>
            <div
                v-if="!weeklyReport || weeklyReport.length === 0"
                class="empty-state"
            >
                생성된 주간 보고서가 없습니다
            </div>
            <ul v-else class="report-list">
                <li
                    v-for="(report, index) in weeklyReport"
                    :key="index"
                    class="report-list-item"
                >
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
                            <button
                            class="btn"
                            @click="() => deleteWeekly(report.id)"
                        >
                            삭제
                        </button>
                        <button
                            class="btn"
                            :disabled="isLoading"
                            @click="viewReport(report)"
                        >
                            보기
                        </button>

                        <button class="btn" @click="() => copyReport(report)">
                            복사
                        </button>

                        <button
                            class="btn"
                            v-on:click="() => downloadReport(report)"
                            :disabled="isLoading"
                        >
                            <Download :size="14" /> 다운로드
                        </button>
                        </div>

             

                    </div>
                    <ul class="report-projects">
                        <li
                            v-for="data in report.report?.projects"
                            :key="data.projectName"
                        >
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

.report-list-item {
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 14px 16px;
    background: var(--bg-soft);
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
