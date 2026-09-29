<script setup>
import { computed, onMounted, ref, watch } from "vue";
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

/** 오늘 보고가 없거나 초안뿐이면 화면 맨 위에서 먼저 말한다. */
const todayCard = computed(() => {
    if (todayState.value === "missing") {
        return {
            tone: "danger",
            chip: TODAY_LABELS.missing,
            title: "오늘 일일보고를 아직 쓰지 않았어요",
            body: "메모, 메신저 대화, PPTX 무엇이든 붙여 넣으면 AI가 프로젝트별로 나눠 초안을 만들어요.",
            action: "작성하기",
        };
    }
    if (todayState.value === "draft") {
        return {
            tone: "warning",
            chip: TODAY_LABELS.draft,
            title: "오늘 원문 초안만 저장돼 있어요",
            body: "추출하고 검토한 뒤 저장해야 제출로 잡혀요.",
            action: "이어서 쓰기",
        };
    }
    return null;
});

const WEEK_STATE = {
    saved: { label: "제출", tone: "success" },
    missing: { label: "빠짐", tone: "danger" },
    today: { label: "오늘", tone: "today" },
    upcoming: { label: "", tone: "upcoming" },
};
const weekCells = computed(() =>
    weekDays.value.map((day) => ({ ...day, ...WEEK_STATE[day.state] })),
);
const missingDays = computed(() => weekDays.value.filter((day) => day.state === "missing").length);

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
        <section
            v-if="todayCard"
            class="card today-card"
            :class="`is-${todayCard.tone}`"
            aria-label="오늘 보고"
        >
            <span class="state-chip" :class="`is-${todayCard.tone}`">{{ todayCard.chip }}</span>
            <div class="today-copy">
                <p class="today-title">{{ todayCard.title }}</p>
                <p class="today-body">{{ todayCard.body }}</p>
            </div>
            <router-link class="btn btn-primary today-action" to="/report">{{ todayCard.action }}</router-link>
        </section>

        <p v-if="isLoading" class="list-status" role="status">현황을 불러오는 중</p>
        <p v-else-if="loadError" class="list-status is-error" role="alert">{{ loadError }}</p>

        <div v-else class="dash-grid">
            <div class="dash-main">
                <section class="dash-section" aria-labelledby="progress-title">
                    <div class="section-head">
                        <h2 id="progress-title">진행 중인 프로젝트</h2>
                        <span v-if="board.projects.length" class="section-count">{{ board.projects.length }}</span>
                    </div>
                    <div v-if="board.projects.length" class="project-grid">
                        <button
                            v-for="project in board.projects"
                            :key="project.name"
                            type="button"
                            class="card project-card"
                            :class="{ 'is-selected': project.name === selectedProject }"
                            :aria-pressed="project.name === selectedProject"
                            @click="chooseProject(project.name)"
                        >
                            <span class="project-name">{{ project.name }}</span>
                            <span class="project-status">{{ project.statusLine }}</span>
                            <span v-if="project.lastActive" class="project-date">
                                {{ dotDate(project.lastActive) }}
                            </span>
                        </button>
                    </div>
                    <div v-else class="empty-state">
                        <p class="empty-title">진행 중인 프로젝트가 없어요</p>
                        <p class="empty-body">
                            일일보고를 저장하면 프로젝트별로 여기 모여요. 표기가 제각각이라면
                            정식명과 별칭을 먼저 등록해 두세요.
                        </p>
                        <div class="empty-actions">
                            <router-link class="btn btn-primary" to="/report">첫 보고 쓰기</router-link>
                            <router-link class="btn" to="/settings/projects">프로젝트명 등록</router-link>
                        </div>
                    </div>
                </section>

                <section class="dash-section" aria-labelledby="history-title">
                    <div class="section-head">
                        <h2 id="history-title">프로젝트별 업무</h2>
                        <select v-model="selectedProject" class="input" aria-label="프로젝트">
                            <option value="">프로젝트를 선택하세요</option>
                            <option v-for="name in projectOptions" :key="name" :value="name">
                                {{ name }}
                            </option>
                        </select>
                    </div>
                    <p v-if="!selectedProject" class="list-status">
                        프로젝트를 고르면 지금까지 한 업무가 날짜순으로 나와요.
                    </p>
                    <p v-else-if="history.length === 0" class="list-status">
                        이 프로젝트에 기록된 업무가 없어요.
                    </p>
                    <div v-else class="card history">
                        <router-link
                            v-for="item in history"
                            :key="item.key"
                            class="history-row"
                            :to="item.href"
                        >
                            <span class="history-when">
                                <span class="history-date">{{ dotDate(item.date) }}</span>
                                <span class="kind">{{ item.kindLabel }}</span>
                            </span>
                            <span class="history-body">
                                <span class="history-title">{{ item.title }}</span>
                                <span
                                    v-for="(row, index) in item.rows"
                                    :key="index"
                                    class="history-line"
                                >
                                    <span v-if="row.tag" class="line-tag" :class="`is-${row.tone}`">{{ row.tag }}</span>
                                    {{ row.text }}
                                </span>
                            </span>
                        </router-link>
                    </div>
                </section>
            </div>

            <aside class="dash-aside">
                <section v-if="weekCells.length" class="card dash-panel" aria-labelledby="week-title">
                    <h2 id="week-title">이번 주 내 제출</h2>
                    <ol class="week-strip">
                        <li
                            v-for="day in weekCells"
                            :key="day.date"
                            class="week-cell"
                            :class="`is-${day.tone}`"
                            :aria-label="`${day.weekday}요일 ${day.label || '예정'}`"
                        >
                            <span class="week-day">{{ day.weekday }}</span>
                            <span class="week-state">{{ day.label || "·" }}</span>
                        </li>
                    </ol>
                    <p class="panel-note">
                        {{ missingDays ? `빠진 날 ${missingDays}일은 주간 초안에 ‘빠진 요일’로 표시돼요.` : todayHeading }}
                    </p>
                </section>

                <section class="card dash-panel" aria-labelledby="last-title">
                    <h2 id="last-title">마지막 업무</h2>
                    <template v-if="board.lastActivity">
                        <span class="panel-meta">
                            {{ board.lastActivity.kindLabel }}
                            <template v-if="board.lastActivity.date"> · {{ dotDate(board.lastActivity.date) }}</template>
                        </span>
                        <span class="last-title">{{ board.lastActivity.title }}</span>
                        <router-link class="panel-link" :to="board.lastActivity.href">열기</router-link>
                    </template>
                    <p v-else class="panel-note">아직 저장한 업무가 없어요.</p>
                </section>
            </aside>
        </div>
    </div>
</template>

<style scoped>
.today-card {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-4) var(--space-5);
}

.today-card.is-danger {
    border-color: var(--danger-border);
}

.today-card.is-warning {
    border-color: var(--warning-border);
}

.today-copy {
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
}

.today-title {
    margin: 0;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.today-body {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text-muted);
}

.today-action {
    flex-shrink: 0;
}





.dash-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 320px;
    gap: var(--space-6);
    align-items: start;
}

.dash-main,
.dash-aside {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    min-width: 0;
}

.dash-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
}

.dash-section h2,
.dash-panel h2 {
    margin: 0;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.section-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2) var(--space-3);
}

.section-head .input {
    width: min(260px, 100%);
    margin-left: auto;
}

.section-count {
    font-size: var(--fs-13);
    color: var(--text-muted);
}

.project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: var(--space-3);
}

.project-card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
    width: 100%;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
    transition: border-color var(--dur-fast) var(--ease);
}

.project-card:hover {
    border-color: var(--border-strong);
}

.project-card.is-selected {
    border-color: var(--accent);
    box-shadow: var(--focus-ring);
}

.project-name {
    font-size: var(--fs-14);
    font-weight: var(--fw-bold);
    color: var(--text-strong);
}

.project-status {
    min-height: calc(2 * var(--lh-base) * 1em);
    font-size: var(--fs-14);
    line-height: var(--lh-base);
    color: var(--text);
}

.project-date,
.panel-meta,
.history-date {
    font-size: var(--fs-12);
    color: var(--text-muted);
}

.history {
    display: flex;
    flex-direction: column;
    padding: 0;
    overflow: hidden;
}

.history-row {
    display: grid;
    grid-template-columns: 96px minmax(0, 1fr);
    gap: var(--space-4);
    padding: var(--space-3) var(--space-4);
    color: inherit;
    text-decoration: none;
    transition: background var(--dur-fast) var(--ease);
}

.history-row + .history-row {
    border-top: 1px solid var(--border);
}

.history-row:hover {
    background: var(--surface-soft);
}

.history-when {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
}

.kind {
    align-self: flex-start;
    padding: 0 var(--space-2);
    border-radius: var(--radius-xs);
    background: var(--surface-soft);
    color: var(--text);
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    line-height: 20px;
}

.history-body {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    min-width: 0;
}

.history-title,
.last-title {
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.history-line {
    font-size: var(--fs-14);
    line-height: var(--lh-base);
    color: var(--text);
}

.line-tag {
    display: inline-block;
    margin-right: var(--space-1);
    padding: 0 6px;
    border-radius: var(--radius-xs);
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    line-height: 18px;
}

.line-tag.is-success { background: var(--success-bg); color: var(--success-fg); }
.line-tag.is-info { background: var(--info-bg); color: var(--info-fg); }
.line-tag.is-warning { background: var(--warning-bg); color: var(--warning-fg); }
.line-tag.is-request { background: var(--project-4-bg); color: var(--project-4-fg); }
.line-tag.is-muted,
.line-tag.is-neutral { background: var(--surface-soft); color: var(--text); }

.dash-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.week-strip {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 6px;
    margin: var(--space-1) 0 0;
    padding: 0;
    list-style: none;
}

.week-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    height: 52px;
    border-radius: var(--radius-sm);
    background: var(--surface-soft);
    color: var(--text-muted);
    font-size: var(--fs-12);
}

.week-state {
    font-weight: var(--fw-bold);
}

.week-cell.is-success { background: var(--success-bg); color: var(--success-fg); }
.week-cell.is-danger { background: var(--danger-bg); color: var(--danger-fg); }
.week-cell.is-today {
    border: 1px dashed var(--danger-border);
    background: var(--surface);
    color: var(--danger-fg);
}

.panel-note {
    margin: 0;
    font-size: var(--fs-13);
    line-height: var(--lh-base);
    color: var(--text-muted);
}

.panel-link {
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-7) var(--space-5);
    border: 1px dashed var(--border-strong);
    border-radius: var(--radius);
    text-align: center;
}

.empty-title {
    margin: 0;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.empty-body {
    max-width: 420px;
    margin: 0;
    font-size: var(--fs-14);
    line-height: var(--lh-base);
    color: var(--text-muted);
}

.empty-actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-2);
}

.list-status {
    margin: 0;
    font-size: var(--fs-14);
    color: var(--text);
}

.list-status.is-error {
    color: var(--danger-fg);
}

@media (max-width: 1100px) {
    .dash-grid {
        grid-template-columns: minmax(0, 1fr);
    }

    .dash-aside {
        order: -1;
    }
}

@media (max-width: 860px) {
    .today-card {
        flex-direction: column;
        align-items: stretch;
        gap: var(--space-3);
    }

    .today-card .state-chip {
        align-self: flex-start;
    }

    .today-action {
        min-height: var(--control-h-lg);
    }

    .history-row {
        grid-template-columns: minmax(0, 1fr);
        gap: var(--space-2);
    }

    .history-when {
        flex-direction: row;
        align-items: center;
        gap: var(--space-2);
    }

    .section-head .input {
        width: 100%;
        margin-left: 0;
    }
}
</style>
