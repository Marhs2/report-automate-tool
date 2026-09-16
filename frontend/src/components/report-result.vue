<template>
    <div class="page report-doc">
        <div class="page-header">
            <div>
                <h1 class="detail-title">{{ userName || "분석 결과" }}</h1>
                <p class="page-subtitle">{{ reportDate || "날짜 없음" }}</p>
            </div>
        </div>
        <div class="status-banner">
            <span>작성자 <strong>{{ userName || "미선택" }}</strong></span>
            <span>날짜 <strong>{{ reportDate }}</strong></span>
            <span v-if="savedReportId" class="status-chip">저장됨</span>
            <span v-else class="status-chip is-draft">아직 저장 전</span>
            <div class="save-actions">
                <button class="btn" @click="retryExtract" :disabled="aiLoading">
                    {{ aiLoading ? "재추출 중..." : "재추출" }}
                </button>
                <button class="btn btn-primary" @click="saveReport" :disabled="aiLoading || saving">
                    {{ saving ? "저장 중..." : savedReportId ? "수정 저장" : "저장하기" }}
                </button>
            </div>
        </div>

        <div v-if="isLoading" class="empty-state">불러오는 중...</div>

        <div v-else-if="reportData" class="content-container">
            <div class="json-container">
                <div
                    v-for="(project, projectIndex) in reportData.projects"
                    :key="project._uid || projectIndex"
                    class="card projects-container"
                >
                    <div class="project-head">
                        <input
                            class="input project-name-input"
                            v-model="project.projectName"
                        />
                        <button
                            class="btn btn-danger"
                            @click="removeProject(projectIndex)"
                        >
                            삭제
                        </button>
                    </div>

                    <div class="field-group completedTasks">
                        <h2>완료된 업무</h2>
                        <div
                            v-if="project.completedTasks.length > 0"
                            v-for="(task, taskIndex) in project.completedTasks"
                            class="task-row"
                        >
                            <input
                                :key="`completed-${taskIndex}`"
                                class="input"
                                :value="task"
                                v-model="project.completedTasks[taskIndex]"
                            />
                            <button
                                class="btn remove-btn"
                                @click="removeCompletedTask(project, taskIndex)"
                            >
                                -
                            </button>
                        </div>

                        <div v-else class="empty-msg">
                            완료된 업무가 없습니다
                        </div>
                        <button
                            class="btn add-btn"
                            @click="addCompletedTask(project)"
                        >
                            +
                        </button>
                    </div>

                    <div class="field-group inProgressTasks">
                        <h2>진행 중인 업무</h2>
                        <div
                            v-if="project.inProgressTasks.length > 0"
                            v-for="(task, taskIndex) in project.inProgressTasks"
                            class="task-row"
                        >
                            <input
                                :key="`progress-${taskIndex}`"
                                class="input"
                                :value="task"
                                v-model="project.inProgressTasks[taskIndex]"
                            />
                            <button
                                class="btn remove-btn"
                                @click="
                                    removeInProgressTask(project, taskIndex)
                                "
                            >
                                -
                            </button>
                        </div>

                        <div v-else class="empty-msg">
                            진행 중인 업무가 없습니다
                        </div>

                        <button
                            class="btn add-btn"
                            @click="addInProgressTask(project)"
                        >
                            +
                        </button>
                    </div>

                    <div class="field-group issues">
                        <h2>이슈</h2>
                        <div
                            v-if="project.issues.length > 0"
                            v-for="(issue, issueIndex) in project.issues"
                            class="task-row"
                        >
                            <input
                                :key="`issue-${issueIndex}`"
                                class="input"
                                v-model="project.issues[issueIndex]"
                            />
                            <button
                                class="btn remove-btn"
                                @click="removeIssue(project, issueIndex)"
                            >
                                -
                            </button>
                        </div>

                        <div v-else class="empty-msg">이슈가 없습니다</div>
                        <button class="btn add-btn" @click="addIssue(project)">
                            +
                        </button>
                    </div>

                    <div class="field-group requests">
                        <h2>요청사항</h2>
                        <div
                            v-if="project.requests.length > 0"
                            v-for="(request, requestIndex) in project.requests"
                            class="task-row"
                        >
                            <input
                                :key="`request-${requestIndex}`"
                                class="input"
                                :value="request"
                                v-model="project.requests[requestIndex]"
                            />
                            <button
                                class="btn remove-btn"
                                @click="removeRequest(project, requestIndex)"
                            >
                                -
                            </button>
                        </div>
                        <div v-else class="empty-msg">요청사항이 없습니다</div>
                        <button
                            class="btn add-btn"
                            @click="addRequest(project)"
                        >
                            +
                        </button>
                    </div>

                    <div class="field-group nextPlans">
                        <h2>다음 계획</h2>
                        <div
                            v-if="project.nextPlans.length > 0"
                            v-for="(plan, planIndex) in project.nextPlans"
                            class="task-row"
                        >
                            <input
                                :key="`plan-${planIndex}`"
                                class="input"
                                :value="plan"
                                v-model="project.nextPlans[planIndex]"
                            />
                            <button
                                class="btn remove-btn"
                                @click="removeNextPlan(project, planIndex)"
                            >
                                -
                            </button>
                        </div>

                        <div v-else class="empty-msg">다음 계획이 없습니다</div>
                        <button
                            class="btn add-btn"
                            @click="addNextPlan(project)"
                        >
                            +
                        </button>
                    </div>
                </div>

                <button class="btn" @click="addProject">추가</button>

                <div class="card save-bar">
                    <div class="save-actions">
                        <button
                            class="btn btn-primary"
                            @click="saveReport"
                            :disabled="aiLoading || saving"
                        >
                            {{ saving ? "저장 중..." : savedReportId ? "수정 저장" : "저장하기" }}
                        </button>
                    </div>
                </div>
            </div>

            <div class="card raw-container">
                <h2>원본 보고서</h2>
                <pre class="raw-content">{{ rawData }}</pre>
            </div>
        </div>

        <div v-else class="empty-state">
            보고서 데이터가 없습니다. 보고서를 먼저 제출해주세요.
        </div>
    </div>
</template>

<script setup>
import { ref, watch } from "vue";
import useApi from "../composables/useApi";
import { useRoute, useRouter } from "vue-router";
import { useToast } from "../composables/useToast";

const route = useRoute();
const router = useRouter();
const { success: toastSuccess, error: toastError } = useToast();

const reportData = ref(null);
const rawData = ref(null);
const userName = ref("");
const reportDate = ref("");
const aiLoading = ref(false);
const saving = ref(false);
const isLoading = ref(false);
const savedReportId = ref(null);
const savedMemberId = ref(null);
const { postSaveReport, postReport, getUsers, getReportById } = useApi();

const issueText = (issue) =>
    typeof issue === "string"
        ? issue.trim()
        : String(issue?.content || "").trim();

const normalizeReportIssues = (report) => {
    if (!report?.projects) return report;
    for (const project of report.projects) {
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
        if (savedReportId.value || !newVal) return;
        sessionStorage.setItem("reportData", JSON.stringify(newVal));
    },
    { deep: true },
);

const asText = (value) =>
    value && typeof value === "object"
        ? String(value.content ?? "").trim()
        : String(value ?? "");

const asTexts = (list) =>
    (Array.isArray(list) ? list : []).map(asText);

const toEditable = (parsed) => {
    if (!parsed) return null;
    const data =
        typeof parsed === "string" ? JSON.parse(parsed) : { ...parsed };
    data.projects = (data.projects || []).map((project) => ({
        projectName: project.projectName || "",
        completedTasks: asTexts(project.completedTasks),
        inProgressTasks: asTexts(project.inProgressTasks),
        issues: asTexts(project.issues),
        requests: asTexts(project.requests),
        nextPlans: asTexts(project.nextPlans),
    }));
    return data;
};

const resolveUserName = async (userId) => {
    if (!userId) {
        userName.value = "";
        return;
    }
    try {
        const users = await getUsers();
        const found = users.find((user) => String(user.id) === String(userId));
        userName.value = found ? found.name : `사용자 ${userId}`;
    } catch {
        userName.value = `사용자 ${userId}`;
    }
};

const loadDraft = () => {
    savedReportId.value = null;
    savedMemberId.value = null;
    const stored = sessionStorage.getItem("reportData");
    reportData.value = stored
        ? normalizeReportIssues(toEditable(JSON.parse(stored)))
        : null;
    rawData.value = sessionStorage.getItem("reportRaw") || "";
    reportDate.value = sessionStorage.getItem("reportDate") || "";
    resolveUserName(localStorage.getItem("report-selectedUser") || "");
};

const loadSaved = async (id) => {
    isLoading.value = true;
    savedReportId.value = id;
    reportData.value = null;
    try {
        const data = await getReportById(id);
        savedMemberId.value = data.member_id;
        reportData.value = normalizeReportIssues(toEditable(data.parsed_json));
        rawData.value = data.raw_text || "";
        reportDate.value = data.report_date || "";
        await resolveUserName(data.member_id);
        document.title = `${userName.value || "일일보고"} · 일일보고`;
    } catch (error) {
        console.error("보고서 불러오기 실패:", error);
        toastError("보고서를 불러오지 못했습니다.");
        reportData.value = null;
    } finally {
        isLoading.value = false;
    }
};

watch(
    () => route.params.id,
    (id) => {
        if (id) loadSaved(id);
        else loadDraft();
    },
    { immediate: true },
);

const addProject = () => {
    reportData.value.projects.push({
        projectName: "",
        completedTasks: [],
        inProgressTasks: [],
        issues: [],
        requests: [],
        nextPlans: [],
    });
};

const removeProject = (index) => {
    reportData.value.projects.splice(index, 1);
};

const addCompletedTask = (project) => {
    project.completedTasks.push("");
};

const removeCompletedTask = (project, index) => {
    project.completedTasks.splice(index, 1);
};

const addInProgressTask = (project) => {
    project.inProgressTasks.push("");
};

const removeInProgressTask = (project, index) => {
    project.inProgressTasks.splice(index, 1);
};

const addIssue = (project) => {
    project.issues.push("");
};

const removeIssue = (project, index) => {
    project.issues.splice(index, 1);
};

const addRequest = (project) => {
    project.requests.push("");
};

const removeRequest = (project, index) => {
    project.requests.splice(index, 1);
};

const addNextPlan = (project) => {
    project.nextPlans.push("");
};

const removeNextPlan = (project, index) => {
    project.nextPlans.splice(index, 1);
};

const saveReport = async () => {
    if (!reportData.value) return;
    const jsonData = JSON.stringify(reportData.value, null, 2);
    const dateValue =
        reportDate.value ||
        sessionStorage.getItem("reportDate") ||
        (() => {
            const d = new Date();
            return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        })();
    saving.value = true;
    try {
        const memberId =
            savedMemberId.value ??
            parseInt(localStorage.getItem("report-selectedUser") || "0", 10);
        await postSaveReport(jsonData, rawData.value, memberId, dateValue);
        if (savedReportId.value) {
            toastSuccess("보고서를 수정했습니다.");
        } else {
            sessionStorage.removeItem("reportData");
            sessionStorage.removeItem("reportRaw");
            sessionStorage.removeItem("reportDate");
            toastSuccess("보고서를 저장했습니다.");
            router.push("/");
        }
    } catch (error) {
        console.error("보고서 저장 실패:", error);
        toastError("보고서 저장에 실패했습니다. 다시 시도해주세요.");
    } finally {
        saving.value = false;
    }
};

const retryExtract = async () => {
    if (!rawData.value) {
        toastError("원문이 없어 재추출할 수 없습니다.");
        return;
    }
    const userId = savedMemberId.value ?? getSelectedMemberId();
    if (userId === null) {
        toastError("사용자 정보가 없습니다.");
        return;
    }
    try {
        aiLoading.value = true;
        const extractDate =
            reportDate.value ||
            sessionStorage.getItem("reportDate") ||
            (() => {
                const d = new Date();
                return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
            })();
        const res = await postReport(
            { content: rawData.value },
            extractDate,
            userId,
        );
        reportData.value = normalizeReportIssues(res);
        sessionStorage.setItem("reportData", JSON.stringify(res));
    } catch (error) {
        console.error("재추출 실패:", error);
        toastError("재추출에 실패했습니다. 다시 시도해주세요.");
    } finally {
        aiLoading.value = false;
    }
};

const getSelectedMemberId = () => {
    const value = localStorage.getItem("report-selectedUser");
    if (!value || value === "선택" || !/^\d+$/.test(value)) return null;
    const memberId = Number(value);
    return memberId > 0 ? memberId : null;
};
</script>

<style scoped>
.status-banner .save-actions {
    margin-left: auto;
}
</style>
