<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useMyWeek } from "../composables/useMyWeek";
import { useMyWeekly } from "../composables/useMyWeekly";
import { useTeamSummary } from "../composables/useTeamSummary";
import { focusColumnsOf } from "../lib/focusColumns";
import { todayIso } from "../lib/submissionGrid";

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

/* ---- 오늘 · 이번 주 ---------------------------------------------- */
const TODAY = {
    missing: { label: "아직 안 냄", tone: "muted", note: "오늘 보고는 오늘 안에 내면 됩니다.", action: "작성하기" },
    draft: { label: "임시 저장만 함", tone: "warning", note: "임시 저장은 제출이 아닙니다. 제출해야 집계에 들어갑니다.", action: "이어서 쓰기" },
    saved: { label: "제출됨", tone: "success", note: "오늘 할 일은 끝났습니다.", action: "" },
};
const todayCard = computed(() => TODAY[todayState.value] || null);

const CELL = {
    saved: { label: "제출", tone: "success" },
    missing: { label: "미제출", tone: "danger" },
    today: { label: "오늘", tone: "today" },
    upcoming: { label: "예정", tone: "upcoming" },
    holiday: { label: "휴", tone: "holiday" },
};
const weekCells = computed(() =>
    weekDays.value.map((day) => ({ ...day, ...CELL[day.state], slash: slashDate(day.date) })),
);
const missedDays = computed(() => weekDays.value.filter((day) => day.state === "missing"));
/** 내가 이번 주에 보고를 쓴 적이 있는지. 관리자는 이때만 내 보고 칸을 본다. */
const wroteThisWeek = computed(() => weekDays.value.some((day) => day.state === "saved"));

/* ---- 다음 할 일 ---------------------------------------------------- */
const STALE_DAYS = 7;
const board = ref({ projects: [], focus: null, history: [], projectNames: [] });
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
            done: item.done || [],
            doing: item.doing || [],
            issues: item.issues || [],
            next: item.next || [],
        })),
);
const loadBoard = async () => {
    loadError.value = "";
    try {
        board.value = await getDashboard(String(route.query.project || ""));
        // 고르지 않았으면 가장 최근 프로젝트를 먼저 펼친다.
        if (!route.query.project && board.value.projects?.length) chooseProject(board.value.projects[0].name);
    } catch (error) {
        console.error("내 현황 조회 실패:", error);
        loadError.value = "내 현황을 불러오지 못했습니다.";
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
            <section class="dash-card" aria-labelledby="all-today-h">
                <div class="dash-card-head">
                    <h2 id="all-today-h" class="dash-card-title">전체 오늘 제출</h2>
                    <p v-if="teamToday.length" class="dash-total">
                        오늘 <b>{{ todayTotal.done }}/{{ todayTotal.total }}명</b> 냄
                        <span v-if="todayTotal.left" class="is-danger">· 아직 안 낸 사람 {{ todayTotal.left }}명</span>
                    </p>
                </div>
                <p v-if="!teamToday.length" class="dash-empty">오늘은 보고하는 날이 아니거나, 집계할 사람이 없습니다.</p>
                <ul v-else class="dept-list">
                    <li v-for="team in teamToday" :key="teamKey(team)" class="dept-row">
                        <div class="dept-line">
                            <span class="dept-name">{{ team.teamName }}</span>
                            <span class="bar" aria-hidden="true"><span :style="{ width: `${pct(team.done, team.total)}%` }"></span></span>
                            <span class="dept-count" :class="{ 'is-all': !team.pending.length }">{{ team.done }}/{{ team.total }}명</span>
                        </div>
                        <p class="dept-missing">
                            <template v-if="team.pending.length">
                                <span class="dept-missing-label">아직 안 낸 사람</span>
                                <template v-if="openTeams.includes(teamKey(team))">{{ team.pending.join(", ") }}</template>
                                <template v-else>{{ team.pending.slice(0, PREVIEW).join(", ") }}</template>
                                <button v-if="team.pending.length > PREVIEW" type="button" class="link-btn"
                                    :aria-expanded="openTeams.includes(teamKey(team))" @click="toggleTeam(teamKey(team))">
                                    {{ openTeams.includes(teamKey(team)) ? "접기" : `외 ${team.pending.length - PREVIEW}명` }}
                                </button>
                            </template>
                            <span v-else class="is-success">모두 냄</span>
                        </p>
                    </li>
                </ul>
                <p class="dash-foot">안 낸 사람이 많은 부서부터. 오늘은 미제출로 세지 않고, 관리자 계정은 이번 기간에 낸 보고가 있을 때만 셉니다.</p>
            </section>

            <section v-if="collection" class="dash-card" aria-labelledby="all-week-h">
                <div class="dash-card-head">
                    <h2 id="all-week-h" class="dash-card-title">전체 주간 취합</h2>
                    <span class="dash-meta">{{ collection.week.label }} · {{ collection.submitted }}/{{ collection.total }}명</span>
                </div>
                <div class="collect-grid">
                    <div v-for="team in collection.teams" :key="team.id ?? team.name" class="collect-cell">
                        <div class="collect-top">
                            <span class="dept-name">{{ team.name }}</span>
                            <span v-if="team.submitted === team.total" class="pill is-success">모두 모임</span>
                        </div>
                        <span class="collect-count">{{ team.submitted }}/{{ team.total }}명</span>
                        <span class="bar" aria-hidden="true">
                            <span :class="{ 'is-full': team.submitted === team.total }"
                                :style="{ width: `${pct(team.submitted, team.total)}%` }"></span>
                        </span>
                    </div>
                </div>
                <router-link class="dash-link" to="/weekly">주간보고에서 취합하기</router-link>
            </section>

            <div v-if="wroteThisWeek" class="dash-row">
                <section class="dash-card is-narrow" aria-labelledby="own-today-h">
                    <h2 id="own-today-h" class="dash-card-title">내 오늘 일일보고</h2>
                    <template v-if="todayCard">
                        <p class="today-state" :class="`is-${todayCard.tone}`"><i aria-hidden="true"></i>{{ todayCard.label }}</p>
                        <router-link v-if="todayCard.action" class="btn btn-primary dash-cta" to="/compose?kind=daily">{{ todayCard.action }}</router-link>
                    </template>
                </section>
                <section class="dash-card is-wide" aria-labelledby="own-week-h">
                    <h2 id="own-week-h" class="dash-card-title">내 이번 주</h2>
                    <ol class="week-grid">
                        <li v-for="day in weekCells" :key="day.date" class="week-cell" :class="`is-${day.tone}`">
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
            <div class="dash-row">
                <section class="dash-card is-narrow" aria-labelledby="today-h">
                    <div class="dash-card-head">
                        <h2 id="today-h" class="dash-card-title">오늘 일일보고</h2>
                        <span class="dash-meta">{{ todayText }}</span>
                    </div>
                    <template v-if="todayCard">
                        <p class="today-state" :class="`is-${todayCard.tone}`"><i aria-hidden="true"></i>{{ todayCard.label }}</p>
                        <p class="dash-note">{{ todayCard.note }}</p>
                        <router-link v-if="todayCard.action" class="btn btn-primary dash-cta" to="/compose?kind=daily">{{ todayCard.action }}</router-link>
                    </template>
                    <template v-else>
                        <p class="today-state is-muted"><i aria-hidden="true"></i>보고하는 날이 아님</p>
                        <p class="dash-note">주말이나 공휴일에는 보고하지 않습니다.</p>
                    </template>
                </section>

                <section class="dash-card is-wide" aria-labelledby="week-h">
                    <h2 id="week-h" class="dash-card-title">이번 주</h2>
                    <ol class="week-grid">
                        <li v-for="day in weekCells" :key="day.date" class="week-cell" :class="`is-${day.tone}`"
                            :aria-label="`${day.weekday}요일 ${day.slash} ${day.label}`">
                            <span class="week-day">{{ day.weekday }}</span>
                            <span class="week-date">{{ day.slash }}</span>
                            <span class="week-state">{{ day.label }}</span>
                        </li>
                    </ol>
                    <div class="week-foot">
                        <span v-if="missedDays.length" class="is-danger">
                            빠진 보고 {{ missedDays.length }}건 · {{ missedDays.map((day) => longDate(day.date)).join(", ") }}
                        </span>
                        <span v-else class="is-success">빠진 보고 없음</span>
                        <span class="dash-foot-inline">오늘과 공휴일(휴)은 미제출로 세지 않습니다</span>
                    </div>
                </section>
            </div>

            <!-- 팀장: 우리 부서 -->
            <div v-if="role === 'leader'" class="dash-row">
                <section class="dash-card is-half" aria-labelledby="dept-today-h">
                    <h2 id="dept-today-h" class="dash-card-title">우리 부서 오늘 제출</h2>
                    <template v-if="myTeam">
                        <p class="dash-total">오늘 <b>{{ myTeam.done }}/{{ myTeam.total }}명</b> 냄</p>
                        <span class="bar" aria-hidden="true"><span :style="{ width: `${pct(myTeam.done, myTeam.total)}%` }"></span></span>
                        <p v-if="!myTeam.pending.length" class="is-success">모두 냈습니다.</p>
                        <div v-else-if="!openTeams.includes('mine')" class="dept-collapsed">
                            <p class="dept-missing">
                                <span class="dept-missing-label">아직 안 낸 사람</span>
                                {{ myTeam.pending.slice(0, PREVIEW).join(", ") }}
                                <span v-if="myTeam.pending.length > PREVIEW" class="dash-meta">외 {{ myTeam.pending.length - PREVIEW }}명</span>
                            </p>
                            <button v-if="myTeam.pending.length > PREVIEW" type="button" class="btn btn-small"
                                aria-expanded="false" @click="toggleTeam('mine')">전체 보기</button>
                        </div>
                        <div v-else class="dept-expanded">
                            <div class="dept-expanded-head">
                                <span class="dept-missing-label">아직 안 낸 사람 {{ myTeam.pending.length }}명</span>
                                <button type="button" class="btn btn-small" aria-expanded="true" @click="toggleTeam('mine')">접기</button>
                            </div>
                            <ul class="name-chips">
                                <li v-for="name in myTeam.pending" :key="name">{{ name }}</li>
                            </ul>
                        </div>
                        <p class="dash-foot">오늘은 아직 낼 수 있어 미제출로 세지 않습니다.</p>
                    </template>
                    <p v-else class="dash-empty">오늘은 보고하는 날이 아닙니다.</p>
                </section>

                <section class="dash-card is-half" aria-labelledby="dept-week-h">
                    <h2 id="dept-week-h" class="dash-card-title">우리 부서 주간 취합</h2>
                    <template v-if="collection">
                        <p class="dash-total"><b>{{ collection.submitted }}/{{ collection.total }}명</b> 제출</p>
                        <span class="bar" aria-hidden="true">
                            <span :class="{ 'is-full': collection.complete }" :style="{ width: `${pct(collection.submitted, collection.total)}%` }"></span>
                        </span>
                        <button v-if="collection.complete" type="button" class="btn btn-primary dash-cta" :disabled="isMaking" @click="makeDeck">
                            {{ isMaking ? "만드는 중" : "PPT 만들기" }}
                        </button>
                        <p v-else class="dash-note">다 모이면 부서 PPT를 만들 수 있습니다.</p>
                    </template>
                    <p v-else class="dash-empty">취합 현황을 불러오지 못했습니다.</p>
                </section>
            </div>

            <section class="dash-card" aria-labelledby="todo-h">
                <div class="dash-card-head">
                    <h2 id="todo-h" class="dash-card-title">{{ focusStale ? "지난 할 일" : "다음 할 일" }}</h2>
                    <span class="dash-meta" :class="{ 'is-danger': focusStale }">{{ focusBasis }}</span>
                </div>
                <p v-if="!board.focus" class="dash-empty">일일보고를 저장하면 다음 계획 · 이슈 · 요청이 여기 모입니다.</p>
                <div v-else class="todo-grid">
                    <div v-for="col in focusColumns" :key="col.key" class="todo-col" :class="`is-${col.key}`">
                        <h3 class="todo-title">{{ col.title }}</h3>
                        <ul v-if="col.items.length" class="todo-list">
                            <li v-for="(item, index) in col.items" :key="index">
                                {{ item.text }}<span v-if="item.project" class="todo-project"> · {{ item.project }}</span>
                            </li>
                        </ul>
                        <p v-else class="dash-empty">없음</p>
                    </div>
                </div>
            </section>

            <section v-if="weeklyEmph" class="dash-card weekly-card is-emph" aria-labelledby="weekly-h">
                <div class="weekly-text">
                    <div class="weekly-head">
                        <h2 id="weekly-h" class="dash-card-title">이번 주 주간보고</h2>
                        <span class="pill" :class="`is-${weeklyCard.tone}`">{{ weeklyCard.label }}</span>
                    </div>
                    <p class="dash-note">이번 주 일일보고로 금요일까지 만듭니다.</p>
                </div>
                <router-link class="btn btn-primary dash-cta" :to="weeklyCard.to">{{ weeklyCard.action }}</router-link>
            </section>
            <section v-else class="dash-card weekly-card" aria-labelledby="weekly-h2">
                <div class="weekly-head">
                    <h2 id="weekly-h2" class="dash-card-title">이번 주 주간보고</h2>
                    <span class="pill" :class="`is-${weeklyCard.tone}`">{{ weeklyCard.label }}</span>
                </div>
                <router-link class="dash-link" :to="weeklyCard.to">주간보고로 가기</router-link>
            </section>

            <section class="dash-card" aria-labelledby="proj-h">
                <h2 id="proj-h" class="dash-card-title">내 프로젝트</h2>
                <p v-if="loadError" class="dash-empty is-danger" role="alert">{{ loadError }}</p>
                <p v-else-if="!board.projects.length" class="dash-empty">
                    일일보고를 저장하면 프로젝트별로 여기 모입니다.
                    <router-link class="dash-link" to="/compose?kind=daily">첫 보고 쓰기</router-link>
                </p>
                <template v-else>
                    <div class="proj-chips" role="group" aria-label="프로젝트 고르기">
                        <button v-for="project in board.projects" :key="project.name" type="button" class="proj-chip"
                            :aria-pressed="project.name === selectedProject" @click="chooseProject(project.name)">
                            {{ project.name }}
                        </button>
                    </div>
                    <div class="flow-wrap">
                        <table class="flow-table">
                            <caption>{{ selectedProject }} · 최근 일일보고 {{ flowRows.length }}건</caption>
                            <thead>
                                <tr>
                                    <th scope="col">날짜</th>
                                    <th scope="col">완료</th>
                                    <th scope="col">진행</th>
                                    <th scope="col">이슈</th>
                                    <th scope="col">다음</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="row in flowRows" :key="row.key">
                                    <th scope="row"><router-link :to="row.href">{{ row.date }}</router-link></th>
                                    <td data-label="완료">{{ row.done.join(", ") || "—" }}</td>
                                    <td data-label="진행">{{ row.doing.join(", ") || "—" }}</td>
                                    <td data-label="이슈" :class="row.issues.length ? 'is-danger' : 'is-none'">{{ row.issues.join(", ") || "—" }}</td>
                                    <td data-label="다음">{{ row.next.join(", ") || "—" }}</td>
                                </tr>
                                <tr v-if="!flowRows.length">
                                    <td colspan="5" class="is-none">이 프로젝트의 일일보고가 없습니다.</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    <router-link class="dash-link" :to="{ path: '/project-timeline', query: { project: selectedProject } }">
                        전체 흐름 보기
                    </router-link>
                </template>
            </section>
        </template>
    </div>
</template>

<style scoped src="../styles/components/dashboard.css"></style>
