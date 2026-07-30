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

        <div v-if="isLoading" class="empty-state">불러오는 중...</div>

        <div v-else-if="reportData" class="content-container">
            <div class="json-container">
                <div
                    v-for="(project, projectIndex) in reportData.projects"
                    :key="project.projectName || projectIndex"
                    class="card projects-container"
                >
                    <input
                        readonly
                        class="input project-name-input"
                        v-model="project.projectName"
                    />

                    <div class="field-group completedTasks">
                        <h2>완료된 업무</h2>
                        <input
                            readonly
                            v-if="project.completedTasks.length > 0"
                            v-for="(task, taskIndex) in project.completedTasks"
                            :key="`completed-${taskIndex}`"
                            class="input"
                            :value="task"
                            v-model="project.completedTasks[taskIndex]"
                        />
                        <div v-else class="empty-msg">
                            완료된 업무가 없습니다
                        </div>
                    </div>

                    <div class="field-group inProgressTasks">
                        <h2>진행 중인 업무</h2>
                        <input
                            readonly
                            v-if="project.inProgressTasks.length > 0"
                            v-for="(task, taskIndex) in project.inProgressTasks"
                            :key="`progress-${taskIndex}`"
                            class="input"
                            :value="task"
                            v-model="project.inProgressTasks[taskIndex]"
                        />

                        <div v-else class="empty-msg">
                            진행 중인 업무가 없습니다
                        </div>
                    </div>

                    <div class="field-group issues">
                        <h2>이슈</h2>
                        <input
                            readonly
                            v-if="project.issues.length > 0"
                            v-for="(issue, issueIndex) in project.issues"
                            :key="`issue-${issueIndex}`"
                            class="input"
                            :value="issue.content"
                            v-model="project.issues[issueIndex].content"
                        />
                        <div v-else class="empty-msg">이슈가 없습니다</div>
                    </div>

                    <div class="field-group requests">
                        <h2>요청사항</h2>
                        <input
                            readonly
                            v-if="project.requests.length > 0"
                            v-for="(request, requestIndex) in project.requests"
                            :key="`request-${requestIndex}`"
                            class="input"
                            :value="request"
                            v-model="project.requests[requestIndex]"
                        />
                        <div v-else class="empty-msg">요청사항이 없습니다</div>
                    </div>

                    <div class="field-group nextPlans">
                        <h2>다음 계획</h2>
                        <input
                            readonly
                            v-if="project.nextPlans.length > 0"
                            v-for="(plan, planIndex) in project.nextPlans"
                            :key="`plan-${planIndex}`"
                            class="input"
                            :value="plan"
                            v-model="project.nextPlans[planIndex]"
                        />

                        <div v-else class="empty-msg">다음 계획이 없습니다</div>
                    </div>
                </div>

                <div class="card save-bar">
                    <span class="member-id-display"
                        >사용자: {{ userName }}</span
                    >
                    <div class="save-actions"></div>
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
import { ref, onMounted } from "vue";
import useAPI from "../composables/useApi";
import { useRoute } from "vue-router";

const route = useRoute();

const reportData = ref(null);
const rawData = ref(null);
const userName = ref("");
const isLoading = ref(false);

const { getUsers, GetReportById } = useAPI();

onMounted(async () => {
    const id = route.params.id;
    if (!id) return;

    isLoading.value = true;
    try {
        const data = await GetReportById(id);
        reportData.value = data.parsed_json;
        rawData.value = data.raw_text;

        // 사용자 이름 조회
        const users = await getUsers();
        const found = users.find(
            (u) => String(u.id) === String(data.member_id),
        );
        userName.value = found ? found.name : `사용자 ${data.member_id}`;
    } catch (error) {
        console.error("보고서 불러오기 실패:", error);
        alert("보고서를 불러오는데 실패했습니다.");
    } finally {
        isLoading.value = false;
    }
});
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
