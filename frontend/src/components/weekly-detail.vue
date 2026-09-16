<template>
    <div class="page report-doc is-wide">
        <AppPageHeader :title="userName || '주간 요약'" subtitle="주간 보고서">
            <template #actions>
                <button type="button" class="btn btn-small" @click="goBack">목록</button>
            </template>
        </AppPageHeader>

        <div v-if="reportData" class="content-container single">
            <div class="json-container">
                <div v-for="(project, projectIndex) in reportData.projects" :key="project._uid || projectIndex"
                    class="card projects-container">
                    <div class="project-head">
                        <input class="input project-name-input" v-model="project.projectName" />
                        <button class="btn btn-danger" @click="removeProject(project)">
                            삭제
                        </button>
                    </div>



                    <div class="field-group completedTasks">
                        <h2>완료된 업무</h2>
                        <div v-if="project.completedTasks.length > 0"
                            v-for="(task, taskIndex) in project.completedTasks" :key="`completed-${taskIndex}`"
                            class="task-row">
                            <input class="input" v-model="project.completedTasks[taskIndex]" />
                            <button class="btn remove-btn" @click="
                                removeItem(project, 'completedTasks', taskIndex)
                                ">
                                -
                            </button>
                        </div>
                        <div v-else class="empty-msg">완료된 업무가 없습니다</div>
                        <button class="btn add-btn" @click="addItem(project, 'completedTasks')">
                            +
                        </button>
                    </div>

                    <div class="field-group inProgressTasks">
                        <h2>진행 중인 업무</h2>
                        <div v-if="project.inProgressTasks.length > 0"
                            v-for="(task, taskIndex) in project.inProgressTasks" :key="`progress-${taskIndex}`"
                            class="task-row">
                            <input class="input" v-model="project.inProgressTasks[taskIndex]" />
                            <button class="btn remove-btn" @click="
                                removeItem(project, 'inProgressTasks', taskIndex)
                                ">
                                -
                            </button>
                        </div>
                        <div v-else class="empty-msg">진행 중인 업무가 없습니다</div>
                        <button class="btn add-btn" @click="addItem(project, 'inProgressTasks')">
                            +
                        </button>
                    </div>

                    <div class="field-group issues">
                        <h2>이슈</h2>
                        <div v-if="project.issues.length > 0" v-for="(issue, issueIndex) in project.issues"
                            :key="`issue-${issueIndex}`" class="task-row">
                            <input class="input" v-model="project.issues[issueIndex]" />
                            <button class="btn remove-btn" @click="removeItem(project, 'issues', issueIndex)">
                                -
                            </button>
                        </div>
                        <div v-else class="empty-msg">이슈가 없습니다</div>
                        <button class="btn add-btn" @click="addItem(project, 'issues')">
                            +
                        </button>
                    </div>

                    <div class="field-group nextPlans">
                        <h2>다음 주 계획</h2>
                        <div v-if="project.nextPlans.length > 0" v-for="(plan, planIndex) in project.nextPlans"
                            :key="`plan-${planIndex}`" class="task-row">
                            <input class="input" v-model="project.nextPlans[planIndex]" />
                            <button class="btn remove-btn" @click="removeItem(project, 'nextPlans', planIndex)">
                                -
                            </button>
                        </div>
                        <div v-else class="empty-msg">다음 주 계획이 없습니다</div>
                        <button class="btn add-btn" @click="addItem(project, 'nextPlans')">
                            +
                        </button>
                    </div>


                </div>
                <button class="btn" @click="addProject">추가</button>


                <div class="card save-bar">
                    <span class="member-id-display">사용자: {{ userName }}</span>
                    <div class="save-actions">
                        <p v-if="confirmQuestions.length" class="confirm-hint">
                            저장 시 확인 질문 {{ confirmQuestions.length }}개
                        </p>
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
import { computed, ref, onMounted, watch } from "vue";
import useApi from "../composables/useApi";
import { useRoute, useRouter } from "vue-router";
import { useDialog } from "../composables/useDialog";
import AppPageHeader from "./ui/AppPageHeader.vue";

const route = useRoute();
const router = useRouter();
const goBack = () => router.push("/weekly");
const removeProject = (project) => {
    if (!reportData.value?.projects) return;
    reportData.value.projects = reportData.value.projects.filter((p) => p !== project);
};

const reportData = ref(null);
const userName = ref("");
const isSaving = ref(false);
const { getUsers, getWeeklyReportById, updateWeeklyReport } = useApi();
const { alert: showAlert, confirm: askConfirm } = useDialog();

const confirmQuestions = computed(() => {
    const items = reportData.value?.confirmQuestions;
    if (!Array.isArray(items)) return [];
    return items
        .map((item, index) => ({
            id: item?.id || `q-${index}`,
            text: String(item?.text || "").trim(),
            ifNo: String(item?.ifNo || "").trim(),
        }))
        .filter((item) => item.text)
        .slice(0, 3);
});

const issueText = (issue) =>
    typeof issue === "string"
        ? issue.trim()
        : String(issue?.content || "").trim();

const normalizeReportIssues = (report) => {
    if (!report?.projects) return report;
    for (const project of report.projects) {
        if (!Array.isArray(project.nextPlans) || project.nextPlans.length === 0) {
            const weeklyPlans = (project.nextWeekPlans || []).filter((plan) =>
                String(plan || "").trim(),
            );
            if (weeklyPlans.length) project.nextPlans = weeklyPlans;
            else project.nextPlans = [];
        }
        const completed = [...(project.completedTasks || [])].filter((task) =>
            String(task || "").trim(),
        );
        const remaining = [];
        const seen = new Set();
        for (const issue of project.issues || []) {
            const content = issueText(issue);
            if (!content) continue;
            const status =
                issue && typeof issue === "object" ? issue.status : "";
            if (status === "해결") {
                if (!completed.includes(content)) completed.push(content);
                continue;
            }
            if (completed.includes(content) || seen.has(content)) continue;
            remaining.push(content);
            seen.add(content);
        }
        project.completedTasks = completed;
        project.issues = remaining;
    }
    return report;
};

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
            const data = await getWeeklyReportById(reportId);
            reportData.value = normalizeReportIssues(data.report);
            userName.value = data.memberName || `사용자 ${data.memberId}`;

            sessionStorage.setItem("reportData", JSON.stringify(reportData.value));
            sessionStorage.setItem("selectedUser", String(data.memberId));
            if (data.createdAt) {
                sessionStorage.setItem(
                    "reportDate",
                    new Date(data.createdAt).toISOString().split("T")[0],
                );
            }
        } catch (error) {
            console.error("보고서 불러오기 실패:", error);
            showAlert("보고서를 불러오는데 실패했습니다.");
        }
        return;
    }

    const stored = sessionStorage.getItem("reportData");

    if (stored) {
        reportData.value = normalizeReportIssues(JSON.parse(stored));
    }

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


const addProject = () => {
    reportData.value.projects.push({
        projectName: "",
        completedTasks: [],
        inProgressTasks: [],
        issues: [],
        nextPlans: [],
    });
};

const addItem = (project, field) => {
    project[field].push("");
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

const copyReport = async () => {
    if (!reportData.value) return;
    try {
        const text = formatReport(reportData.value);
        await navigator.clipboard.writeText(text);
        showAlert("보고서가 클립보드에 복사되었습니다.");
    } catch (error) {
        console.error("복사 실패:", error);
        showAlert("복사에 실패했습니다.");
    }
};

const persistReport = async () => {
    const reportId = route.params.id;
    isSaving.value = true;
    try {
        await updateWeeklyReport(reportId, JSON.stringify(reportData.value));
        showAlert("주간 보고서가 저장되었습니다.");
    } catch (error) {
        console.error("저장 실패:", error);
        showAlert("주간 보고서 저장에 실패했습니다.");
    } finally {
        isSaving.value = false;
    }
};

const saveReport = async () => {
    if (!reportData.value) return;
    const reportId = route.params.id;
    if (!reportId) {
        showAlert("저장할 주간 보고서 ID가 없습니다.");
        return;
    }
    const questions = confirmQuestions.value;
    for (const [index, question] of questions.entries()) {
        const ok = await askConfirm(question.text, {
            title: `저장 전 확인 ${index + 1}/${questions.length}`,
            help: "아니요면 해당 항목을 고친 뒤 다시 저장하세요.",
            confirmLabel: "네",
            cancelLabel: "아니요",
        });
        if (!ok) return;
    }
    await persistReport();
};
</script>

<style scoped>
/* display/gap/margin-left은 report-doc.css의 .report-doc .save-actions가 제공한다 */
.save-actions {
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
}

.confirm-hint {
    margin: 0;
    margin-right: auto;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--accent);
}
</style>
