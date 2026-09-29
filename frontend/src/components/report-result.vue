<template>
    <div class="page report-doc">
        <!-- 제목 한 줄에 사람·날짜·상태를 모은다. 예전에는 제목과 아래 띠에 두 번 적혀 있었다. -->
        <header class="detail-head">
            <div class="detail-title">
                <h1>{{ userName || "일일보고" }}</h1>
                <span class="detail-date">{{ formatDotDate(reportDate) || "날짜 없음" }}</span>
            </div>
        </header>

     

        <Teleport to="body">
            <div
                v-if="projectPopup"
                class="app-dialog-overlay"
                @click.self="closeProjectPopup"
            >
                <div class="card app-dialog" role="dialog" aria-modal="true" aria-labelledby="edit-project-title">
                    <h2 id="edit-project-title" class="app-dialog-message">프로젝트</h2>
                    <div class="edit-pick-list" role="listbox" aria-label="이 보고서의 프로젝트">
                        <div
                            v-for="(project, index) in reportData?.projects || []"
                            :key="project._uid || index"
                            class="edit-pick-row"
                        >
                            <button
                                type="button"
                                class="edit-pick"
                                :class="{ 'is-on': index === activeIndex }"
                                :aria-selected="index === activeIndex"
                                @click="selectReportProject(index)"
                            >
                                {{ project.projectName || `프로젝트 ${index + 1}` }}
                            </button>
                            <button
                                class="edit-drop"
                                type="button"
                                @click="deleteReportProject(index)"
                            >
                                삭제
                            </button>
                        </div>
                        <p v-if="!(reportData?.projects || []).length" class="edit-empty">이 보고서에 프로젝트가 없습니다.</p>
                    </div>
                    <form class="edit-project-add" @submit.prevent="addNamedProject">
                        <input
                            v-model="newProjectName"
                            class="input"
                            type="text"
                            placeholder="새 프로젝트 이름"
                            aria-label="새 프로젝트 이름"
                        />
                        <button class="btn" type="submit">추가</button>
                    </form>
                    <div class="app-dialog-actions">
                        <button class="btn" type="button" @click="closeProjectPopup">닫기</button>
                    </div>
                </div>
            </div>
        </Teleport>

        <div v-if="isLoading" class="empty-state">불러오는 중...</div>

        <div v-else-if="reportData" class="content-container">
            <div class="json-container">
                <div
                    v-if="!canEdit && reportData.projects.length > 1"
                    class="project-nav"
                    role="group"
                    aria-label="프로젝트 이동"
                >
                    <button
                        v-for="(project, index) in reportData.projects"
                        :key="`nav-${project._uid || index}`"
                        type="button"
                        class="project-nav-chip"
                        @click="scrollToProject(index)"
                    >
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
                        <h2 class="read-project-name">
                            {{ project.projectName || `프로젝트 ${projectIndex + 1}` }}
                        </h2>
                    </div>
                    <section
                        v-for="col in filledColumns(project)"
                        :key="col.key"
                        class="read-block"
                    >
                        <h3 :class="col.key">{{ col.label }}</h3>
                        <ul class="read-list">
                            <li v-for="(item, itemIndex) in col.items" :key="itemIndex">
                                {{ item }}
                            </li>
                        </ul>
                    </section>
                </div>
                </template>

                <template v-else-if="!isNarrow">
                <div
                    v-for="(project, projectIndex) in reportData.projects"
                    :key="project._uid || projectIndex"
                    :id="`project-${projectIndex}`"
                    class="card projects-container"
                    :data-accent="projectAccentIndex(projectIndex)"
                    @focusin="activeIndex = projectIndex"
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
                            class="btn"
                            type="button"
                            @click="openProjectPopup(projectIndex)"
                        >
                            고르기
                        </button>
                        <button
                            class="btn btn-danger"
                            type="button"
                            @click="removeProject(projectIndex)"
                        >
                            삭제
                        </button>
                    </div>
                    <div
                        v-for="col in DESK_FIELDS"
                        :key="col.key"
                        class="field-group"
                        :class="col.key"
                    >
                        <h2>{{ col.label }}</h2>
                        <div
                            v-for="(_item, itemIndex) in project[col.key] || []"
                            :key="`${col.key}-${itemIndex}`"
                            class="task-row"
                        >
                            <input
                                class="input"
                                v-model="project[col.key][itemIndex]"
                                :aria-label="col.label"
                            />
                            <button
                                class="btn remove-btn"
                                type="button"
                                aria-label="이 항목 삭제"
                                @click="removeRow(project, col.key, itemIndex)"
                            >
                                삭제
                            </button>
                        </div>
                        <p v-if="!(project[col.key] || []).length" class="empty-msg">{{ col.empty }}</p>
                        <button class="btn add-btn" type="button" @click="addField(project, col.key)">
                            항목 추가
                        </button>
                    </div>
                </div>
                <button class="btn add-project-btn" type="button" @click="openProjectPopup()">프로젝트 추가</button>
                <div class="card save-bar">
                    <div class="save-actions">
                        <button
                            class="btn btn-primary"
                            @click="saveReport"
                            :disabled="aiLoading || saving"
                        >
                            {{ saving ? "저장 중..." : savedReportId ? "수정 저장" : "저장하기" }}
                        </button>
                        <button
                            v-if="rawData"
                            class="btn reextract-btn"
                            type="button"
                            :disabled="aiLoading || saving"
                            @click="retryExtract"
                        >
                            {{ aiLoading ? "재추출 중..." : "재추출" }}
                        </button>
                    </div>
                </div>
                </template>

                <template v-else>
                <div v-if="activeProject" class="card projects-container">
                    <div class="edit-current">
                        <input
                            class="input"
                            v-model="activeProject.projectName"
                            placeholder="프로젝트 이름"
                            aria-label="프로젝트 이름"
                        />
                        <button type="button" class="edit-more" @click="openProjectPopup(activeIndex)">더보기</button>
                    </div>
                    <section
                        v-for="col in EDIT_COLUMNS"
                        :key="col.key"
                        class="edit-bucket"
                    >
                        <h2>{{ col.label }}</h2>
                        <div
                            v-for="(text, itemIndex) in activeProject[col.key]"
                            :key="`${col.key}-${itemIndex}`"
                            class="edit-row"
                        >
                            <input
                                class="input"
                                v-model="activeProject[col.key][itemIndex]"
                                :aria-label="col.label"
                            />
                            <button
                                type="button"
                                class="edit-remove"
                                @click="removeRow(activeProject, col.key, itemIndex)"
                            >
                                삭제
                            </button>
                        </div>
                        <p v-if="!activeProject[col.key].length" class="edit-empty">없음</p>
                    </section>
                    <form class="edit-compose" @submit.prevent="addCurrentLine">
                        <div class="edit-kinds" role="group" aria-label="종류">
                            <button
                                v-for="col in EDIT_COLUMNS"
                                :key="`kind-${col.key}`"
                                type="button"
                                :aria-pressed="editKind === col.key"
                                :class="{ 'is-on': editKind === col.key }"
                                @click="editKind = col.key"
                            >
                                {{ col.label }}
                            </button>
                        </div>
                        <div class="edit-entry">
                            <input
                                class="input"
                                v-model="draftText"
                                :placeholder="activeKind.placeholder"
                                :aria-label="activeKind.label"
                                enterkeyhint="done"
                            />
                            <button class="btn" type="submit">넣기</button>
                        </div>
                    </form>
                </div>
                <button
                    v-else
                    type="button"
                    class="btn add-project-btn"
                    @click="openProjectPopup"
                >
                    프로젝트 추가
                </button>

                <div class="card save-bar">
                    <div class="save-actions">
                        <button
                            class="btn btn-primary"
                            @click="saveReport"
                            :disabled="aiLoading || saving"
                        >
                            {{ saving ? "저장 중..." : savedReportId ? "수정 저장" : "저장하기" }}
                        </button>
                        <button
                v-if="rawData"
                class="btn reextract-btn"
                type="button"
                :disabled="aiLoading || saving"
                @click="retryExtract"
            >
                {{ aiLoading ? "재추출 중..." : "재추출" }}
            </button>
                    </div>
                </div>
                </template>
            </div>

            <aside v-if="rawData" class="card raw-container" >
                <button type="button" class="raw-fold"  @click="rawOpen = !rawOpen">
                    {{ rawOpen ? "원본 접기" : "원본 보기" }}
                </button>
                <template v-if="rawOpen">
                    <label class="raw-toggle">
                        <input type="checkbox" v-model="highlightOn" />
                        추출 항목과 겹치는 원문 표시
                    </label>
                    <pre class="raw-content" v-html="highlightedRaw"></pre>
                </template>
            </aside>
        </div>

        <div v-else class="empty-state">
            보고서 데이터가 없습니다. 보고서를 먼저 제출해주세요.
        </div>
    </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
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
import { indexAfterCurrent } from "../lib/projectInsert";

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
const { postSaveReport, postReport, getUsers, getReportById, getProjectNames, postProjectName } = useApi();


/** 읽기 모드에서 쓰는 순서. 편집 칸과 같은 키를 쓴다. */
const READ_COLUMNS = [
    { key: "completedTasks", label: "완료된 업무" },
    { key: "inProgressTasks", label: "진행 중인 업무" },
    { key: "issues", label: "이슈" },
    { key: "requests", label: "요청사항" },
    { key: "nextPlans", label: "다음 계획" },
];

const EDIT_COLUMNS = [
    { key: "completedTasks", label: "완료", placeholder: "오늘 마무리한 일" },
    { key: "inProgressTasks", label: "진행", placeholder: "아직 끝나지 않은 일" },
    { key: "issues", label: "이슈", placeholder: "무엇이 막혔는지" },
    { key: "requests", label: "요청", placeholder: "필요한 도움" },
    { key: "nextPlans", label: "다음 계획", placeholder: "다음에 할 일" },
];

const DESK_FIELDS = [
    { key: "completedTasks", label: "완료된 업무", empty: "완료된 업무가 없습니다" },
    { key: "inProgressTasks", label: "진행 중인 업무", empty: "진행 중인 업무가 없습니다" },
    { key: "issues", label: "이슈", empty: "이슈가 없습니다" },
    { key: "requests", label: "요청사항", empty: "요청사항이 없습니다" },
    { key: "nextPlans", label: "다음 계획", empty: "다음 계획이 없습니다" },
];

const isNarrow = ref(
    typeof window !== "undefined" && window.matchMedia("(max-width: 860px)").matches,
);
let narrowQuery = null;
const syncNarrow = () => {
    isNarrow.value = Boolean(narrowQuery?.matches);
};

const activeIndex = ref(0);
const knownProjects = ref([]);
const editKind = ref(EDIT_COLUMNS[0].key);
const draftText = ref("");
const projectPopup = ref(false);
const assignIndex = ref(null);
const newProjectName = ref("");
const rawOpen = ref(
    typeof window !== "undefined" && window.matchMedia("(min-width: 861px)").matches,
);

const activeProject = computed(() => reportData.value?.projects?.[activeIndex.value] || null);
const activeKind = computed(
    () => EDIT_COLUMNS.find((col) => col.key === editKind.value) || EDIT_COLUMNS[0],
);

const filledColumns = (project) =>
    READ_COLUMNS.map((col) => ({
        ...col,
        items: (project?.[col.key] || []).map((item) => String(item || "").trim()).filter(Boolean),
    })).filter((col) => col.items.length);

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
    list: { to: "/reports", label: "일일보고" },
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

const loadProjects = async () => {
    try {
        const names = await getProjectNames();
        knownProjects.value = Array.isArray(names)
            ? names.map((name) => String(name || "").trim()).filter(Boolean)
            : [];
    } catch {
        knownProjects.value = [];
    }
};

onMounted(() => {
    narrowQuery = window.matchMedia("(max-width: 860px)");
    syncNarrow();
    narrowQuery.addEventListener("change", syncNarrow);
    loadProjects();
});

onUnmounted(() => {
    pageTitleOverride.value = "";
    pageParentOverride.value = null;
    narrowQuery?.removeEventListener("change", syncNarrow);
    window.removeEventListener("keydown", onEditKey);
    document.documentElement.classList.remove("is-overlay-open");
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
        completedTasks: asTexts(project.completedTasks).filter(Boolean),
        inProgressTasks: asTexts(project.inProgressTasks).filter(Boolean),
        issues: asTexts(project.issues).filter(Boolean),
        requests: asTexts(project.requests).filter(Boolean),
        nextPlans: asTexts(project.nextPlans).filter(Boolean),
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
    activeIndex.value = 0;
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
    activeIndex.value = 0;
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

const blankProject = (name = "") => ({
    projectName: name,
    completedTasks: [],
    inProgressTasks: [],
    issues: [],
    requests: [],
    nextPlans: [],
});

const focusProject = async (index) => {
    activeIndex.value = index;
    await nextTick();
    scrollToProject(index);
};

const chooseNamedProject = async (name, insertAfter = null) => {
    const value = String(name || "").trim();
    if (!value || !reportData.value) return;
    const projects = reportData.value.projects;
    const target = assignIndex.value;
    if (target != null && projects[target]) {
        const other = projects.findIndex(
            (project, index) =>
                index !== target && String(project.projectName || "").trim() === value,
        );
        if (other >= 0) {
            closeProjectPopup();
            await focusProject(other);
            return;
        }
        projects[target].projectName = value;
        closeProjectPopup();
        await focusProject(target);
        return;
    }
    const index = projects.findIndex(
        (project) => String(project.projectName || "").trim() === value,
    );
    if (index >= 0) {
        closeProjectPopup();
        await focusProject(index);
        return;
    }
    const at = indexAfterCurrent(projects.length, insertAfter, activeIndex.value);
    projects.splice(at, 0, blankProject(value));
    closeProjectPopup();
    await focusProject(at);
};

const openProjectPopup = (index = null) => {
    assignIndex.value = Number.isInteger(index) ? index : null;
    newProjectName.value = "";
    projectPopup.value = true;
    document.documentElement.classList.add("is-overlay-open");
    loadProjects();
};

const closeProjectPopup = () => {
    projectPopup.value = false;
    newProjectName.value = "";
    assignIndex.value = null;
    document.documentElement.classList.remove("is-overlay-open");
};

const onEditKey = (event) => {
    if (event.key === "Escape") closeProjectPopup();
};

watch(projectPopup, (open) => {
    if (open) window.addEventListener("keydown", onEditKey);
    else window.removeEventListener("keydown", onEditKey);
});

const registerProject = async (name) => {
    const value = String(name || "").trim();
    if (!value) return;
    if (!knownProjects.value.includes(value)) {
        knownProjects.value = [...knownProjects.value, value];
    }
    try {
        await postProjectName(value, "");
    } catch (error) {
        if (error.response?.status !== 409) {
            showAlert(error.response?.data?.detail || "프로젝트를 추가하지 못했습니다.");
        }
    }
};

const addNamedProject = async () => {
    const name = newProjectName.value.trim();
    if (!name || !reportData.value) return;
    const anchor = assignIndex.value;
    await registerProject(name);
    assignIndex.value = null;
    await chooseNamedProject(name, anchor);
};

const removeRow = async (project, key, index) => {
    if (!Array.isArray(project?.[key])) return;
    project[key].splice(index, 1);
    if (savedReportId.value) await persistReport();
};

const addCurrentLine = () => {
    const text = draftText.value.trim();
    if (!text || !activeProject.value) return;
    activeProject.value[editKind.value].push(text);
    draftText.value = "";
};

const addField = (project, key) => {
    if (!Array.isArray(project[key])) project[key] = [];
    project[key].push("");
};

const removeProject = async (index) => {
    const name = reportData.value.projects[index]?.projectName || "이 프로젝트";
    const ok = await askConfirm(`${name}을(를) 삭제할까요?`, {
        title: "프로젝트 삭제",
        confirmLabel: "삭제",
    });
    if (!ok) return;
    reportData.value.projects.splice(index, 1);
    if (activeIndex.value >= reportData.value.projects.length) {
        activeIndex.value = Math.max(0, reportData.value.projects.length - 1);
    }
    if (savedReportId.value) await persistReport();
};

const selectReportProject = async (index) => {
    closeProjectPopup();
    await focusProject(index);
};

const deleteReportProject = async (index) => {
    closeProjectPopup();
    await removeProject(index);
};

let persistChain = Promise.resolve();

const reportDateValue = () =>
    reportDate.value ||
    sessionStorage.getItem("reportDate") ||
    (() => {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    })();

const writeReport = async (announce) => {
    if (!reportData.value) return;
    if (!canEdit.value) {
        showAlert("자신의 보고만 수정할 수 있습니다.");
        return;
    }
    for (const project of reportData.value.projects) {
        for (const col of EDIT_COLUMNS) {
            project[col.key] = (project[col.key] || [])
                .map((item) => String(item || "").trim())
                .filter(Boolean);
        }
    }
    if (reportData.value.projects.some((project) => !String(project.projectName || "").trim())) {
        showAlert("프로젝트 이름을 입력해주세요.");
        return;
    }
    const wasSaved = Boolean(savedReportId.value);
    const jsonData = JSON.stringify(reportData.value, null, 2);
    const memberId =
        savedMemberId.value ??
        parseInt(localStorage.getItem("report-selectedUser") || "0", 10);
    saving.value = true;
    try {
        const saved = await postSaveReport(
            jsonData,
            rawData.value,
            memberId,
            reportDateValue(),
            wasSaved ? savedReportId.value : null,
        );
        if (!wasSaved && announce) {
            sessionStorage.removeItem("reportData");
            sessionStorage.removeItem("reportRaw");
            sessionStorage.removeItem("reportDate");
            showAlert("보고서를 저장했습니다.");
            router.push("/reports");
            return;
        }
        const nextId = saved?.id;
        if (nextId && String(nextId) !== String(savedReportId.value || "")) {
            savedReportId.value = nextId;
            await router.replace({
                name: "report-result",
                params: { id: String(nextId) },
                query: route.query,
            });
        }
        if (announce) showAlert("보고서를 수정했습니다.");
    } catch (error) {
        console.error("보고서 저장 실패:", error);
        showAlert("보고서 저장에 실패했습니다. 다시 시도해주세요.");
    } finally {
        saving.value = false;
    }
};

const persistReport = (options = {}) => {
    const announce = Boolean(options.announce);
    const job = persistChain.then(() => writeReport(announce));
    persistChain = job.catch(() => {});
    return job;
};

const saveReport = () => persistReport({ announce: true });

const retryExtract = async () => {
    if (!canEdit.value) {
        showAlert("자신의 보고만 수정할 수 있습니다.");
        return;
    }
    if (!rawData.value) {
        showAlert("원문이 없어 재추출할 수 없습니다.");
        return;
    }
    const ok = await askConfirm("지금 고친 내용은 바뀝니다. 저장하기 전까지는 반영되지 않습니다.", {
        title: "원문으로 다시 정리할까요?",
        confirmLabel: "재추출",
    });
    if (!ok) return;
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
    margin-bottom: 0;
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
    font-size: var(--fs-24);
    letter-spacing: -0.02em;
    color: var(--text-strong);
}

.detail-date {
    font-size: var(--fs-13);
    color: var(--text);
}

.reextract {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin: 0 0 var(--space-3);
    padding: var(--space-3) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
}

.reextract p {
    margin: 0;
    min-width: 0;
    font-size: var(--fs-13);
    line-height: 1.45;
    color: var(--text);
    word-break: keep-all;
}

.reextract-btn {
    flex: none;
    width: auto;
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
    margin-top: var(--space-5);
    padding-top: var(--space-4);
    border-top: 1px solid var(--border);
}

.read-block h3 {
    margin: 0 0 var(--space-2);
    font-family: var(--sans);
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    letter-spacing: 0;
    color: var(--text-strong);
}

.read-block h3.issues {
    color: var(--danger-fg);
}

.read-list {
    margin: 0;
    padding-left: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.read-list li {
    font-size: var(--fs-14);
    color: var(--text-strong);
    line-height: var(--lh-relaxed);
    word-break: keep-all;
}

.projects-container {
    scroll-margin-top: calc(var(--topbar-height) + var(--space-4));
}

.project-head {
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--border);
}

.project-dot {
    flex-shrink: 0;
    width: var(--space-2);
    height: var(--space-2);
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
    height: var(--control-h-sm);
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
        font-size: var(--fs-20);
    }

    .reextract-btn {
        min-height: var(--control-h-lg);
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
        min-height: var(--control-h-lg);
    }
}

.report-doc .save-bar {
    margin-top: var(--space-2);
}

.edit-quiet {
    min-height: var(--control-h-lg);
    padding: 0 var(--space-1);
    border: 0;
    background: transparent;
    color: var(--text);
    font: inherit;
    font-size: var(--fs-16);
    cursor: pointer;
}

.edit-quiet:disabled {
    opacity: 0.5;
    cursor: default;
}

.edit-current {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding-bottom: var(--space-4);
}

.edit-current .input {
    min-width: 0;
    flex: 1;
    min-height: var(--control-h-lg);
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
}

.edit-more {
    flex: none;
    min-height: var(--control-h-lg);
    padding: 0 var(--space-2);
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--accent);
    font: inherit;
    font-size: var(--fs-16);
    cursor: pointer;
}

.edit-more:hover {
    background: var(--accent-soft);
    color: var(--accent-hover);
}

.edit-bucket + .edit-bucket {
    margin-top: var(--space-3);
}

.edit-bucket h2 {
    margin: 5px 0;
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.edit-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-top: var(--space-2);
}

.edit-row .input {
    min-width: 0;
    flex: 1;
    min-height: var(--control-h-lg);
    font-size: var(--fs-16);
}

.edit-remove {
    flex: none;
    min-width: var(--control-h-lg);
    min-height: var(--control-h-lg);
    padding: 0 var(--space-2);
    border: 0;
    background: transparent;
    color: var(--danger-fg);
    font: inherit;
    font-size: var(--fs-14);
    cursor: pointer;
}

.edit-empty {
    margin: 0;
    min-height: var(--control-h-lg);
    display: flex;
    align-items: center;
    border-top: 1px solid var(--border);
    font-size: var(--fs-14);
    color: var(--text-muted);
}

.edit-compose {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-top: var(--space-4);
}

.edit-kinds {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    min-width: 0;
}

.edit-kinds button {
    flex: 1 1 calc(33.33% - var(--space-2));
    min-width: 0;
    min-height: var(--control-h-lg);
    padding: 0 var(--space-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    background: var(--surface);
    color: var(--text-strong);
    font: inherit;
    font-size: var(--fs-14);
    white-space: nowrap;
    cursor: pointer;
    transition:
        border-color var(--dur-fast) var(--ease),
        background var(--dur-fast) var(--ease);
}

.edit-kinds button:hover {
    border-color: var(--border-strong);
}

.edit-kinds button.is-on {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--accent-hover);
    font-weight: var(--fw-semibold);
}

.edit-kinds button:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
}

.edit-entry {
    display: flex;
    gap: var(--space-2);
    align-items: center;
}

.edit-entry .input {
    min-width: 0;
    flex: 1;
    min-height: var(--control-h-lg);
    font-size: var(--fs-16);
}

.edit-pick-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-height: 240px;
    margin-bottom: var(--space-3);
    overflow: auto;
}

.edit-pick-row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
}

.edit-pick-row .edit-pick {
    flex: 1;
    min-width: 0;
}

.edit-pick-row .edit-drop {
    flex: none;
    margin: 0;
    padding: 0 var(--space-1);
}

.edit-pick {
    min-height: var(--control-h-lg);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--text-strong);
    font: inherit;
    font-size: var(--fs-16);
    text-align: left;
    cursor: pointer;
}

.edit-pick.is-on {
    border-color: var(--accent);
    background: var(--accent-soft);
}

.edit-project-add {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    margin-bottom: var(--space-3);
}

.edit-project-add .input {
    min-width: 0;
    flex: 1;
    min-height: var(--control-h-lg);
}

.edit-drop {
    display: flex;
    align-items: center;
    min-height: var(--control-h-lg);
    margin: 0 0 var(--space-2);
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--danger-fg);
    font: inherit;
    font-size: var(--fs-16);
    cursor: pointer;
}

.app-dialog-actions .edit-quiet {
    color: var(--danger-fg);
}

.raw-fold {
    min-height: var(--control-h-lg);
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--text-strong);
    font: inherit;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    cursor: pointer;
}
</style>
