<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ChevronRight } from "lucide-vue-next";
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
            body: "원문을 붙여 넣으면 AI가 프로젝트별로 나눠 줘요.",
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
    <div class="page is-wide dash">
        <header class="page-intro">
            <div class="page-intro-text">
                <h1>{{ todayHeading }}</h1>
                <p>오늘 보고와 이번 주 제출, 내가 맡은 프로젝트를 한 곳에서 봐요.</p>
            </div>
        </header>

        <section class="card today" :class="todayCard && `is-${todayCard.tone}`" aria-label="오늘 보고">
            <div v-if="todayCard" class="today-main">
                <div class="today-copy">
                    <span class="state-chip" :class="`is-${todayCard.tone}`">{{ todayCard.chip }}</span>
                    <p class="today-title">{{ todayCard.title }}</p>
                    <p v-if="todayCard.body" class="today-body">{{ todayCard.body }}</p>
                    <p v-else-if="board.lastActivity" class="today-body">
                        마지막 업무 ·
                        <router-link :to="board.lastActivity.href">{{ board.lastActivity.title }}</router-link>
                    </p>
                </div>
                <router-link v-if="todayCard.action" class="btn btn-primary today-action" :to="todayCard.to">
                    {{ todayCard.action }}
                </router-link>
            </div>
            <div v-else class="today-main">
                <div class="today-copy">
                    <span class="state-chip is-plain">주말</span>
                    <p class="today-title">오늘은 보고하는 날이 아니에요</p>
                </div>
            </div>

            <div v-if="weekCells.length" class="week">
                <p class="week-label">이번 주</p>
                <ol class="week-strip">
                    <li
                        v-for="day in weekCells"
                        :key="day.date"
                        class="week-cell"
                        :class="`is-${day.tone}`"
                        :aria-label="`${day.weekday}요일 ${day.label}`"
                    >
                        <span class="week-day">{{ day.weekday }} <b>{{ day.day }}</b></span>
                        <span class="week-state"><i aria-hidden="true"></i>{{ day.label }}</span>
                    </li>
                </ol>
                <p v-if="missingDays" class="week-note">
                    빠진 날 {{ missingDays }}일은 주간 초안에 ‘빠진 요일’로 표시돼요.
                </p>
            </div>
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

        <div v-else class="dash-grid">
            <section class="group-block" aria-labelledby="progress-title">
                <div class="group-head">
                    <h2 id="progress-title">내 프로젝트</h2>
                    <span class="group-meta">{{ board.projects.length }}개</span>
                </div>
                <div class="group">
                    <button
                        v-for="project in board.projects"
                        :key="project.name"
                        type="button"
                        class="row"
                        :class="{ 'is-current': project.name === selectedProject }"
                        :aria-pressed="project.name === selectedProject"
                        @click="chooseProject(project.name)"
                    >
                        <span class="row-main">
                            <span class="row-title">{{ project.name }}</span>
                            <span class="row-sub">{{ project.statusLine }}</span>
                        </span>
                        <span class="row-end">
                            <span v-if="project.lastActive">{{ dotDate(project.lastActive) }}</span>
                            <ChevronRight :size="16" class="row-chevron" />
                        </span>
                    </button>
                </div>
            </section>

            <section class="group-block" aria-labelledby="history-title">
                <div class="group-head">
                    <h2 id="history-title">{{ selectedProject || "업무 기록" }}</h2>
                    <router-link
                        v-if="selectedProject"
                        class="group-link"
                        :to="{ path: '/project-timeline', query: { project: selectedProject } }"
                    >흐름 보기</router-link>
                </div>
                <div class="group">
                    <p v-if="!selectedProject" class="group-empty">
                        왼쪽에서 프로젝트를 고르면 한 업무가 날짜순으로 나와요.
                    </p>
                    <p v-else-if="history.length === 0" class="group-empty">
                        이 프로젝트에 기록된 업무가 없어요.
                    </p>
                    <router-link
                        v-for="item in history"
                        v-else
                        :key="item.key"
                        class="row history-row"
                        :to="item.href"
                    >
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
                </div>
            </section>
        </div>
    </div>
</template>

<style scoped>
.today {
    display: flex;
    flex-direction: column;
    gap: 0;
    padding: 0;
    overflow: hidden;
}

.today-main {
    display: flex;
    align-items: center;
    gap: var(--space-5);
    padding: var(--space-5) var(--space-6);
}

.today-copy {
    display: flex;
    flex: 1;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
    min-width: 0;
}

.today-title {
    margin: 0;
    font-size: var(--fs-20);
    font-weight: var(--fw-bold);
    line-height: var(--lh-tight);
    color: var(--text-strong);
    word-break: keep-all;
}

.today-body {
    margin: 0;
    font-size: var(--fs-14);
    color: var(--text-muted);
    word-break: keep-all;
}

.today-body a {
    color: var(--accent);
    text-decoration: none;
    font-weight: var(--fw-medium);
}

.today-action {
    flex-shrink: 0;
    min-height: var(--control-h-lg);
    padding: 0 var(--space-6);
}

.week {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: var(--space-2) var(--space-5);
    padding: var(--space-4) var(--space-6);
    border-top: 1px solid var(--border);
    background: var(--bg);
}

.week-label {
    margin: 0;
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

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
    gap: 2px;
    min-width: 0;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
}

.week-day {
    font-size: var(--fs-12);
    color: var(--text-muted);
}

.week-day b {
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.week-state {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-muted);
}

.week-state i {
    width: 6px;
    height: 6px;
    border-radius: var(--radius-pill);
    background: var(--border-strong);
}

.week-cell.is-success .week-state { color: var(--success-fg); }
.week-cell.is-success .week-state i { background: var(--success-fg); }
.week-cell.is-danger .week-state { color: var(--danger-fg); }
.week-cell.is-danger .week-state i { background: var(--danger-fg); }
.week-cell.is-today { border-color: var(--accent-border); }
.week-cell.is-today .week-state { color: var(--accent); }
.week-cell.is-today .week-state i { background: var(--accent); }
.week-cell.is-upcoming { background: transparent; border-style: dashed; }
.week-cell.is-upcoming .week-state { font-weight: var(--fw-regular); }

.week-note {
    grid-column: 2;
    margin: 0;
    font-size: var(--fs-12);
    color: var(--text-muted);
}

.list-status {
    margin: 0;
    font-size: var(--fs-14);
    color: var(--text-muted);
}

.list-status.is-error {
    color: var(--danger-fg);
}

.dash-grid {
    display: grid;
    grid-template-columns: minmax(280px, 0.8fr) minmax(0, 1.2fr);
    gap: var(--space-6);
    align-items: start;
}

.group-link {
    flex-shrink: 0;
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    color: var(--accent);
    text-decoration: none;
}

.group-link:hover {
    text-decoration: underline;
}

.history-row {
    align-items: flex-start;
    gap: var(--space-4);
}

.history-when {
    display: flex;
    flex: 0 0 72px;
    flex-direction: column;
    gap: 2px;
    padding-top: 2px;
}

.history-date {
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.history-kind {
    font-size: var(--fs-12);
    color: var(--text-muted);
}

.history-body {
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
}

.history-line {
    display: flex;
    align-items: flex-start;
    gap: var(--space-2);
    font-size: var(--fs-14);
    line-height: var(--lh-base);
    color: var(--text);
}

.history-line .cat-tag {
    flex-shrink: 0;
    margin-top: 1px;
}

.history-text {
    min-width: 0;
    word-break: keep-all;
    overflow-wrap: anywhere;
}

@media (max-width: 1100px) {
    .dash-grid {
        grid-template-columns: minmax(0, 1fr);
    }
}

@media (max-width: 860px) {
    .dash {
        gap: var(--space-4);
    }

    .today-main {
        flex-direction: column;
        align-items: stretch;
        gap: var(--space-4);
        padding: var(--space-4);
    }

    .today-title {
        font-size: var(--fs-16);
    }

    .today-action {
        width: 100%;
    }

    .week {
        grid-template-columns: minmax(0, 1fr);
        padding: var(--space-3) var(--space-4) var(--space-4);
    }

    .week-note {
        grid-column: 1;
    }

    .week-strip {
        gap: var(--space-1);
    }

    .week-cell {
        align-items: center;
        padding: var(--space-2) 0;
    }

    .week-state {
        font-size: var(--fs-12);
    }

    .history-row {
        flex-direction: column;
        gap: var(--space-2);
    }

    .history-when {
        flex: none;
        flex-direction: row;
        gap: var(--space-2);
    }
}
</style>
