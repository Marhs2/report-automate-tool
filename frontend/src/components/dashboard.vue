<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ArrowRight, Check, CircleAlert, CircleCheck, PenLine } from "lucide-vue-next";
import { useRoute, useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useMyWeek } from "../composables/useMyWeek";
import { splitHistoryLine } from "../lib/historyLine";
import { TODAY_LABELS } from "../lib/weekStatus";

const route = useRoute();
const router = useRouter();
const { getDashboard } = useApi();
const { weekDays, todayState, refreshMyWeek } = useMyWeek();

const board = ref({
    projects: [],
    lastActivity: null,
    projectNames: [],
    selectedProject: "",
    history: [],
});
const isLoading = ref(false);
const loadError = ref("");

const selectedProject = computed({
    get: () => String(route.query.project || ""),
    set: (value) => {
        const project = String(value || "").trim();
        router.replace({ path: "/", query: project ? { project } : {} });
    },
});

const projectOptions = computed(() => {
    const names = [...(board.value.projectNames || [])];
    const selected = String(board.value.selectedProject || "");
    if (selected && !names.includes(selected)) names.push(selected);
    return names;
});

const dotDate = (value) => {
    const [year, month, day] = String(value || "").split("T")[0].split("-");
    if (!year || !month || !day) return "";
    return `${Number(month)}월 ${Number(day)}일`;
};

const todayHeading = computed(() => {
    const now = new Date();
    const weekday = ["일", "월", "화", "수", "목", "금", "토"][now.getDay()];
    return `${now.getMonth() + 1}월 ${now.getDate()}일 ${weekday}요일`;
});

/** 오늘 보고 상태를 화면 맨 위 한 장에 말한다. 주말이면 null. */
const todayCard = computed(() => {
    if (todayState.value === "missing") {
        return {
            tone: "danger",
            chip: TODAY_LABELS.missing,
            title: "오늘 일일보고를 아직 쓰지 않았어요",
            action: "작성하기",
            to: "/compose?kind=daily",
        };
    }
    if (todayState.value === "draft") {
        return {
            tone: "warning",
            chip: TODAY_LABELS.draft,
            title: "오늘 원문 초안만 저장돼 있어요",
            body: "추출하고 검토한 뒤 저장해야 제출로 잡혀요.",
            action: "이어서 쓰기",
            to: "/compose?kind=daily",
        };
    }
    if (todayState.value === "saved") {
        return {
            tone: "success",
            chip: TODAY_LABELS.saved,
            title: "오늘 보고를 저장했어요",
            body: "",
            action: "",
            to: "",
        };
    }
    return null;
});

const WEEK_STATE = {
    saved: { label: "제출", tone: "success" },
    missing: { label: "빠짐", tone: "danger" },
    today: { label: "오늘", tone: "today" },
    upcoming: { label: "예정", tone: "upcoming" },
};
const weekCells = computed(() =>
    weekDays.value.map((day) => ({ ...day, ...WEEK_STATE[day.state] })),
);
const missingDays = computed(() => weekDays.value.filter((day) => day.state === "missing").length);

/** historyLine 톤 → 공통 분류 태그(.cat-tag). */
const CAT_BY_TONE = { success: "is-done", info: "is-progress", warning: "is-issue", request: "is-request", muted: "is-next" };

const history = computed(() =>
    (board.value.history || []).map((item) => ({
        ...item,
        rows: (item.lines || []).map(splitHistoryLine),
    })),
);

const load = async () => {
    isLoading.value = true;
    loadError.value = "";
    try {
        board.value = await getDashboard(String(route.query.project || ""));
        // 고르지 않았으면 가장 최근 프로젝트를 먼저 펼친다. 빈 칸을 보여줄 이유가 없다.
        if (!route.query.project && board.value.projects?.length) {
            selectedProject.value = board.value.projects[0].name;
        }
    } catch (error) {
        console.error("내 현황 조회 실패:", error);
        loadError.value = "내 현황을 불러오지 못했습니다.";
    } finally {
        isLoading.value = false;
    }
};

const currentProject = computed(() =>
    (board.value.projects || []).find((project) => project.name === selectedProject.value) || null,
);

const TODAY_ICONS = { danger: CircleAlert, warning: PenLine, success: CircleCheck };

const chooseProject = (name) => {
    selectedProject.value = name;
};

watch(() => route.query.project, load, { immediate: true });

onMounted(() => {
    document.title = "내 현황";
    refreshMyWeek();
});
</script>

<template>
    <div class="page dash">
        <!-- 오늘 상태: 노션 콜아웃. 화면에서 가장 먼저 읽혀야 하는 한 가지. -->
        <section
            v-if="todayCard"
            class="callout today"
            :class="`is-${todayCard.tone}`"
            aria-labelledby="today-title"
        >
            <component :is="TODAY_ICONS[todayCard.tone]" :size="22" class="callout-icon today-icon" aria-hidden="true" />
            <div class="callout-text">
                <p class="today-date">{{ todayHeading }}</p>
                <h2 id="today-title" class="today-title">{{ todayCard.title }}</h2>
                <p v-if="todayCard.body" class="callout-body">{{ todayCard.body }}</p>
                <p v-else-if="board.lastActivity" class="callout-body">
                    마지막 업무 ·
                    <router-link class="inline-link" :to="board.lastActivity.href">{{ board.lastActivity.title }}</router-link>
                </p>
            </div>
            <router-link v-if="todayCard.action" class="btn btn-primary today-cta" :to="todayCard.to">
                <PenLine :size="16" />
                {{ todayCard.action }}
            </router-link>
        </section>
        <section v-else class="callout today" aria-labelledby="today-title">
            <div class="callout-text">
                <p class="today-date">{{ todayHeading }}</p>
                <h2 id="today-title" class="today-title">오늘은 보고하는 날이 아니에요</h2>
            </div>
        </section>

        <section v-if="weekCells.length" class="dash-section" aria-labelledby="week-title">
            <div class="dash-section-head">
                <h2 id="week-title" class="section-title">이번 주</h2>
                <span v-if="missingDays" class="dash-section-meta is-danger">빠진 날 {{ missingDays }}일</span>
            </div>
            <ol class="week-strip">
                <li
                    v-for="day in weekCells"
                    :key="day.date"
                    class="week-cell"
                    :class="`is-${day.tone}`"
                    :aria-label="`${day.weekday}요일 ${day.label}`"
                >
                    <span class="week-day">{{ day.weekday }}요일</span>
                    <span class="week-num">{{ day.day }}</span>
                    <span class="week-state">
                        <Check v-if="day.tone === 'success'" :size="15" :stroke-width="2.5" />
                        <CircleAlert v-else-if="day.tone === 'danger'" :size="15" :stroke-width="2.25" />
                        {{ day.label }}
                    </span>
                </li>
            </ol>
            <p v-if="missingDays" class="dash-note">
                빠진 날은 주간 초안에 ‘빠진 요일’로 표시돼요.
            </p>
        </section>

        <p v-if="isLoading" class="list-status" role="status">현황을 불러오는 중</p>
        <p v-else-if="loadError" class="list-status is-error" role="alert">{{ loadError }}</p>

        <div v-else-if="board.projects.length === 0" class="empty-state">
            <p class="empty-title">진행 중인 프로젝트가 없어요</p>
            <p class="empty-body">
                일일보고를 저장하면 프로젝트별로 여기 모여요. 표기가 제각각이라면
                정식명과 별칭을 먼저 등록해 두세요.
            </p>
            <div class="empty-actions">
                <router-link class="btn btn-primary" to="/compose?kind=daily">첫 보고 쓰기</router-link>
                <router-link class="btn" to="/settings/projects">프로젝트명 등록</router-link>
            </div>
        </div>

        <!-- 내 프로젝트: 위에서 고르고 바로 아래에서 읽는다. 좌우로 눈을 옮기지 않게 한 칸으로 쌓는다. -->
        <section v-else class="dash-section" aria-labelledby="progress-title">
            <div class="dash-section-head">
                <h2 id="progress-title" class="section-title">내 프로젝트</h2>
                <span class="dash-section-meta">{{ board.projects.length }}개</span>
            </div>

            <div class="project-tabs" role="tablist" aria-label="프로젝트">
                <button
                    v-for="project in board.projects"
                    :key="project.name"
                    type="button"
                    role="tab"
                    class="project-tab"
                    :class="{ 'is-on': project.name === selectedProject }"
                    :aria-selected="project.name === selectedProject"
                    @click="chooseProject(project.name)"
                >
                    <span class="project-tab-name">{{ project.name }}</span>
                    <span v-if="project.lastActive" class="project-tab-date">{{ dotDate(project.lastActive) }}</span>
                </button>
            </div>

            <div v-if="selectedProject" class="project-panel" role="tabpanel">
                <div class="project-panel-head">
                    <p v-if="currentProject?.statusLine" class="project-status">{{ currentProject.statusLine }}</p>
                    <router-link
                        class="group-link"
                        :to="{ path: '/project-timeline', query: { project: selectedProject } }"
                    >
                        전체 흐름 보기
                        <ArrowRight :size="14" />
                    </router-link>
                </div>

                <p v-if="history.length === 0" class="group-empty">
                    이 프로젝트에 기록된 업무가 없어요.
                </p>
                <ol v-else class="history">
                    <li v-for="item in history" :key="item.key">
                        <router-link class="history-row" :to="item.href">
                            <span class="history-when">
                                <span class="history-date">{{ dotDate(item.date) }}</span>
                                <span class="history-kind">{{ item.kindLabel }}</span>
                            </span>
                            <span class="history-body">
                                <span
                                    v-for="(row, index) in item.rows"
                                    :key="index"
                                    class="history-line"
                                >
                                    <span v-if="row.tag" class="cat-tag"
                                        :class="CAT_BY_TONE[row.tone] || 'is-next'">{{ row.tag }}</span>
                                    <span class="history-text">{{ row.text }}</span>
                                </span>
                                <span v-if="item.rows.length === 0" class="history-line">
                                    <span class="history-text">{{ item.title }}</span>
                                </span>
                            </span>
                        </router-link>
                    </li>
                </ol>
            </div>
        </section>
    </div>
</template>

<style scoped>
/* ---- 오늘 콜아웃 (.callout 공통 + 화면 맨 위라 조금 크게) ------------- */
.today {
    padding: var(--space-5) var(--space-6);
}

.today-icon {
    align-self: flex-start;
    margin-top: 22px;
}

.today-date {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text);
    font-variant-numeric: tabular-nums;
}

.today-title {
    margin: 0;
    font-size: var(--fs-20);
    font-weight: var(--fw-bold);
    line-height: var(--lh-tight);
    color: var(--text-strong);
}

.today .callout-body {
    font-size: var(--fs-14);
}

.today-cta {
    flex-shrink: 0;
    height: var(--control-h-lg);
    padding: 0 var(--space-5);
}

.inline-link {
    color: var(--accent);
    font-weight: var(--fw-medium);
    text-decoration: none;
}

.inline-link:hover {
    text-decoration: underline;
}

/* ---- 섹션 공통 ------------------------------------------------------ */
.dash-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    min-width: 0;
}

.dash-section-head {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
}

.dash-section-meta {
    font-size: var(--fs-13);
    color: var(--text-muted);
}

.dash-section-meta.is-danger {
    color: var(--danger-fg);
    font-weight: var(--fw-semibold);
}

.dash-note {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text-muted);
}

/* ---- 이번 주 -------------------------------------------------------- */
.week-strip {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
}

.week-cell {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    min-width: 0;
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--radius);
}

.week-day {
    font-size: var(--fs-13);
    color: var(--text-muted);
}

.week-num {
    font-size: var(--fs-24);
    font-weight: var(--fw-bold);
    line-height: 1.1;
    color: var(--text-strong);
    font-variant-numeric: tabular-nums;
}

.week-state {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-muted);
}

.week-cell.is-success .week-state { color: var(--success-fg); }
.week-cell.is-danger { border-color: var(--danger-border); background: var(--danger-bg); }
.week-cell.is-danger .week-state { color: var(--danger-fg); }
.week-cell.is-today { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
.week-cell.is-today .week-state { color: var(--accent-hover); }
.week-cell.is-upcoming { background: var(--surface-soft); border-color: transparent; }
.week-cell.is-upcoming .week-num { color: var(--text-muted); }
.week-cell.is-upcoming .week-state { font-weight: var(--fw-regular); }

/* ---- 내 프로젝트 ---------------------------------------------------- */
.project-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
}

.project-tab {
    display: inline-flex;
    align-items: baseline;
    gap: var(--space-2);
    max-width: 100%;
    min-height: var(--control-h);
    padding: var(--space-1) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--text);
    font: inherit;
    cursor: pointer;
    transition:
        background var(--dur-fast) var(--ease),
        border-color var(--dur-fast) var(--ease);
}

.project-tab:hover {
    background: var(--surface-soft);
}

.project-tab:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
}

.project-tab.is-on {
    border-color: var(--text-strong);
    background: var(--text-strong);
    color: var(--surface);
}

.project-tab-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
}

.project-tab-date {
    flex-shrink: 0;
    font-size: var(--fs-12);
    opacity: 0.75;
}

.project-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-top: var(--space-2);
}

.project-panel-head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2) var(--space-4);
}

.project-status {
    margin: 0;
    min-width: 0;
    font-size: var(--fs-14);
    color: var(--text);
}

.group-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-left: auto;
    flex-shrink: 0;
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    color: var(--accent);
    text-decoration: none;
}

.group-link:hover {
    text-decoration: underline;
}

.history {
    margin: 0;
    padding: 0;
    list-style: none;
    border-top: 1px solid var(--border);
}

.history > li {
    border-bottom: 1px solid var(--border);
}

.history-row {
    display: grid;
    grid-template-columns: 112px minmax(0, 1fr);
    gap: var(--space-4);
    padding: var(--space-4) var(--space-2);
    border-radius: var(--radius-xs);
    color: inherit;
    text-decoration: none;
    transition: background var(--dur-fast) var(--ease);
}

.history-row:hover {
    background: var(--surface-soft);
}

.history-row:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
}

.history-when {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.history-date {
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.history-kind {
    font-size: var(--fs-13);
    color: var(--text-muted);
}

.history-body {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-width: 0;
}

.history-line {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    font-size: var(--fs-14);
    line-height: var(--lh-base);
    color: var(--text-strong);
}

.history-line .cat-tag {
    flex-shrink: 0;
    margin-top: 2px;
}

.history-text {
    min-width: 0;
    word-break: keep-all;
    overflow-wrap: anywhere;
}

.list-status {
    margin: 0;
    font-size: var(--fs-14);
    color: var(--text-muted);
}

.list-status.is-error {
    color: var(--danger-fg);
}

@media (max-width: 860px) {
    .today {
        padding: var(--space-4);
    }

    .today-icon {
        margin-top: 2px;
    }

    .today-title {
        font-size: var(--fs-16);
    }

    .week-strip {
        gap: var(--space-1);
    }

    .week-cell {
        align-items: center;
        padding: var(--space-2) 0;
    }

    .week-day {
        font-size: var(--fs-12);
    }

    .week-num {
        font-size: var(--fs-16);
    }

    .week-state {
        font-size: var(--fs-11);
    }

    .project-tabs {
        flex-wrap: nowrap;
        overflow-x: auto;
        margin: 0 calc(-1 * var(--space-4));
        padding: 0 var(--space-4);
        scrollbar-width: none;
    }

    .project-tab {
        flex-shrink: 0;
        min-height: var(--control-h-lg);
    }

    .history-row {
        grid-template-columns: minmax(0, 1fr);
        gap: var(--space-2);
        padding: var(--space-3) 0;
    }

    .history-when {
        flex-direction: row;
        gap: var(--space-2);
    }
}
</style>
