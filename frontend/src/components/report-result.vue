<template>
    <div class="page">
        <div class="page-header">
            <div>
                <h1>분석 결과</h1>
                <p class="page-subtitle">
                    AI가 정리한 내용을 확인하고 필요한 부분을 수정하세요
                </p>
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
                        >
                            <input
                                :key="`completed-${taskIndex}`"
                                class="input"
                                :value="task"
                                v-model="project.completedTasks[taskIndex]"
                            />
                            <button
                                class="btn"
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
                        >
                            <input
                                :key="`issue-${issueIndex}`"
                                class="input"
                                :value="issue.content"
                                v-model="project.issues[issueIndex].content"
                            />
                            <select
                                :key="`issue-status-${issueIndex}`"
                                class="input issue-status-select"
                                :value="issue.status || '미해결'"
                                @change="toggleIssueStatus(issue, $event)"
                            >
                                <option value="미해결">미해결</option>
                                <option value="해결">해결</option>
                            </select>
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

                <div class="card save-bar">
                    <span class="member-id-display"
                        >사용자: {{ userName }}</span
                    >
                    <div class="save-actions">
                        <button class="btn" @click="retryExtract">
                            재추출
                        </button>
                        <button class="btn btn-primary" @click="saveReport">
                            저장하기
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
import { ref, onMounted, watch } from "vue";
import useAPI from "../composables/useAPI";
import { useRouter } from "vue-router";

const route = useRouter();

const reportData = ref(null);
const rawData = ref(null);
const userName = ref("");
const aiLoading = ref(false);
const { PostSaveReport, PostReport, getUsers } = useAPI();

watch(
    reportData,
    (newVal) => {
        if (newVal) {
            sessionStorage.setItem("reportData", JSON.stringify(newVal));
        }
    },
    { deep: true },
);

onMounted(() => {
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
    project.issues.push({ content: "", status: "미해결" });
};

const toggleIssueStatus = (issue, event) => {
    issue.status = event.target.value;
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

const saveReport = () => {
    if (reportData.value) {
        const jsonData = JSON.stringify(reportData.value, null, 2);
        const reportDate =
            sessionStorage.getItem("reportDate") ||
            (() => {
                const d = new Date();
                return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
            })();

        PostSaveReport(
            jsonData,
            rawData.value,
            parseInt(localStorage.getItem("report-selectedUser") || "0"),
            reportDate,
        )
            .then((response) => {
                console.log("보고서 저장 성공:", response);
                alert("보고서가 성공적으로 저장되었습니다.");
                sessionStorage.removeItem("reportData");
                sessionStorage.removeItem("reportRaw");
                sessionStorage.removeItem("reportDate");
                route.push("/");
            })
            .catch((error) => {
                console.error("보고서 저장 실패:", error);
                alert("보고서 저장에 실패했습니다. 다시 시도해주세요.");
            });
    }
};

const retryExtract = async () => {
    if (!rawData.value) return;
    const userId = localStorage.getItem("report-selectedUser") || "";
    if (!userId) {
        alert("사용자 정보가 없습니다.");
        return;
    }
    try {
        aiLoading.value = true;
        const reportDate =
            sessionStorage.getItem("reportDate") ||
            (() => {
                const d = new Date();
                return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
            })();
        const res = await PostReport(
            { content: rawData.value },
            reportDate,
            userId,
        );
        reportData.value = res;
        sessionStorage.setItem("reportData", JSON.stringify(res));
    } catch (error) {
        console.error("재추출 실패:", error);
        alert("재추출에 실패했습니다. 다시 시도해주세요.");
    } finally {
        aiLoading.value = false;
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

/* 이슈 상태 선택 (미해결/해결) */
.issue-status-select {
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
