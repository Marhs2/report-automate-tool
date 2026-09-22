<template>
    <div class="page report-doc is-wide">
        <!-- 제목 한 줄에 사람·날짜·상태를 모은다. 예전에는 제목과 아래 띠에 두 번 적혀 있었다. -->
        <header class="detail-head">
            <div class="detail-title">
                <h1>{{ userName || "일일보고" }}</h1>
                <span class="detail-date">{{ formatDotDate(reportDate) || "날짜 없음" }}</span>
                <span v-if="savedReportId" class="status-chip">저장됨</span>
                <span v-else class="status-chip is-draft">아직 저장 전</span>
            </div>
            <div class="detail-actions">
                <template v-if="canEdit">
                    <button class="btn btn-small" @click="retryExtract" :disabled="aiLoading">
                        {{ aiLoading ? "재추출 중..." : "재추출" }}
                    </button>
                    <button
                        class="btn btn-primary btn-small hide-on-narrow"
                        @click="saveReport"
                        :disabled="aiLoading || saving"
                    >
                        {{ saving ? "저장 중..." : savedReportId ? "수정 저장" : "저장하기" }}
                    </button>
                </template>
            </div>
        </header>

        <div v-if="isLoading" class="empty-state">불러오는 중...</div>

        <div v-else-if="reportData" class="content-container">
            <div class="json-container">
                <div
                    v-if="reportData.projects.length > 1"
                    class="project-nav"
                    role="group"
                    aria-label="프로젝트 이동"
                >
                    <span class="project-nav-label">
                        프로젝트 {{ reportData.projects.length }}개로 나눴습니다
                    </span>
                    <button
                        v-for="(project, index) in reportData.projects"
                        :key="`nav-${project._uid || index}`"
                        type="button"
                        class="project-nav-chip"
                        :data-accent="projectAccentIndex(index)"
                        @click="scrollToProject(index)"
                    >
                        <i class="project-dot" aria-hidden="true"></i>
                        {{ project.projectName || `프로젝트 ${index + 1}` }}
                    </button>
                </div>

                <!-- 읽기 모드: 제출된 보고를 문서처럼 본다. -->
                <template v-if="!canEdit">
                <div
                    v-for="(project, projectIndex) in reportData.projects"
                    :key="`read-${project._uid || projectIndex}`"
                    :id="`project-${projectIndex}`"
                    class="card projects-container"
                    :data-accent="projectAccentIndex(projectIndex)"
                >
                    <div class="project-head">
                        <i class="project-dot" aria-hidden="true"></i>
                        <h2 class="read-project-name">
                            {{ project.projectName || `프로젝트 ${projectIndex + 1}` }}
                        </h2>
                    </div>
                    <section
                        v-for="col in READ_COLUMNS"
                        :key="col.key"
                        class="read-block"
                    >
                        <h3 :class="col.key">{{ col.label }}</h3>
                        <ul v-if="(project[col.key] || []).filter(Boolean).length" class="read-list">
                            <li v-for="(item, itemIndex) in project[col.key].filter(Boolean)" :key="itemIndex">
                                {{ item }}
                            </li>
                        </ul>
                        <p v-else class="empty-msg">없음</p>
                    </section>
                </div>
                </template>

                <template v-else>
                <div
                    v-for="(project, projectIndex) in reportData.projects"
                    :key="project._uid || projectIndex"
                    :id="`project-${projectIndex}`"
                    class="card projects-container"
                    :data-accent="projectAccentIndex(projectIndex)"
                >
                    <div class="project-head">
                        <i class="project-dot" aria-hidden="true"></i>
                        <span
                            v-if="reportData.projects.length > 1"
                            class="project-kicker"
                        >프로젝트 {{ projectIndex + 1 }}/{{ reportData.projects.length }}</span>
                        <input
                            class="input project-name-input"
                            v-model="project.projectName"
                            placeholder="프로젝트 이름"
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
                                aria-label="이 항목 삭제"
                                @click="removeCompletedTask(project, taskIndex)"
                            >
                                삭제
                            </button>
                        </div>

                        <div v-if="!project.completedTasks.length" class="empty-msg">
                            완료된 업무가 없습니다
                        </div>
                        <button
                            class="btn add-btn"
                            @click="addCompletedTask(project)"
                        >
                            항목 추가
                        </button>
                    </div>

                    <div class="field-group inProgressTasks">
                        <h2>진행 중인 업무</h2>
                        <div
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
                                aria-label="이 항목 삭제"
                                @click="removeInProgressTask(project, taskIndex)"
                            >
                                삭제
                            </button>
                        </div>

                        <div v-if="!project.inProgressTasks.length" class="empty-msg">
                            진행 중인 업무가 없습니다
                        </div>

                        <button
                            class="btn add-btn"
                            @click="addInProgressTask(project)"
                        >
                            항목 추가
                        </button>
                    </div>

                    <div class="field-group issues">
                        <h2>이슈</h2>
                        <div
                            v-for="(issue, issueIndex) in project.issues"
                            :key="`issue-${issueIndex}`"
                            class="task-row"
                        >
                            <input
                                class="input"
                                v-model="project.issues[issueIndex]"
                            />
                            <button
                                class="btn remove-btn"
                                aria-label="이 항목 삭제"
                                @click="removeIssue(project, issueIndex)"
                            >
                                삭제
                            </button>
                        </div>

                        <div v-if="!project.issues.length" class="empty-msg">이슈가 없습니다</div>
                        <button class="btn add-btn" @click="addIssue(project)">
                            항목 추가
                        </button>
                    </div>

                    <div class="field-group requests">
                        <h2>요청사항</h2>
                        <div
                            v-for="(request, requestIndex) in project.requests"
                            :key="`request-${requestIndex}`"
                            class="task-row"
                        >
                            <input
                                class="input"
                                v-model="project.requests[requestIndex]"
                            />
                            <button
                                class="btn remove-btn"
                                aria-label="이 항목 삭제"
                                @click="removeRequest(project, requestIndex)"
                            >
                                삭제
                            </button>
                        </div>
                        <div v-if="!project.requests.length" class="empty-msg">요청사항이 없습니다</div>
                        <button
                            class="btn add-btn"
                            @click="addRequest(project)"
                        >
                            항목 추가
                        </button>
                    </div>

                    <div class="field-group nextPlans">
                        <h2>다음 계획</h2>
                        <div
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
                                aria-label="이 항목 삭제"
                                @click="removeNextPlan(project, planIndex)"
                            >
                                삭제
                            </button>
                        </div>

                        <div v-if="!project.nextPlans.length" class="empty-msg">다음 계획이 없습니다</div>
                        <button
                            class="btn add-btn"
                            @click="addNextPlan(project)"
                        >
                            항목 추가
                        </button>
                    </div>
                </div>

                <button class="btn add-project-btn" @click="addProject">프로젝트 추가</button>

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
                </template>
            </div>

            <aside v-if="rawData" class="card raw-container">
                <h2>원본 보고서</h2>
                <label class="raw-toggle">
                    <input type="checkbox" v-model="highlightOn" />
                    추출 항목과 겹치는 원문 표시
                </label>
                <pre class="raw-content" v-html="highlightedRaw"></pre>
            </aside>
        </div>

        <div v-else class="empty-state">
            보고서 데이터가 없습니다. 보고서를 먼저 제출해주세요.
        </div>
    </div>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from "vue";
import useApi from "../composables/useApi";
import { useRoute, useRouter } from "vue-router";
import { useDialog } from "../composables/useDialog";
import { selectedUserId } from "../composables/useSelectedUser";
import { isAdmin } from "../composables/useSession";
import { pageParentOverride, pageTitleOverride, usePageMeta } from "../composables/usePageMeta";
import {
    highlightedRawHtml,
    projectAccentIndex,
} from "../lib/projectAccent";

const route = useRoute();
const router = useRouter();
const { alert: showAlert, confirm: askConfirm } = useDialog();
const { setPageMeta } = usePageMeta();

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


/** 읽기 모드에서 쓰는 순서. 편집 칸과 같은 키를 쓴다. */
const READ_COLUMNS = [
    { key: "completedTasks", label: "완료된 업무" },
    { key: "inProgressTasks", label: "진행 중인 업무" },
    { key: "issues", label: "이슈" },
    { key: "requests", label: "요청사항" },
    { key: "nextPlans", label: "다음 계획" },
];

const isMine = computed(() => {
    if (savedMemberId.value == null) return true;
    if (selectedUserId.value == null) return false;
    return String(savedMemberId.value) === String(selectedUserId.value);
});

/** 새로 추출한 초안, 내 보고, 관리자는 고칠 수 있다. */
const canEdit = computed(() => {
    if (!savedReportId.value) return true;
    return isMine.value || isAdmin.value;
});

const formatDotDate = (value) => {
    const [year, month, day] = String(value || "").split("-");
    if (!year || !month || !day) return String(value || "");
    return `${year}.${month}.${day}`;
};

/** 어디서 들어왔는지에 따라 위쪽 크럼을 맞춘다.
 *  달력에서 왔는데 "일일보고"로 돌아가면 보던 자리를 잃는다. */
const CRUMB_SOURCES = {
    activities: { to: "/activities", label: "사용자 활동" },
    timeline: { to: "/project-timeline", label: "프로젝트 흐름" },
    list: { to: "/", label: "일일보고" },
};

watch(
    [() => route.name, () => route.query.from, savedReportId, canEdit],
    ([name, from, id, editable]) => {
        if (name !== "report-result") return;
        setPageMeta({
            title: id ? (editable ? "보고 수정" : "일일보고 상세") : "분석 결과",
            parent: CRUMB_SOURCES[String(from || "")] || CRUMB_SOURCES.list,
        });
    },
    { immediate: true },
);

onUnmounted(() => {
    pageTitleOverride.value = "";
    pageParentOverride.value = null;
});


const issueText = (issue) =>
    typeof issue === "string"
        ? issue.trim()
        : String(issue?.content || "").trim();

const highlightOn = ref(true);

/** 프로젝트가 여러 개면 위 이동 바에서 해당 카드로 스크롤한다. */
const scrollToProject = (index) => {
    const el = document.getElementById(`project-${index}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
};

const highlightedRaw = computed(() =>
    highlightedRawHtml(rawData.value, reportData.value?.projects, {
        on: highlightOn.value,
    }),
);

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
        showAlert("보고서를 불러오지 못했습니다.");
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

const removeProject = async (index) => {
    const name = reportData.value.projects[index]?.projectName || "이 프로젝트";
    const ok = await askConfirm(`${name}을(를) 삭제할까요?`, {
        title: "프로젝트 삭제",
        confirmLabel: "삭제",
    });
    if (ok) reportData.value.projects.splice(index, 1);
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
    if (!canEdit.value) {
        showAlert("자신의 보고만 수정할 수 있습니다.");
        return;
    }
    



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
        if(reportData.value.projects.some((project) => project.projectName.trim() === "")) {
            showAlert("프로젝트 이름을 입력해주세요.");
            return;
        }

        
        const memberId =
            savedMemberId.value ??
            parseInt(localStorage.getItem("report-selectedUser") || "0", 10);
        await postSaveReport(jsonData, rawData.value, memberId, dateValue);
        if (savedReportId.value) {
            showAlert("보고서를 수정했습니다.");
        } else {
            sessionStorage.removeItem("reportData");
            sessionStorage.removeItem("reportRaw");
            sessionStorage.removeItem("reportDate");
            showAlert("보고서를 저장했습니다.");
            router.push("/");
        }
    } catch (error) {
        console.error("보고서 저장 실패:", error);
        showAlert("보고서 저장에 실패했습니다. 다시 시도해주세요.");
    } finally {
        saving.value = false;
    }
};

const retryExtract = async () => {
    if (!canEdit.value) {
        showAlert("자신의 보고만 수정할 수 있습니다.");
        return;
    }
    if (!rawData.value) {
        showAlert("원문이 없어 재추출할 수 없습니다.");
        return;
    }
    const userId = savedMemberId.value ?? getSelectedMemberId();
    if (userId === null) {
        showAlert("사용자 정보가 없습니다.");
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
        showAlert("재추출에 실패했습니다. 다시 시도해주세요.");
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
/* 제목 줄 하나에 사람·날짜·상태·동작을 모은다. */
.detail-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
}

.detail-title {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2) var(--space-3);
    min-width: 0;
}

.detail-title h1 {
    margin: 0;
    font-family: var(--heading);
    font-size: 22px;
    letter-spacing: -0.3px;
    color: var(--text-strong);
}

.detail-date {
    font-size: var(--fs-13);
    color: var(--text);
}

.detail-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
}

/* 읽기 모드: 입력칸 대신 문서로 읽는다. */
.read-project-name {
    margin: 0;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    word-break: keep-all;
}

.read-block + .read-block {
    margin-top: var(--space-4);
}

.read-block h3 {
    margin: 0 0 var(--space-2);
    font-family: var(--sans);
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    letter-spacing: 0.4px;
    color: var(--text);
}

.read-block h3.issues {
    color: var(--danger-fg);
}

.read-list {
    margin: 0;
    padding-left: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
}

.read-list li {
    font-size: var(--fs-14);
    color: var(--text-strong);
    line-height: var(--lh-base);
    word-break: keep-all;
}

.projects-container {
    scroll-margin-top: var(--space-4);
}

.project-head {
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--border);
}

.project-dot {
    flex-shrink: 0;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--project-accent, var(--accent));
}

.project-nav {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
}

.project-nav-label {
    margin-right: var(--space-2);
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    word-break: keep-all;
}

.project-nav-chip {
    --project-accent: var(--accent);
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    max-width: 240px;
    height: 28px;
    padding: 0 var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    background: var(--surface);
    font: inherit;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    cursor: pointer;
}

.project-nav-chip:hover {
    border-color: var(--project-accent);
    background: var(--surface-soft);
}

.project-nav-chip[data-accent="1"] {
    --project-accent: var(--info-fg);
}

.project-nav-chip[data-accent="2"] {
    --project-accent: var(--warning-fg);
}

.project-nav-chip[data-accent="3"] {
    --project-accent: var(--success-fg);
}

.project-nav-chip[data-accent="4"] {
    --project-accent: var(--project-4-fg);
}

.project-nav-chip[data-accent="5"] {
    --project-accent: var(--project-5-fg);
}

@media (max-width: 860px) {
    .detail-head {
        align-items: flex-start;
        gap: var(--space-2);
        margin-bottom: var(--space-3);
    }

    .detail-title {
        width: 100%;
    }

    .detail-title h1 {
        font-size: 20px;
    }

    .detail-actions {
        display: grid;
        grid-template-columns: 1fr 1fr;
        width: 100%;
        gap: 8px;
    }

    .detail-actions .btn {
        flex: none;
        width: 100%;
        min-height: 44px;
    }

    .project-nav {
        flex-wrap: nowrap;
        align-items: stretch;
        overflow-x: auto;
        overscroll-behavior-x: contain;
    }

    .project-nav-label {
        flex: none;
        align-self: center;
    }

    .project-nav-chip {
        flex: none;
        max-width: 220px;
        min-height: 44px;
    }
}
</style>
