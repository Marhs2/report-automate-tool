<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { useMyWeek } from "../composables/useMyWeek";
import { useTeamSummary } from "../composables/useTeamSummary";
import { todayString, weekdayLabelOf } from "../lib/dateScope";
import { TEAM_LINKS } from "../lib/nav";
import { shiftWorkday, teamDay } from "../lib/teamDay";
import { weekDays, weekStatus } from "../lib/weekStatus";
import { errorMessage } from "../lib/errorMessage";
import KindTag from "./ui/KindTag.vue";
import WeekDots from "./ui/WeekDots.vue";

const { getReports, getUsers, getTeams } = useApi();
/** 남의 임시 저장은 볼 수 없지만 내 것은 안다. 내 줄만 "임시 저장"으로 보여 준다. */
const { todayState } = useMyWeek();
/** 팀장: 우리 부서 오늘 제출 · 주간 취합. 관리자: 부서별 오늘 제출 · 전체 주간 취합. 내 현황과 같은 값. */
const { role, teamToday, myTeam, pct, collection, myWeeklyTeam } = useTeamSummary();

const today = todayString();
const date = ref(today);
const onlyIssues = ref(false);
const reports = ref([]);
const users = ref([]);
const teams = ref([]);
const isLoading = ref(false);
const loadError = ref("");
const openId = ref(null);

const load = async () => {
    isLoading.value = true;
    loadError.value = "";
    try {
        const [reportRows, userRows, teamRows] = await Promise.all([getReports(), getUsers(), getTeams()]);
        reports.value = reportRows || [];
        users.value = userRows || [];
        teams.value = teamRows || [];
    } catch (error) {
        console.error("팀 화면 조회 실패:", error);
        loadError.value = errorMessage(error, "팀 보고를 불러오지 못했습니다.");
    } finally {
        isLoading.value = false;
    }
};

/* ---- 그날의 사람들 --------------------------------------------------- */
const day = computed(() =>
    teamDay({ reports: reports.value, users: users.value, teams: teams.value, date: date.value, today }),
);
const shown = computed(() =>
    onlyIssues.value ? day.value.people.filter((person) => person.issueCount) : day.value.people,
);
const isMe = (person) => String(person.memberId) === String(selectedUserId.value ?? "");

/** 보는 날이 속한 주의 월~금 점. 보고 목록을 이미 다 받아 두어 사람마다 바로 센다.
    shortcut: 공휴일 목록은 여기 없어 평일 휴일이 미제출 점으로 보인다, 휴일 API를 붙일 때 weekStatus의 holidays로 넘긴다. */
const DOT_STATE = { saved: "done", missing: "missing", today: "today", upcoming: "future", holiday: "holiday" };
const weekDots = computed(() => {
    const days = weekDays(date.value);
    const savedByMember = new Map();
    for (const report of reports.value) {
        const key = String(report.member_id);
        if (!savedByMember.has(key)) savedByMember.set(key, new Set());
        savedByMember.get(key).add(String(report.report_date));
    }
    return new Map(
        day.value.people.map((person) => [
            person.memberId,
            weekStatus(days, savedByMember.get(String(person.memberId)) || new Set(), today).map((entry) => ({
                label: entry.weekday,
                state: entry.state === "saved" && entry.date === today ? "today-done" : DOT_STATE[entry.state],
            })),
        ]),
    );
});

/** 처음 들어오면 첫 보고 하나를 펼쳐 둔다. 누르면 펼쳐진다는 걸 보여 주려고. */
watch(
    () => [date.value, day.value.people.length],
    () => {
        openId.value = day.value.people.find((person) => person.reportId)?.memberId ?? null;
    },
);

const toggle = (person) => {
    if (!person.reportId) return;
    openId.value = openId.value === person.memberId ? null : person.memberId;
};

const dateLabel = computed(() => {
    const [, month, dayNumber] = date.value.split("-").map(Number);
    const prefix = date.value === today ? "오늘 · " : "";
    return `${prefix}${month}월 ${dayNumber}일 ${weekdayLabelOf(date.value)}요일`;
});

/* ---- 줄마다 보이는 상태 ----------------------------------------------- */
const STATES = {
    submitted: { label: "제출함", tone: "is-success" },
    waiting: { label: "아직", tone: "is-plain" },
    missing: { label: "빠짐", tone: "is-danger" },
    upcoming: { label: "예정", tone: "is-plain" },
};

const isMyDraft = (person) => isMe(person) && person.status === "waiting" && todayState.value === "draft";
const stateOf = (person) => (isMyDraft(person) ? { label: "임시 저장", tone: "is-warning" } : STATES[person.status]);

const subOf = (person) => {
    if (isMyDraft(person)) return "쓰는 중 · 제출하면 팀에 보여요";
    if (person.status !== "submitted") return person.status === "missing" ? "이날 보고가 없어요" : "아직 쓰지 않았어요";
    const issue = person.lines.find((line) => line.kind === "issue");
    if (issue) return `이슈 ${person.issueCount} · ${issue.text}`;
    return person.lines[0]?.text || "내용 없음";
};

const metaOf = (person) => [person.team, ...person.projects].filter(Boolean).join(" · ");

/* ---- 오른쪽 집계(팀장 · 관리자, 오늘만) ------------------------------- */
const isToday = computed(() => date.value === today);
const showLeaderBoards = computed(() => role.value === "leader" && isToday.value && Boolean(myTeam.value || collection.value));
const showAdminBoards = computed(() => role.value === "admin" && isToday.value && Boolean(teamToday.value.length || collection.value));
const hasAside = computed(() => showLeaderBoards.value || showAdminBoards.value);
/** 관리자는 부서 보드에 안 낸 사람이 다 있으니 사람 보드의 같은 줄은 숨긴다. */
const showNotYet = computed(() => day.value.notYet.length && !onlyIssues.value && !(role.value === "admin" && isToday.value));

onMounted(load);
</script>

<template>
    <div class="page team-page" :class="{ 'has-aside': hasAside }">
        <div class="team-main">
            <section class="card board team-board" aria-labelledby="team-day-title">
                <header class="board-head team-head">
                    <div class="team-date-nav">
                        <button type="button" class="icon-btn" aria-label="전날" @click="date = shiftWorkday(date, -1)">
                            <ChevronLeft :size="20" />
                        </button>
                        <h2 id="team-day-title" class="team-date">{{ dateLabel }}</h2>
                        <button
                            type="button"
                            class="icon-btn"
                            aria-label="다음날"
                            :disabled="date >= today"
                            @click="date = shiftWorkday(date, 1)"
                        >
                            <ChevronRight :size="20" />
                        </button>
                    </div>
                    <div class="seg" role="group" aria-label="보기">
                        <button type="button" :class="{ 'is-on': !onlyIssues }" :aria-pressed="!onlyIssues" @click="onlyIssues = false">전체</button>
                        <button type="button" :class="{ 'is-on': onlyIssues }" :aria-pressed="onlyIssues" @click="onlyIssues = true">이슈만</button>
                    </div>
                </header>

                <div v-if="!isLoading && !loadError && day.total" class="team-count-row">
                    <p class="team-count"><b>{{ day.submitted }}</b> / {{ day.total }}명 제출</p>
                    <p v-if="showNotYet" class="team-notyet">
                        아직 안 낸 사람: {{ day.notYet.map((person) => person.name).join(", ") }}
                    </p>
                </div>

                <div v-if="isLoading" class="team-skel" role="status" aria-label="팀 보고를 불러오는 중">
                    <div v-for="n in 3" :key="n" class="team-skel-row" aria-hidden="true">
                        <span class="skel skel-avatar"></span>
                        <span class="skel-lines">
                            <span class="skel skel-line"></span>
                            <span class="skel skel-line is-short"></span>
                        </span>
                    </div>
                </div>

                <div v-else-if="loadError" class="board-error" role="alert">
                    <span>{{ loadError }}</span>
                    <button type="button" class="btn btn-small" @click="load">다시 시도</button>
                </div>

                <template v-else>
                    <div v-if="shown.length" class="team-list">
                        <div
                            v-for="person in shown"
                            :key="person.memberId"
                            class="team-person"
                            :class="{ 'is-open': openId === person.memberId }"
                        >
                            <button
                                type="button"
                                class="team-row"
                                :class="{ 'is-static': !person.reportId }"
                                :aria-expanded="person.reportId ? openId === person.memberId : null"
                                :disabled="!person.reportId"
                                @click="toggle(person)"
                            >
                                <span class="avatar" :class="{ 'is-me': isMe(person) }">{{ person.name.slice(0, 1) }}</span>
                                <span class="team-row-main">
                                    <span class="team-row-top">
                                        <span class="team-name">{{ person.name }}</span>
                                        <span v-if="isMe(person)" class="team-me">나</span>
                                        <span v-if="metaOf(person)" class="team-meta">{{ metaOf(person) }}</span>
                                    </span>
                                    <span v-if="openId !== person.memberId" class="team-sub">{{ subOf(person) }}</span>
                                </span>
                                <span class="team-row-end">
                                    <WeekDots :days="weekDots.get(person.memberId)" />
                                    <span class="state-chip" :class="stateOf(person).tone">{{ stateOf(person).label }}</span>
                                    <ChevronDown v-if="person.reportId" :size="18" class="team-chevron" aria-hidden="true" />
                                </span>
                            </button>
                            <div v-if="openId === person.memberId" class="team-lines">
                                <p v-for="(line, index) in person.lines" :key="index" class="team-line">
                                    <KindTag :kind="line.kind" :label="line.label" />
                                    <span class="team-line-text">
                                        {{ line.text }}
                                        <span v-if="person.projects.length > 1" class="team-line-project">{{ line.project }}</span>
                                    </span>
                                </p>
                                <router-link
                                    class="btn btn-small team-raw"
                                    :to="{ path: `/report-result/${person.reportId}`, query: { from: 'team' } }"
                                >
                                    원문 보기
                                </router-link>
                            </div>
                        </div>
                    </div>
                    <div v-else class="board-empty">
                        <p class="board-empty-title">{{ onlyIssues ? "이날 올라온 이슈가 없어요" : "보고할 팀원이 없어요" }}</p>
                        <button v-if="onlyIssues" type="button" class="btn btn-small" @click="onlyIssues = false">전체 보기</button>
                    </div>
                </template>
            </section>

            <nav class="team-links" aria-label="팀 화면 더 보기">
                <router-link v-for="link in TEAM_LINKS" :key="link.to" :to="link.to" class="btn">
                    {{ link.label }}
                </router-link>
            </nav>
        </div>

        <aside v-if="hasAside" class="team-aside" aria-label="부서 집계">
            <!-- 팀장: 오늘 기준 요약이라 다른 날을 볼 때는 숨긴다. -->
            <template v-if="showLeaderBoards">
                <section v-if="myTeam" class="card board" aria-labelledby="team-mine-title">
                    <header class="board-head">
                        <h2 id="team-mine-title" class="board-title">우리 부서 오늘 제출</h2>
                        <span class="board-num">{{ myTeam.done }} / {{ myTeam.total }}명</span>
                    </header>
                    <div class="board-body">
                        <span class="bar" role="img" :aria-label="`${myTeam.total}명 중 ${myTeam.done}명 제출`">
                            <span :class="{ 'is-full': !myTeam.pending.length }" :style="{ width: `${pct(myTeam.done, myTeam.total)}%` }"></span>
                        </span>
                        <p class="board-note">
                            <template v-if="myTeam.pending.length">아직 안 낸 사람 <b>{{ myTeam.pending.join(", ") }}</b></template>
                            <template v-else>모두 냈어요</template>
                        </p>
                    </div>
                </section>
                <section v-if="collection" class="card board" aria-labelledby="team-collect-mine-title">
                    <header class="board-head">
                        <h2 id="team-collect-mine-title" class="board-title">이번 주 부서 주간보고</h2>
                        <span class="state-chip" :class="myWeeklyTeam?.submitted ? 'is-success' : 'is-warning'">{{ myWeeklyTeam?.submitted ? "만듦" : "아직 안 만듦" }}</span>
                    </header>
                    <div class="board-body">
                        <p v-if="myWeeklyTeam?.submitted" class="board-note">{{ myWeeklyTeam.authorName || "팀장" }} 작성 · {{ collection.week.label }}</p>
                        <router-link v-if="myWeeklyTeam?.submitted" class="btn" :to="`/weekly-detail/${myWeeklyTeam.weeklyId}`">주간보고 열기</router-link>
                        <router-link v-else class="btn btn-primary" to="/weekly">부서 주간보고 만들기</router-link>
                    </div>
                </section>
            </template>

            <template v-if="showAdminBoards">
                <section v-if="teamToday.length" class="card board" aria-labelledby="team-depts-title">
                    <header class="board-head">
                        <h2 id="team-depts-title" class="board-title">부서별 오늘 제출</h2>
                        <span class="board-meta">안 낸 사람이 많은 부서부터</span>
                    </header>
                    <ul class="dept-list">
                        <li v-for="team in teamToday" :key="team.teamId ?? 'none'" class="dept-row">
                            <div class="dept-line">
                                <span class="dept-name">{{ team.teamName }}</span>
                                <span class="bar" role="img" :aria-label="`${team.total}명 중 ${team.done}명 제출`">
                                    <span :class="{ 'is-full': !team.pending.length }" :style="{ width: `${pct(team.done, team.total)}%` }"></span>
                                </span>
                                <span class="dept-count" :class="team.pending.length ? 'is-low' : 'is-all'">{{ team.done }}/{{ team.total }}명</span>
                            </div>
                            <p class="dept-who">{{ team.pending.length ? `아직 안 낸 사람 ${team.pending.join(", ")}` : "모두 냄" }}</p>
                        </li>
                    </ul>
                </section>
                <section v-if="collection" class="card board" aria-labelledby="team-collect-title">
                    <header class="board-head">
                        <h2 id="team-collect-title" class="board-title">전체 주간 취합</h2>
                        <span class="board-meta">{{ collection.week.label }} · <b class="board-meta-num">{{ collection.submitted }} / {{ collection.total }}개 부서</b></span>
                    </header>
                    <ul class="dept-list">
                        <li v-for="team in collection.teams" :key="team.id ?? team.name" class="dept-row">
                            <div class="dept-line">
                                <span class="dept-name">{{ team.name }}</span>
                                <span class="dept-count" :class="team.submitted ? 'is-all' : 'is-low'">{{ team.submitted ? "제출" : "미제출" }}</span>
                            </div>
                            <p v-if="team.submitted" class="dept-who">{{ team.authorName }} 작성</p>
                        </li>
                    </ul>
                    <div class="board-foot">
                        <router-link class="btn btn-small" to="/weekly">주간보고에서 취합하기</router-link>
                    </div>
                </section>
            </template>
        </aside>
    </div>
</template>

<style scoped src="../styles/components/team.css"></style>
