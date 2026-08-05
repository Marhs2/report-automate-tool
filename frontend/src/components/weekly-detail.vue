<template>
    <div class="page">
        <div class="page-header">
            <div>
                <h1>주간 요약</h1>
            </div>
        </div>

        <div v-if="reportData" class="content-container">
            <div class="json-container">
                <div
                    v-for="(project, projectIndex) in reportData.projects"
                    :key="project.projectName || projectIndex"
                    class="card projects-container"
                >
                    <input
                        class="input project-name-input"
                        v-model="project.projectName"
                    />

                    <div class="field-group completedTasks">
                        <h2>완료된 업무</h2>
                        <div
                            v-if="project.completedTasks.length > 0"
                            v-for="(task, taskIndex) in project.completedTasks"
                            :key="`completed-${taskIndex}`"
                            class="task-row"
                        >
                            <input
                                class="input"
                                v-model="project.completedTasks[taskIndex]"
                            />
                            <button
                                class="btn remove-btn"
                                @click="
                                    removeItem(project, 'completedTasks', taskIndex)
                                "
                            >
                                -
                            </button>
                        </div>
                        <div v-else class="empty-msg">완료된 업무가 없습니다</div>
                        <button
                            class="btn add-btn"
                            @click="addItem(project, 'completedTasks')"
                        >
                            +
                        </button>
                    </div>

                    <div class="field-group inProgressTasks">
                        <h2>진행 중인 업무</h2>
                        <div
                            v-if="project.inProgressTasks.length > 0"
                            v-for="(task, taskIndex) in project.inProgressTasks"
                            :key="`progress-${taskIndex}`"
                            class="task-row"
                        >
                            <input
                                class="input"
                                v-model="project.inProgressTasks[taskIndex]"
                            />
                            <button
                                class="btn remove-btn"
                                @click="
                                    removeItem(project, 'inProgressTasks', taskIndex)
                                "
                            >
                                -
                            </button>
                        </div>
                        <div v-else class="empty-msg">진행 중인 업무가 없습니다</div>
                        <button
                            class="btn add-btn"
                            @click="addItem(project, 'inProgressTasks')"
                        >
                            +
                        </button>
                    </div>

                    <div class="field-group issues">
                        <h2>이슈</h2>
                        <template v-if="project.issues.length > 0">
                            <div
                                v-for="(issue, issueIndex) in project.issues"
                                :key="`issue-${issueIndex}`"
                                class="issue-row"
                            >
                                <input
                                    class="input"
                                    :value="issueText(issue)"
                                    @input="
                                        (e) => setIssueContent(issue, e.target.value)
                                    "
                                />
                                <select
                                    class="input issue-status-select"
                                    :value="issueStatus(issue)"
                                    @change="
                                        (e) => setIssueStatus(issue, e.target.value)
                                    "
                                >
                                    <option value="미해결">미해결</option>
                                    <option value="해결">해결</option>
                                </select>
                                <button
                                    class="btn remove-btn"
                                    @click="removeItem(project, 'issues', issueIndex)"
                                >
                                    -
                                </button>
                            </div>
                        </template>
                        <div v-else class="empty-msg">이슈가 없습니다</div>
                        <button class="btn add-btn" @click="addIssue(project)">
                            +
                        </button>
                    </div>

                    <div class="field-group nextPlans">
                        <h2>다음 주 계획</h2>
                        <div
                            v-if="project.nextPlans.length > 0"
                            v-for="(plan, planIndex) in project.nextPlans"
                            :key="`plan-${planIndex}`"
                            class="task-row"
                        >
                            <input
                                class="input"
                                v-model="project.nextPlans[planIndex]"
                            />
                            <button
                                class="btn remove-btn"
                                @click="removeItem(project, 'nextPlans', planIndex)"
                            >
                                -
                            </button>
                        </div>
                        <div v-else class="empty-msg">다음 주 계획이 없습니다</div>
                        <button class="btn add-btn" @click="addItem(project, 'nextPlans')">
                            +
                        </button>
                    </div>
                </div>

                <div class="card save-bar">
                    <span class="member-id-display"
                        >사용자: {{ userName }}</span
                    >
                    <div class="save-actions">
                        <button class="btn" @click="copyReport" :disabled="isSaving">
                            복사
                        </button>
                        <button class="btn btn-primary" @click="saveReport" :disabled="isSaving">
                            {{ isSaving ? "저장 중..." : "저장" }}
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div v-else class="empty-state">보고서 데이터가 없습니다.</div>
    </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import useAPI from "../composables/useAPI";
import { useRoute } from "vue-router";

const route = useRoute();

const reportData = ref(null);
const rawData = ref(null);
const userName = ref("");
const isSaving = ref(false);
const { getUsers, GetWeeklyReportById, updateWeeklyReport } = useAPI();

watch(
    reportData,
    (newVal) => {
        if (newVal) {
            sessionStorage.setItem("reportData", JSON.stringify(newVal));
        }
    },
    { deep: true },
);

onMounted(async () => {
    const reportId = route.params.id;

    if (reportId) {
        try {
            const data = await GetWeeklyReportById(reportId);
            reportData.value = data.report;
            rawData.value = null;
            userName.value = data.memberName || `사용자 ${data.memberId}`;

            sessionStorage.setItem("reportData", JSON.stringify(data.report));
            sessionStorage.setItem("selectedUser", String(data.memberId));
            if (data.createdAt) {
                sessionStorage.setItem(
                    "reportDate",
                    new Date(data.createdAt).toISOString().split("T")[0],
                );
            }
        } catch (error) {
            console.error("보고서 불러오기 실패:", error);
            alert("보고서를 불러오는데 실패했습니다.");
        }
        return;
    }

    const stored = sessionStorage.getItem("reportData");

    if (stored) {
        reportData.value = JSON.parse(stored);
    }

    const storedRaw = sessionStorage.getItem("reportRaw");

    if (storedRaw) {
        rawData.value = storedRaw;
    }

    console.log("Loaded report data:", reportData.value);

    const userId = localStorage.getItem("report-selectedUser") || "";
    if (userId) {
        getUsers()
            .then((users) => {
                const found = users.find(
                    (u) => String(u.id) === String(userId),
                );
                userName.value = found ? found.name : `사용자 ${userId}`;
            })
            .catch(() => {
                userName.value = `사용자 ${userId}`;
            });
    }
});

const issueText = (issue) =>
    typeof issue === "string" ? issue : (issue?.content ?? "");

const issueStatus = (issue) =>
    typeof issue === "string" ? "미해결" : (issue?.status ?? "미해결");

const setIssueContent = (issue, value) => {
    if (typeof issue === "object") {
        issue.content = value;
    }
};

const setIssueStatus = (issue, value) => {
    if (typeof issue === "object") {
        issue.status = value;
    }
};

const addItem = (project, field) => {
    project[field].push("");
};

const addIssue = (project) => {
    project.issues.push({ content: "", status: "미해결" });
};

const removeItem = (project, field, index) => {
    project[field].splice(index, 1);
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

const copyReport = async () => {
    if (!reportData.value) return;
    try {
        const text = formatReport(reportData.value);
        await navigator.clipboard.writeText(text);
        alert("보고서가 클립보드에 복사되었습니다.");
    } catch (error) {
        console.error("복사 실패:", error);
        alert("복사에 실패했습니다.");
    }
};

const saveReport = async () => {
    if (!reportData.value) return;
    const reportId = route.params.id;
    if (!reportId) {
        alert("저장할 주간 보고서 ID가 없습니다.");
        return;
    }
    isSaving.value = true;
    try {
        await updateWeeklyReport(reportId, JSON.stringify(reportData.value));
        alert("주간 보고서가 저장되었습니다.");
    } catch (error) {
        console.error("저장 실패:", error);
        alert("주간 보고서 저장에 실패했습니다.");
    } finally {
        isSaving.value = false;
    }
};
</script>

<style scoped>
/* 전체 레이아웃 (편집기와 원본 보고서 좌우 정렬) */
.content-container {
    display: flex;
    gap: 24px;
    align-items: flex-start;
}

/* 왼쪽 편집 폼 영역 */
.json-container {
    flex: 2;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 20px;
}

/* 오른쪽 원본 보고서 영역 (스크롤 고정) */
.raw-container {
    flex: 1;
    min-width: 0;
    position: sticky;
    top: 32px;
}

.raw-container h2 {
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}

.raw-container pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
    font-size: 13px;
    line-height: 1.5;
    max-height: 80vh;
    overflow-y: auto;
    color: var(--text);
}

/* 개별 프로젝트 카드 */
.projects-container {
    display: flex;
    flex-direction: column;
}

/* 프로젝트명 입력창 */
.project-name-input {
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 16px;
    color: var(--text-h);
}

/* 각 업무/이슈/요청/계획 박스 레이아웃 */
.field-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
    border: 1px solid var(--border);
    background: var(--bg-soft);
    padding: 14px 16px;
    border-radius: var(--radius-sm);
}

.field-group:last-of-type {
    margin-bottom: 0;
}

.field-group h2 {
    margin: 0 0 4px;
    font-size: 13px;
    color: var(--text);
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

.field-group .empty-msg {
    font-size: 13px;
    color: var(--text);
    font-style: italic;
    opacity: 0.7;
}

/* 추가 (+) 버튼 */
.add-btn {
    align-self: flex-start;
    padding: 5px 14px;
    font-size: 13px;
}

/* 항목 행 (입력 + 삭제 버튼) */
.task-row {
    display: flex;
    align-items: center;
    gap: 8px;
}

.task-row .input {
    flex: 1;
    min-width: 0;
}

.remove-btn {
    flex-shrink: 0;
    padding: 5px 10px;
    font-size: 13px;
}

.issue-row {
    display: flex;
    align-items: center;
    gap: 8px;
}

.issue-row .input:first-child {
    flex: 1;
    min-width: 0;
}

.issue-status-select {
    flex-shrink: 0;
    max-width: 110px;
}

/* 하단 저장 영역 */
.save-bar {
    display: flex;
    gap: 12px;
    align-items: center;
}

.save-bar .member-id-display {
    font-size: 14px;
    color: var(--text-h);
}

.save-actions {
    display: flex;
    gap: 8px;
    margin-left: auto;
}
</style>
