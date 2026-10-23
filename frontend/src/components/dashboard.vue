<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useMyWeek } from "../composables/useMyWeek";
import { useMyWeekly } from "../composables/useMyWeekly";
import { useTeamSummary } from "../composables/useTeamSummary";
import { focusColumnsOf } from "../lib/focusColumns";
import { todayIso } from "../lib/submissionGrid";
import WeekDots from "./ui/WeekDots.vue";

/*
 * 내 현황. 2026-10-21 시안(실무자 · 팀장 · 관리자)을 따른다.
 * 실무자: 오늘 · 이번 주 → 다음 할 일 → 이번 주 주간보고 → 내 프로젝트 표.
 * 팀장: 실무자 화면 + 이번 주 아래에 우리 부서 오늘 제출 · 주간 취합.
 * 관리자: 전체 오늘 제출 · 전체 주간 취합, 이번 주에 직접 쓴 보고가 있으면 내 보고 두 칸.
 */
const route = useRoute();
const router = useRouter();
const { getDashboard } = useApi();
const { weekDays, todayState, refreshMyWeek } = useMyWeek();

const WEEKDAY = ["일", "월", "화", "수", "목", "금", "토"];
const parseIso = (iso) => {
    const [y, m, d] = String(iso || "").slice(0, 10).split("-").map(Number);
    return y && m && d ? new Date(y, m - 1, d) : null;
};
const longDate = (iso) => {
    const day = parseIso(iso);
    return day ? `${day.getMonth() + 1}월 ${day.getDate()}일 (${WEEKDAY[day.getDay()]})` : "";
};
const slashDate = (iso) => {
    const day = parseIso(iso);
    return day ? `${day.getMonth() + 1}/${day.getDate()}` : "";
};
const daysBetween = (from, to) => Math.round((parseIso(to) - parseIso(from)) / 86400000);

const { role, teamToday, openTeams, toggleTeam, teamKey, todayTotal, myTeam, pct, collection, isMaking, makeDeck } =
    useTeamSummary();
const { weeklyCard, weeklyEmph } = useMyWeekly();
const todayText = computed(() => longDate(todayIso()));

/** 안 낸 사람 이름은 여기까지만 보이고 "외 N명"으로 접는다. 주간 취합 화면의 MEMBER_PREVIEW와 같은 수. */
const PREVIEW = 6;
const isOpen = (key) => openTeams.value.includes(key);
const pendingNames = (key, names) => (isOpen(key) ? names : names.slice(0, PREVIEW)).join(", ");

/* ---- 오늘 · 이번 주 ---------------------------------------------- */
const TODAY = {
    missing: { label: "아직 안 냄", tone: "muted", note: "오늘 보고는 오늘 안에 내면 됩니다.", action: "작성하기" },
    draft: { label: "임시 저장만 함", tone: "warning", note: "임시 저장은 제출이 아닙니다. 제출해야 집계에 들어갑니다.", action: "이어서 쓰기" },
    saved: { label: "제출됨", tone: "success", note: "오늘 할 일은 끝났습니다.", action: "" },
};
const todayCard = computed(() => TODAY[todayState.value] || null);
/** 한 화면에 기본 버튼은 하나. 오늘 쓸 게 남았으면 그것, 아니면 주간보고 버튼이 기본이 된다. */
const todayHasCta = computed(() => Boolean(todayCard.value?.action));
/** useMyWeek은 불러오기 표시가 없다. 주 배열이 비어 있으면 아직 안 온 것으로 본다. */
const weekLoading = computed(() => !weekDays.value.length);

const CELL = {
    saved: { label: "제출", tone: "success" },
    missing: { label: "미제출", tone: "danger" },
    today: { label: "오늘", tone: "today" },
    upcoming: { label: "예정", tone: "upcoming" },
    holiday: { label: "휴", tone: "holiday" },
};
const DOT = { saved: "done", missing: "missing", today: "today", upcoming: "future", holiday: "holiday" };
const weekCells = computed(() =>
    weekDays.value.map((day) => ({ ...day, ...CELL[day.state], slash: slashDate(day.date) })),
);
const weekDots = computed(() =>
    weekDays.value.map((day) => ({
        label: day.weekday,
        state: day.state === "saved" && day.date === todayIso() ? "today-done" : DOT[day.state],
    })),
);
const missedDays = computed(() => weekDays.value.filter((day) => day.state === "missing"));
/** 내가 이번 주에 보고를 쓴 적이 있는지. 관리자는 이때만 내 보고 칸을 본다. */
const wroteThisWeek = computed(() => weekDays.value.some((day) => day.state === "saved"));

const CHIP_TONE = { muted: "is-plain", warning: "is-warning", success: "is-success" };

/* ---- 다음 할 일 ---------------------------------------------------- */
const STALE_DAYS = 7;
const board = ref({ projects: [], focus: null, history: [], projectNames: [] });
const isBoardLoading = ref(false);
const loadError = ref("");
const focusAge = computed(() => (board.value.focus?.date ? daysBetween(board.value.focus.date, todayIso()) : 0));
const focusStale = computed(() => focusAge.value > STALE_DAYS);
const focusBasis = computed(() => {
    const date = board.value.focus?.date;
    if (!date) return "";
    if (focusStale.value) return `${longDate(date)} 보고 기준 · ${focusAge.value}일 전`;
    return date === todayIso() ? `${longDate(date)} 오늘 보고 기준` : `${longDate(date)} 보고 기준`;
});
/** 프로젝트별로 온 할 일을 세 칸(다음 계획 · 열린 이슈 · 요청)으로 편다. */
const focusColumns = computed(() => focusColumnsOf(board.value.focus));

/* ---- 내 프로젝트 ---------------------------------------------------- */
const FLOW_LIMIT = 5;
const FLOW_COLS = [
    { key: "done", label: "완료" },
    { key: "doing", label: "진행" },
    { key: "issues", label: "이슈" },
    { key: "next", label: "다음" },
];
const selectedProject = computed(() => String(route.query.project || board.value.selectedProject || ""));
const chooseProject = (name) => router.replace({ path: route.path, query: { project: name } });
const flowRows = computed(() =>
    (board.value.history || [])
        .filter((item) => item.kind === "daily")
        .slice(0, FLOW_LIMIT)
        .map((item) => ({
            key: item.key,
            href: item.href,
            date: longDate(item.date),
            cells: FLOW_COLS.map((col) => ({ key: col.key, label: col.label, items: item[col.key] || [] })),
        })),
);
const loadBoard = async () => {
    isBoardLoading.value = true;
    loadError.value = "";
    try {
        board.value = await getDashboard(String(route.query.project || ""));
        // 고르지 않았으면 가장 최근 프로젝트를 먼저 펼친다.
        if (!route.query.project && board.value.projects?.length) chooseProject(board.value.projects[0].name);
    } catch (error) {
        console.error("내 현황 조회 실패:", error);
        loadError.value = "내 현황을 불러오지 못했습니다.";
    } finally {
        isBoardLoading.value = false;
    }
};

watch(() => route.query.project, loadBoard, { immediate: true });

onMounted(() => {
    document.title = "내 현황";
    refreshMyWeek();
});
</script>

<template>
    <div class="page dash">
        <!-- 관리자: 전체 현황이 먼저. 본인 보고는 이번 주에 쓴 적이 있을 때만 아래에. -->
        <template v-if="role === 'admin'">
            <section class="card board" aria-labelledby="all-today-h">
                <header class="board-head">
                    <h2 id="all-today-h" class="board-title">전체 오늘 제출</h2>
                    <p v-if="teamToday.length" class="board-num">
                        {{ todayTotal.done }} / {{ todayTotal.total }}명
                        <span v-if="todayTotal.left" class="board-num-note is-danger">아직 안 낸 사람 {{ todayTotal.left }}명</span>
                    </p>
                </header>
                <p v-if="!teamToday.length" class="board-empty-title">오늘은 보고하는 날이 아니거나, 집계할 사람이 없습니다.</p>
                <ul v-else class="dept-list">
                    <li v-for="team in teamToday" :key="teamKey(team)" class="dept-row">
                        <div class="dept-line">
                            <span class="dept-name">{{ team.teamName }}</span>
                            <span class="bar" aria-hidden="true"><span :class="{ 'is-full': !team.pending.length }" :style="{ width: `${pct(team.done, team.total)}%` }"></span></span>
                            <span class="dept-count" :class="{ 'is-all': !team.pending.length }">{{ team.done }}/{{ team.total }}명</span>
                        </div>
                        <p class="dept-who">
                            <template v-if="team.pending.length">
                                <span class="dept-who-label">아직 안 낸 사람</span>
                                {{ pendingNames(teamKey(team), team.pending) }}
                                <button
                                    v-if="team.pending.length > PREVIEW"
                                    type="button"
                                    class="btn btn-small btn-ghost dept-more"
                                    :aria-expanded="isOpen(teamKey(team))"
                                    @click="toggleTeam(teamKey(team))"
                                >
                                    {{ isOpen(teamKey(team)) ? "접기" : `외 ${team.pending.length - PREVIEW}명` }}
                                </button>
                            </template>
                            <span v-else class="is-success">모두 냄</span>
                        </p>
                    </li>
                </ul>
                <p class="board-foot-note">안 낸 사람이 많은 부서부터. 오늘은 미제출로 세지 않고, 관리자 계정은 이번 기간에 낸 보고가 있을 때만 셉니다.</p>
            </section>

            <section v-if="collection" class="card board" aria-labelledby="all-week-h">
                <header class="board-head">
                    <h2 id="all-week-h" class="board-title">전체 주간 취합</h2>
                    <span class="board-meta">{{ collection.week.label }} · <b class="board-meta-num">{{ collection.submitted }}/{{ collection.total }}명</b></span>
                </header>
                <ul class="dept-list">
                    <li v-for="team in collection.teams" :key="team.id ?? team.name" class="dept-row">
                        <div class="dept-line">
                            <span class="dept-name">{{ team.name }}</span>
                            <span class="bar" aria-hidden="true">
                                <span :class="{ 'is-full': team.submitted === team.total }" :style="{ width: `${pct(team.submitted, team.total)}%` }"></span>
                            </span>
                            <span class="dept-count" :class="{ 'is-all': team.submitted === team.total }">{{ team.submitted }}/{{ team.total }}명</span>
                            <span v-if="team.submitted === team.total" class="state-chip is-success">모두 모임</span>
                        </div>
                    </li>
                </ul>
                <div class="board-foot">
                    <router-link class="btn btn-small" to="/weekly">주간보고에서 취합하기</router-link>
                </div>
            </section>

            <div v-if="wroteThisWeek" class="dash-row is-today-week">
                <section class="card board" aria-labelledby="own-today-h">
                    <header class="board-head">
                        <h2 id="own-today-h" class="board-title">내 오늘 일일보고</h2>
                        <span class="board-meta">{{ todayText }}</span>
                    </header>
                    <div v-if="todayCard" class="board-body">
                        <p class="today-state" :class="`is-${todayCard.tone}`">{{ todayCard.label }}</p>
                        <router-link v-if="todayCard.action" class="btn btn-primary dash-cta" to="/compose?kind=daily">{{ todayCard.action }}</router-link>
                    </div>
                </section>
                <section class="card board" aria-labelledby="own-week-h">
                    <header class="board-head">
                        <h2 id="own-week-h" class="board-title">내 이번 주</h2>
                        <WeekDots v-if="weekDots.length" :days="weekDots" />
                    </header>
                    <ol class="week-grid">
                        <li v-for="day in weekCells" :key="day.date" class="week-cell" :class="`is-${day.tone}`"
                            :aria-label="`${day.weekday}요일 ${day.slash} ${day.label}`">
                            <span class="week-day">{{ day.weekday }}</span>
                            <span class="week-date">{{ day.slash }}</span>
                            <span class="week-state">{{ day.label }}</span>
                        </li>
                    </ol>
                </section>
            </div>
        </template>

        <!-- 실무자 · 팀장 -->
        <template v-else>
            <div class="dash-row is-today-week">
                <section class="card board" aria-labelledby="today-h">
                    <header class="board-head">
                        <h2 id="today-h" class="board-title">오늘 일일보고</h2>
                        <span class="board-meta">{{ todayText }}</span>
                    </header>
                    <div class="board-body">
                        <template v-if="weekLoading">
                            <span class="skel skel-state" role="status" aria-label="오늘 상태를 불러오는 중"></span>
                        </template>
                        <template v-else-if="todayCard">
                            <p class="today-state" :class="`is-${todayCard.tone}`">{{ todayCard.label }}</p>
                            <p class="board-note">{{ todayCard.note }}</p>
                            <router-link v-if="todayCard.action" class="btn btn-primary dash-cta" to="/compose?kind=daily">{{ todayCard.action }}</router-link>
                        </template>
                        <template v-else>
                            <p class="today-state is-muted">보고하는 날이 아님</p>
                            <p class="board-note">주말이나 공휴일에는 보고하지 않습니다.</p>
                        </template>
                    </div>
                </section>

                <section class="card board" aria-labelledby="week-h">
                    <header class="board-head">
                        <h2 id="week-h" class="board-title">이번 주</h2>
                        <WeekDots v-if="weekDots.length" :days="weekDots" />
                    </header>
                    <ol v-if="weekLoading" class="week-grid" role="status" aria-label="이번 주 현황을 불러오는 중">
                        <li v-for="n in 5" :key="n" class="week-cell is-skel" aria-hidden="true"></li>
                    </ol>
                    <ol v-else class="week-grid">
                        <li v-for="day in weekCells" :key="day.date" class="week-cell" :class="`is-${day.tone}`"
                            :aria-label="`${day.weekday}요일 ${day.slash} ${day.label}`">
                            <span class="week-day">{{ day.weekday }}</span>
                            <span class="week-date">{{ day.slash }}</span>
                            <span class="week-state">{{ day.label }}</span>
                        </li>
                    </ol>
                    <div v-if="!weekLoading" class="board-foot week-foot">
                        <span v-if="missedDays.length" class="is-danger">
                            빠진 보고 {{ missedDays.length }}건 · {{ missedDays.map((day) => longDate(day.date)).join(", ") }}
                        </span>
                        <span v-else class="is-success">빠진 보고 없음</span>
                        <span class="board-foot-note">오늘과 공휴일(휴)은 미제출로 세지 않습니다</span>
                    </div>
                </section>
            </div>

            <!-- 팀장: 우리 부서 -->
            <div v-if="role === 'leader'" class="dash-row is-halves">
                <section class="card board" aria-labelledby="dept-today-h">
                    <header class="board-head">
                        <h2 id="dept-today-h" class="board-title">우리 부서 오늘 제출</h2>
                        <span v-if="myTeam" class="board-num">{{ myTeam.done }} / {{ myTeam.total }}명</span>
                    </header>
                    <div v-if="myTeam" class="board-body">
                        <span class="bar" aria-hidden="true"><span :class="{ 'is-full': !myTeam.pending.length }" :style="{ width: `${pct(myTeam.done, myTeam.total)}%` }"></span></span>
                        <p v-if="!myTeam.pending.length" class="board-note is-success">모두 냈습니다.</p>
                        <p v-else class="dept-who">
                            <span class="dept-who-label">아직 안 낸 사람 {{ myTeam.pending.length }}명</span>
                            {{ pendingNames("mine", myTeam.pending) }}
                            <button
                                v-if="myTeam.pending.length > PREVIEW"
                                type="button"
                                class="btn btn-small btn-ghost dept-more"
                                :aria-expanded="isOpen('mine')"
                                @click="toggleTeam('mine')"
                            >
                                {{ isOpen("mine") ? "접기" : `외 ${myTeam.pending.length - PREVIEW}명` }}
                            </button>
                        </p>
                        <p class="board-foot-note">오늘은 아직 낼 수 있어 미제출로 세지 않습니다.</p>
                    </div>
                    <p v-else class="board-empty-title">오늘은 보고하는 날이 아닙니다.</p>
                </section>

                <section class="card board" aria-labelledby="dept-week-h">
                    <header class="board-head">
                        <h2 id="dept-week-h" class="board-title">우리 부서 주간 취합</h2>
                        <span v-if="collection" class="board-num">{{ collection.submitted }} / {{ collection.total }}명</span>
                    </header>
                    <div v-if="collection" class="board-body">
                        <span class="bar" aria-hidden="true">
                            <span :class="{ 'is-full': collection.complete }" :style="{ width: `${pct(collection.submitted, collection.total)}%` }"></span>
                        </span>
                        <button v-if="collection.complete" type="button" class="btn dash-cta" :disabled="isMaking" @click="makeDeck">
                            {{ isMaking ? "만드는 중" : "PPT 만들기" }}
                        </button>
                        <p v-else class="board-note">다 모이면 부서 PPT를 만들 수 있습니다.</p>
                    </div>
                    <p v-else class="board-empty-title">취합 현황을 불러오지 못했습니다.</p>
                </section>
            </div>

            <section class="card board" aria-labelledby="todo-h">
                <header class="board-head">
                    <h2 id="todo-h" class="board-title">{{ focusStale ? "지난 할 일" : "다음 할 일" }}</h2>
                    <span v-if="focusBasis" class="board-meta" :class="{ 'is-danger': focusStale }">{{ focusBasis }}</span>
                </header>
                <div v-if="isBoardLoading" class="todo-grid" role="status" aria-label="다음 할 일을 불러오는 중">
                    <div v-for="n in 3" :key="n" class="todo-col" aria-hidden="true">
                        <span class="skel skel-line is-short"></span>
                        <span class="skel skel-line"></span>
                    </div>
                </div>
                <p v-else-if="loadError" class="board-error" role="alert">{{ loadError }}</p>
                <p v-else-if="!board.focus" class="board-empty-title">일일보고를 저장하면 다음 계획 · 이슈 · 요청이 여기 모입니다.</p>
                <div v-else class="todo-grid">
                    <div v-for="col in focusColumns" :key="col.key" class="todo-col" :class="`is-${col.key}`">
                        <h3 class="todo-title">{{ col.title }}</h3>
                        <ul v-if="col.items.length" class="todo-list">
                            <li v-for="(item, index) in col.items" :key="index">
                                {{ item.text }}<span v-if="item.project" class="todo-project"> · {{ item.project }}</span>
                            </li>
                        </ul>
                        <p v-else class="todo-none">없음</p>
                    </div>
                </div>
            </section>

            <section class="card board" aria-labelledby="weekly-h">
                <header class="board-head">
                    <h2 id="weekly-h" class="board-title">이번 주 주간보고</h2>
                    <span class="state-chip" :class="CHIP_TONE[weeklyCard.tone]">{{ weeklyCard.label }}</span>
                </header>
                <div class="board-body weekly-body">
                    <template v-if="weeklyEmph">
                        <p class="board-note">이번 주 일일보고로 금요일까지 만듭니다.</p>
                        <router-link class="btn dash-cta" :class="{ 'btn-primary': !todayHasCta }" :to="weeklyCard.to">{{ weeklyCard.action }}</router-link>
                    </template>
                    <router-link v-else class="btn btn-small" :to="weeklyCard.to">주간보고로 가기</router-link>
                </div>
            </section>

            <section class="card board" aria-labelledby="proj-h">
                <header class="board-head">
                    <h2 id="proj-h" class="board-title">내 프로젝트</h2>
                </header>
                <div v-if="isBoardLoading" class="board-body" role="status" aria-label="내 프로젝트를 불러오는 중">
                    <span class="skel skel-line is-short" aria-hidden="true"></span>
                    <span class="skel skel-line" aria-hidden="true"></span>
                </div>
                <div v-else-if="loadError" class="board-error" role="alert">
                    <span>{{ loadError }}</span>
                    <button type="button" class="btn btn-small" @click="loadBoard">다시 시도</button>
                </div>
                <div v-else-if="!board.projects.length" class="board-empty">
                    <p class="board-empty-title">일일보고를 저장하면 프로젝트별로 여기 모입니다.</p>
                    <router-link class="btn btn-small" to="/compose?kind=daily">첫 보고 쓰기</router-link>
                </div>
                <template v-else>
                    <div class="proj-chips" role="group" aria-label="프로젝트 고르기">
                        <button
                            v-for="project in board.projects"
                            :key="project.name"
                            type="button"
                            class="btn btn-small"
                            :class="{ 'is-active': project.name === selectedProject }"
                            :aria-pressed="project.name === selectedProject"
                            @click="chooseProject(project.name)"
                        >
                            {{ project.name }}
                        </button>
                    </div>
                    <div class="flow-wrap">
                        <table class="flow-table">
                            <caption>{{ selectedProject }} · 최근 일일보고 {{ flowRows.length }}건</caption>
                            <thead>
                                <tr>
                                    <th scope="col">날짜</th>
                                    <th v-for="col in FLOW_COLS" :key="col.key" scope="col">{{ col.label }}</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="row in flowRows" :key="row.key">
                                    <th scope="row"><router-link :to="row.href">{{ row.date }}</router-link></th>
                                    <td
                                        v-for="cell in row.cells"
                                        :key="cell.key"
                                        :data-label="cell.label"
                                        :class="{ 'is-danger': cell.key === 'issues' && cell.items.length, 'is-none': !cell.items.length }"
                                    >
                                        {{ cell.items.join(", ") || "없음" }}
                                    </td>
                                </tr>
                                <tr v-if="!flowRows.length">
                                    <td colspan="5" class="is-none">이 프로젝트의 일일보고가 없습니다.</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    <div class="board-foot">
                        <router-link class="btn btn-small" :to="{ path: '/project-timeline', query: { project: selectedProject } }">
                            전체 흐름 보기
                        </router-link>
                    </div>
                </template>
            </section>
        </template>
    </div>
</template>

<style scoped src="../styles/components/dashboard.css"></style>
