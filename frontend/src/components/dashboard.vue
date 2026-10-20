<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ArrowRight, Check, CircleAlert, CircleCheck, PenLine } from "lucide-vue-next";
import { useRoute, useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useMyWeek } from "../composables/useMyWeek";
import { isAdmin } from "../composables/useSession";
import { splitHistoryLine } from "../lib/historyLine";
import { TODAY_LABELS } from "../lib/weekStatus";
import { buildRows, periodDays, todayByTeam, todayIso } from "../lib/submissionGrid";

const route = useRoute();
const router = useRouter();
const { getDashboard, getUserActivities, getTeams, getUsers } = useApi();

/** 다음 할 일의 근거 보고가 며칠 전인지. 일주일이 넘으면 오늘 할 일처럼 보이지 않게 제목을 바꾼다. */
const STALE_FOCUS_DAYS = 7;
const focusAgeDays = computed(() => {
    const date = String(board.value.focus?.date || "").slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return 0;
    const diff = new Date(`${todayIso()}T00:00:00`) - new Date(`${date}T00:00:00`);
    return Math.max(0, Math.round(diff / 86400000));
});
const focusIsStale = computed(() => focusAgeDays.value > STALE_FOCUS_DAYS);

/* 관리자 홈: 부서별 오늘 제출 현황. 자세히 볼 때는 사용자 활동으로 간다. */
const teamToday = ref([]);
const loadTeamToday = async () => {
    const today = todayIso();
    const days = periodDays("week", today);
    try {
        const [activities, teams, users] = await Promise.all([
            getUserActivities(Number(days[0].slice(0, 4)), Number(days[0].slice(5, 7)), days[0], days.at(-1)),
            getTeams(),
            getUsers().catch(() => []),
        ]);
        const rows = buildRows(activities || [], days, {
            today,
            adminIds: new Set((users || []).filter((user) => user.is_admin).map((user) => String(user.id))),
            teamNames: Object.fromEntries((teams || []).map((team) => [String(team.id), team.team_name])),
        });
        teamToday.value = todayByTeam(rows, days, today);
    } catch (error) {
        console.error("부서별 오늘 현황 조회 실패:", error);
        teamToday.value = [];
    }
};
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
            title: "오늘 보고를 임시 저장만 했어요",
            body: "저장까지 마쳐야 제출돼요.",
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

/** 오늘 재촉할 게 없을 때(todayCard가 null) 그 이유를 말한다. 주말과, 보고 대상이 아닌 관리자를 구분한다. */
const quietTitle = computed(() => {
    const weekday = new Date().getDay();
    if (weekday === 0 || weekday === 6) return "주말이라 오늘은 보고할 게 없어요";
    if (isAdmin.value) return "관리자 계정은 일일보고 대상이 아니에요";
    return "오늘은 보고하는 날이 아니에요";
});

const WEEK_STATE = {
    saved: { label: "제출", tone: "success" },
    missing: { label: "미제출", tone: "danger" },
    today: { label: "오늘", tone: "today" },
    upcoming: { label: "예정", tone: "upcoming" },
};
const weekCells = computed(() =>
    weekDays.value.map((day) => ({ ...day, ...WEEK_STATE[day.state] })),
);
const missingDays = computed(() => weekDays.value.filter((day) => day.state === "missing").length);

/** historyLine 톤 → 공통 분류 태그(.cat-tag). */
const CAT_BY_TONE = { success: "is-done", info: "is-progress", warning: "is-issue", request: "is-request", muted: "is-next" };

/** 대시보드에는 최근 몇 건만. 나머지는 프로젝트 흐름에서 본다. */
const HISTORY_LIMIT = 5;
const history = computed(() =>
    (board.value.history || []).slice(0, HISTORY_LIMIT).map((item) => ({
        ...item,
        rows: (item.lines || []).map(splitHistoryLine),
    })),
);
const moreHistory = computed(() => Math.max(0, (board.value.history || []).length - HISTORY_LIMIT));

const FOCUS_KINDS = [
    { key: "nextPlans", label: "다음", cls: "is-next" },
    { key: "issues", label: "이슈", cls: "is-issue" },
    { key: "requests", label: "요청", cls: "is-request" },
];

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
    if (isAdmin.value) loadTeamToday();
});
</script>

<template>
    <div class="page dash">
        <!-- 오늘 상태: 노션 콜아웃. 화면에서 가장 먼저 읽혀야 하는 한 가지. -->
        <section
            v-if="todayCard"
            class="callout today dash-today"
            :class="`is-${todayCard.tone}`"
            aria-labelledby="today-title"
        >
            <component :is="TODAY_ICONS[todayCard.tone]" :size="22" class="callout-icon today-icon" aria-hidden="true" />
            <div class="callout-text">
                <p class="today-date">{{ todayHeading }}</p>
                <h2 id="today-title" class="today-title">{{ todayCard.title }}</h2>
                <p v-if="todayCard.body" class="callout-body">{{ todayCard.body }}</p>
                <p v-if="board.lastActivity" class="callout-body">
                    마지막 업무 ·
                    <router-link class="inline-link" :to="board.lastActivity.href">{{ board.lastActivity.title }}</router-link>
                    <span class="last-meta">{{ board.lastActivity.kindLabel }}<template v-if="dotDate(board.lastActivity.date)"> · {{ dotDate(board.lastActivity.date) }}</template></span>
                </p>
            </div>
            <router-link v-if="todayCard.action" class="btn btn-primary today-cta" :to="todayCard.to">
                <PenLine :size="16" />
                {{ todayCard.action }}
            </router-link>
        </section>
        <section v-else class="callout today dash-today" aria-labelledby="today-title">
            <div class="callout-text">
                <p class="today-date">{{ todayHeading }}</p>
                <h2 id="today-title" class="today-title">{{ quietTitle }}</h2>
                <ul v-if="isAdmin && teamToday.length" class="team-today" aria-label="부서별 오늘 제출">
                    <li v-for="team in teamToday" :key="team.teamId ?? 'none'">
                        <span class="team-today-name">{{ team.teamName }}</span>
                        <span class="team-today-count" :class="{ 'is-all': team.done === team.total }">
                            오늘 {{ team.done }}/{{ team.total }}
                        </span>
                        <span v-if="team.pending.length" class="team-today-pending">
                            아직 안 냄 · {{ team.pending.join(", ") }}
                        </span>
                    </li>
                </ul>
                <p v-if="isAdmin" class="callout-body">
                    날짜별로는
                    <router-link class="inline-link" to="/activities">사용자 활동</router-link>,
                    주간 취합은
                    <router-link class="inline-link" to="/weekly">주간 보고서</router-link>에서 봐요.
                </p>
                <p v-if="board.lastActivity" class="callout-body">
                    마지막 업무 ·
                    <router-link class="inline-link" :to="board.lastActivity.href">{{ board.lastActivity.title }}</router-link>
                    <span class="last-meta">{{ board.lastActivity.kindLabel }}<template v-if="dotDate(board.lastActivity.date)"> · {{ dotDate(board.lastActivity.date) }}</template></span>
                </p>
            </div>
        </section>

        <!-- 옆 칸(PC) / 오늘 바로 아래(폰): 이번 주와 다음 할 일. 프로젝트 이력보다 먼저 봐야 하는 것. -->
        <aside class="dash-side">
        <section v-if="weekCells.length" class="dash-section" aria-labelledby="week-title">
            <div class="dash-section-head">
                <h2 id="week-title" class="section-title">이번 주</h2>
                <span v-if="missingDays" class="dash-section-meta is-danger">미제출 {{ missingDays }}일</span>
            </div>
            <ol class="week-strip">
                <li
                    v-for="day in weekCells"
                    :key="day.date"
                    class="week-cell"
                    :class="`is-${day.tone}`"
                    :aria-label="`${day.weekday}요일 ${day.label}`"
                >
                    <span class="week-day">{{ day.weekday }}</span>
                    <span class="week-num">{{ day.day }}</span>
                    <span class="week-state">
                        <Check v-if="day.tone === 'success'" :size="15" :stroke-width="2.5" />
                        <CircleAlert v-else-if="day.tone === 'danger'" :size="15" :stroke-width="2.25" />
                        {{ day.label }}
                    </span>
                </li>
            </ol>
            <p v-if="missingDays" class="dash-note">
                미제출한 날은 주간 초안에 ‘빠진 요일’로 표시돼요.
            </p>
        </section>

        <section v-if="board.focus" class="dash-section" aria-labelledby="focus-title">
            <div class="dash-section-head">
                <h2 id="focus-title" class="section-title">{{ focusIsStale ? "지난 할 일" : "다음 할 일" }}</h2>
                <span class="dash-section-meta">
                    {{ dotDate(board.focus.date) }} 보고<template v-if="focusIsStale"> · {{ focusAgeDays }}일 전</template>
                </span>
            </div>
            <ul class="focus-list">
                <li v-for="(item, index) in board.focus.items" :key="`${item.project}-${index}`">
                    <p v-if="item.project" class="focus-project">{{ item.project }}</p>
                    <template v-for="kind in FOCUS_KINDS" :key="kind.key">
                        <p v-for="(text, line) in item[kind.key]" :key="`${kind.key}-${line}`" class="focus-line">
                            <span class="cat-tag" :class="kind.cls">{{ kind.label }}</span>
                            <span class="focus-text">{{ text }}</span>
                        </p>
                    </template>
                </li>
            </ul>
        </section>
        </aside>

        <div class="dash-projects">
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
                <router-link
                    v-if="moreHistory"
                    class="group-link history-more"
                    :to="{ path: '/project-timeline', query: { project: selectedProject } }"
                >
                    이전 기록 {{ moreHistory }}건 더 보기
                    <ArrowRight :size="14" />
                </router-link>
            </div>
        </section>
        </div>
    </div>
</template>

<style scoped src="../styles/components/dashboard.css"></style>
