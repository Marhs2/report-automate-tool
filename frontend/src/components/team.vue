<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { ChevronLeft, ChevronRight } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { useMyWeek } from "../composables/useMyWeek";
import { useTeamSummary } from "../composables/useTeamSummary";
import { todayString, weekdayLabelOf } from "../lib/dateScope";
import { TEAM_LINKS } from "../lib/nav";
import { shiftWorkday, teamDay } from "../lib/teamDay";
import { errorMessage } from "../lib/errorMessage";
import KindTag from "./ui/KindTag.vue";

const { getReports, getUsers, getTeams } = useApi();
/** 남의 임시 저장은 볼 수 없지만 내 것은 안다. 내 줄만 "임시 저장"으로 보여 준다. */
const { todayState } = useMyWeek();
/** 팀장: 우리 부서 오늘 제출 · 주간 취합. 관리자: 부서별 오늘 제출 · 전체 주간 취합. 내 현황과 같은 값. */
const { role, teamToday, myTeam, pct, collection, isMaking, makeDeck } = useTeamSummary();

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

const day = computed(() =>
    teamDay({ reports: reports.value, users: users.value, teams: teams.value, date: date.value, today }),
);
const shown = computed(() =>
    onlyIssues.value ? day.value.people.filter((person) => person.issueCount) : day.value.people,
);

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

const summary = computed(() => {
    if (!day.value.total) return "보고할 팀원이 없어요.";
    return `${day.value.total}명 중 ${day.value.submitted}명이 제출했어요`;
});

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

const isMe = (person) => String(person.memberId) === String(selectedUserId.value ?? "");

onMounted(load);
</script>

<template>
    <div class="page team-page">
        <div class="team-head">
            <div class="team-day">
                <div class="team-date-nav">
                    <button type="button" class="btn btn-ghost btn-small team-step" aria-label="전날" @click="date = shiftWorkday(date, -1)">
                        <ChevronLeft :size="18" />
                    </button>
                    <span class="team-date">{{ dateLabel }}</span>
                    <button
                        type="button"
                        class="btn btn-ghost btn-small team-step"
                        aria-label="다음날"
                        :disabled="date >= today"
                        @click="date = shiftWorkday(date, 1)"
                    >
                        <ChevronRight :size="18" />
                    </button>
                </div>
                <p class="team-summary">{{ summary }}</p>
            </div>
            <div class="seg" role="group" aria-label="보기">
                <button type="button" :class="{ 'is-on': !onlyIssues }" :aria-pressed="!onlyIssues" @click="onlyIssues = false">전체</button>
                <button type="button" :class="{ 'is-on': onlyIssues }" :aria-pressed="onlyIssues" @click="onlyIssues = true">이슈만</button>
            </div>
        </div>

        <!-- 팀장 · 관리자에게만. 오늘 기준 요약이라 다른 날을 볼 때는 숨긴다. -->
        <div v-if="role === 'leader' && date === today && (myTeam || collection)" class="team-summary-cards">
            <section v-if="myTeam" class="team-card">
                <p class="team-card-label">우리 부서 오늘 제출</p>
                <p class="team-card-num">{{ myTeam.done }} / {{ myTeam.total }}명</p>
                <span class="bar" role="img" :aria-label="`${myTeam.total}명 중 ${myTeam.done}명 제출`">
                    <span :class="{ 'is-full': !myTeam.pending.length }" :style="{ width: `${pct(myTeam.done, myTeam.total)}%` }"></span>
                </span>
                <p class="team-card-note">
                    <template v-if="myTeam.pending.length">아직 안 낸 사람 <b>{{ myTeam.pending.join(", ") }}</b></template>
                    <template v-else>모두 냈어요</template>
                </p>
            </section>
            <section v-if="collection" class="team-card">
                <p class="team-card-label">이번 주 주간 취합</p>
                <p class="team-card-num">{{ collection.submitted }} / {{ collection.total }}명</p>
                <span class="bar" role="img" :aria-label="`${collection.total}명 중 ${collection.submitted}명 주간보고 제출`">
                    <span :class="{ 'is-full': collection.complete }" :style="{ width: `${pct(collection.submitted, collection.total)}%` }"></span>
                </span>
                <button v-if="collection.complete" type="button" class="btn btn-primary" :disabled="isMaking" @click="makeDeck">
                    {{ isMaking ? "만드는 중" : "부서 PPT 만들기" }}
                </button>
                <p v-else class="team-card-note">다 모이면 부서 PPT를 만들 수 있어요.</p>
            </section>
        </div>

        <template v-if="role === 'admin' && date === today">
            <section v-if="teamToday.length" class="team-depts" aria-labelledby="team-depts-title">
                <h2 id="team-depts-title" class="team-section-label">부서별 오늘 제출 · 안 낸 사람이 많은 부서부터</h2>
                <div class="group team-list">
                    <div v-for="team in teamToday" :key="team.teamId ?? 'none'" class="team-dept">
                        <span class="team-dept-name">{{ team.teamName }}</span>
                        <span class="bar" role="img" :aria-label="`${team.total}명 중 ${team.done}명 제출`">
                            <span :class="{ 'is-full': !team.pending.length }" :style="{ width: `${pct(team.done, team.total)}%` }"></span>
                        </span>
                        <span class="team-dept-count" :class="team.pending.length ? 'is-low' : 'is-all'">{{ team.done }}/{{ team.total }}명</span>
                        <span class="team-dept-who">{{ team.pending.length ? `아직 안 낸 사람 ${team.pending.join(", ")}` : "모두 냄" }}</span>
                    </div>
                </div>
            </section>
            <section v-if="collection" class="team-depts" aria-labelledby="team-collect-title">
                <h2 id="team-collect-title" class="team-section-label">
                    전체 주간 취합 · {{ collection.week.label }} · {{ collection.submitted }} / {{ collection.total }}명
                </h2>
                <div class="group team-list">
                    <div v-for="team in collection.teams" :key="team.id ?? team.name" class="team-dept is-plain">
                        <span class="team-dept-name">{{ team.name }}</span>
                        <span class="team-dept-count">{{ team.submitted }}/{{ team.total }}명</span>
                    </div>
                    <router-link class="team-dept-link" to="/weekly">주간보고에서 취합하기</router-link>
                </div>
            </section>
        </template>

        <p v-if="isLoading" class="list-status" role="status">불러오는 중</p>
        <p v-else-if="loadError" class="list-status is-error" role="alert">{{ loadError }}</p>

        <template v-else>
            <p v-if="day.notYet.length && !onlyIssues && !(role === 'admin' && date === today)" class="team-notyet">
                아직 안 낸 사람: {{ day.notYet.map((person) => person.name).join(", ") }}
            </p>

            <div v-if="shown.length" class="group team-list">
                <div
                    v-for="person in shown"
                    :key="person.memberId"
                    class="team-person"
                    :class="{ 'is-open': openId === person.memberId }"
                >
                    <button
                        type="button"
                        class="row team-row"
                        :class="{ 'is-static': !person.reportId }"
                        :aria-expanded="person.reportId ? openId === person.memberId : null"
                        :disabled="!person.reportId"
                        @click="toggle(person)"
                    >
                        <span class="avatar">{{ person.name.slice(0, 1) }}</span>
                        <span class="row-main">
                            <span class="row-title">
                                {{ person.name }}
                                <span class="team-meta">{{ [isMe(person) ? "나" : "", person.team, ...person.projects].filter(Boolean).join(" · ") }}</span>
                            </span>
                            <span v-if="openId !== person.memberId" class="row-sub">{{ subOf(person) }}</span>
                        </span>
                        <span class="state-chip" :class="stateOf(person).tone">{{ stateOf(person).label }}</span>
                    </button>
                    <div v-if="openId === person.memberId" class="team-lines">
                        <p v-for="(line, index) in person.lines" :key="index" class="team-line">
                            <KindTag :kind="line.kind" :label="line.label" />
                            <span class="team-line-text">
                                {{ line.text }}
                                <span v-if="person.projects.length > 1" class="team-line-project">{{ line.project }}</span>
                            </span>
                        </p>
                        <router-link class="team-raw" :to="{ path: `/report-result/${person.reportId}`, query: { from: 'team' } }">
                            원문 보기
                        </router-link>
                    </div>
                </div>
            </div>
            <div v-else class="empty-state">
                <p class="empty-title">{{ onlyIssues ? "이날 올라온 이슈가 없어요" : "보고할 팀원이 없어요" }}</p>
            </div>

            <p class="team-hint">사람을 누르면 그날 보고가 펼쳐져요.</p>
        </template>

        <nav class="team-links" aria-label="팀 화면 더 보기">
            <router-link v-for="link in TEAM_LINKS" :key="link.to" :to="link.to" class="btn btn-ghost">
                {{ link.label }}
            </router-link>
        </nav>
    </div>
</template>

<style scoped src="../styles/components/team.css"></style>
