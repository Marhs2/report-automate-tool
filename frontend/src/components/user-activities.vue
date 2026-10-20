<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Check, ChevronDown, ChevronLeft, ChevronRight, Search, X } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import { isAdmin, leaderTeamId } from "../composables/useSession";
import {
    buildRows,
    dayHeader,
    periodDays,
    periodLabel,
    shiftAnchor,
    todayIso,
} from "../lib/submissionGrid";

const router = useRouter();
const { alert: showAlert } = useDialog();
const { getUserActivities, getHolidays, getTeams, getUsers } = useApi();

const MODES = [
    { id: "week", label: "주", current: "이번 주" },
    { id: "month", label: "월", current: "이번 달" },
];

const today = todayIso();
/** 이보다 많으면 처음에 부서를 접고 이름 검색을 둔다. */
const MANY_PEOPLE = 12;
const TODAY_NAME_LIMIT = 6;
const mode = ref("week");
const anchor = ref(today);
// 팀장은 자기 부서부터 본다. 다른 부서도 고를 수 있다.
const filterTeam = ref(!isAdmin.value && leaderTeamId.value ? String(leaderTeamId.value) : "all");
const missedFirst = ref(false);
const query = ref("");
const onlyMissed = ref(false);
const collapsed = ref(new Set());
let collapseReady = false;

const activities = ref([]);
const holidays = ref({});
const teams = ref([]);
const adminIds = ref(new Set());
const isLoading = ref(false);
const loadError = ref("");

const days = computed(() => periodDays(mode.value, anchor.value));
const headers = computed(() => days.value.map((date) => dayHeader(date, holidays.value)));
const label = computed(() => periodLabel(mode.value, days.value));
const isCurrent = computed(() => days.value.includes(today) || periodLabel(mode.value, periodDays(mode.value, today)) === label.value);
const currentLabel = computed(() => MODES.find((item) => item.id === mode.value)?.current || "");

const teamNames = computed(() =>
    Object.fromEntries(teams.value.map((team) => [String(team.id), team.team_name])),
);

const baseOptions = computed(() => ({
    today,
    holidays: holidays.value,
    adminIds: adminIds.value,
    teamNames: teamNames.value,
    teamFilter: filterTeam.value,
    missedFirst: missedFirst.value,
}));
/** 검색 · 미제출만과 상관없는 전체. 요약 줄과 인원 수는 이것으로 센다. */
const allRows = computed(() => buildRows(activities.value, days.value, baseOptions.value));
const rows = computed(() =>
    buildRows(activities.value, days.value, {
        ...baseOptions.value,
        query: query.value,
        onlyMissed: onlyMissed.value,
    }),
);
const peopleCount = computed(() => allRows.value.reduce((sum, team) => sum + team.members.length, 0));
const isMany = computed(() => peopleCount.value > MANY_PEOPLE);

const teamKey = (team) => String(team.teamId ?? "none");
/** 검색하거나 미제출만 볼 때는 찾은 사람이 숨지 않게 모두 펼친다. */
const isCollapsed = (team) =>
    !query.value.trim() && !onlyMissed.value && collapsed.value.has(teamKey(team));
const toggleTeam = (team) => {
    const next = new Set(collapsed.value);
    const key = teamKey(team);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    collapsed.value = next;
};
/** 처음 한 번만: 사람이 많으면 부서를 접는다. 팀장은 자기 부서를 펼친 채로 본다. */
const initCollapse = () => {
    if (collapseReady || !activities.value.length || !teams.value.length) return;
    collapseReady = true;
    if (!isMany.value) return;
    const own = leaderTeamId.value != null ? String(leaderTeamId.value) : "";
    collapsed.value = new Set(allRows.value.map(teamKey).filter((key) => key !== own));
};

const dayCountText = (count) => {
    if (count.off && !count.done) return "휴";
    if (count.future && !count.done) return "·";
    return `${count.done}/${count.total}`;
};
const dayCountTone = (count) => {
    if (count.missed) return "is-missed";
    if (count.total && count.done === count.total) return "is-done";
    return "";
};

const totals = computed(() => {
    const submitted = rows.value.reduce((sum, team) => sum + team.submitted, 0);
    const due = rows.value.reduce((sum, team) => sum + team.due, 0);
    return { submitted, due, pct: due ? Math.round((submitted / due) * 100) : 0 };
});

/** 오늘 아직 안 낸 사람. 오늘이 평일이고 보는 기간 안일 때만. */
const todayMissing = computed(() => {
    const index = days.value.indexOf(today);
    if (index < 0 || holidays.value[today]) return [];
    return allRows.value.flatMap((team) =>
        team.members.filter((member) => member.cells[index].state !== "done").map((member) => member.name),
    );
});
const todayMissingShown = computed(() => todayMissing.value.slice(0, TODAY_NAME_LIMIT));
const todayMissingMore = computed(() => Math.max(0, todayMissing.value.length - TODAY_NAME_LIMIT));

const load = async () => {
    isLoading.value = true;
    loadError.value = "";
    try {
        const start = days.value[0];
        const end = days.value.at(-1);
        const years = [...new Set([start.slice(0, 4), end.slice(0, 4)])];
        const [rowsData, ...holidayLists] = await Promise.all([
            getUserActivities(Number(start.slice(0, 4)), Number(start.slice(5, 7)), start, end),
            ...years.map((year) => getHolidays(Number(year))),
        ]);
        activities.value = rowsData || [];
        holidays.value = Object.fromEntries(
            holidayLists.flat().filter((row) => row?.date).map((row) => [row.date, row.name]),
        );
        initCollapse();
    } catch (error) {
        console.error("사용자 활동 조회 실패:", error);
        activities.value = [];
        loadError.value = "제출 현황을 불러오지 못했습니다.";
    } finally {
        isLoading.value = false;
    }
};

const loadTeams = async () => {
    try {
        const [teamRows, users] = await Promise.all([getTeams(), getUsers().catch(() => [])]);
        teams.value = teamRows || [];
        adminIds.value = new Set((users || []).filter((user) => user.is_admin).map((user) => String(user.id)));
        initCollapse();
    } catch (error) {
        console.error("부서 조회 실패:", error);
        showAlert("부서를 불러오지 못했습니다.");
    }
};

const setMode = (next) => {
    if (mode.value === next) return;
    mode.value = next;
    load();
};
const shift = (step) => {
    anchor.value = shiftAnchor(mode.value, anchor.value, step);
    load();
};
const goCurrent = () => {
    anchor.value = today;
    load();
};

const openReport = (member, cell) => {
    if (!cell.reportId) return;
    router.push({ name: "report-result", params: { id: cell.reportId }, query: { from: "activities" } });
};

const cellTitle = (member, header, cell) => {
    const when = `${header.weekLabel} ${header.day}일`;
    if (cell.state === "done") return `${member.name} · ${when} 제출 (눌러서 보기)`;
    if (cell.state === "missed") return `${member.name} · ${when} 미제출`;
    if (cell.date === today) return `${member.name} · 오늘 아직 안 냄`;
    if (cell.state === "off") return `${when} ${header.holidayName}`;
    return `${member.name} · ${when} 예정`;
};

onMounted(() => {
    loadTeams();
    load();
});
</script>

<template>
    <div class="page">
        <header class="view-head">
            <div class="view-head-text">
                <p class="view-period">
                    {{ label }}
                    <span v-if="isCurrent" class="cat-tag is-progress">{{ currentLabel }}</span>
                </p>
            </div>
            <div class="view-nav">
                <div class="seg" role="tablist" aria-label="보는 기간">
                    <button
                        v-for="item in MODES"
                        :key="item.id"
                        type="button"
                        role="tab"
                        :aria-selected="mode === item.id"
                        :class="{ 'is-on': mode === item.id }"
                        @click="setMode(item.id)"
                    >
                        {{ item.label }}
                    </button>
                </div>
                <select v-model="filterTeam" class="input team-filter" aria-label="부서">
                    <option value="all">전체 부서</option>
                    <option v-for="team in teams" :key="team.id" :value="String(team.id)">
                        {{ team.team_name }}
                    </option>
                </select>
                <div class="stepper" role="group" aria-label="기간 이동">
                    <button type="button" :aria-label="mode === 'week' ? '이전 주' : '이전 달'" @click="shift(-1)">
                        <ChevronLeft :size="16" />
                    </button>
                    <button type="button" class="stepper-reset" :disabled="isCurrent" @click="goCurrent">
                        {{ currentLabel }}
                    </button>
                    <button type="button" :aria-label="mode === 'week' ? '다음 주' : '다음 달'" @click="shift(1)">
                        <ChevronRight :size="16" />
                    </button>
                </div>
            </div>
        </header>

        <div class="grid-summary">
            <p v-if="todayMissing.length" class="summary-today" :title="todayMissing.join(', ')">
                <strong>오늘 아직 안 냄 {{ todayMissing.length }}명</strong>
                <span>
                    {{ todayMissingShown.join(", ") }}<template v-if="todayMissingMore"> 외 {{ todayMissingMore }}명</template>
                </span>
            </p>
            <p v-else-if="days.includes(today)" class="summary-today is-done">
                <strong>오늘 모두 제출했어요</strong>
            </p>
            <p class="summary-rate">
                제출 {{ totals.submitted }}/{{ totals.due }}<template v-if="totals.due"> · {{ totals.pct }}%</template>
            </p>
            <div class="grid-tools">
                <label v-if="isMany" class="name-search">
                    <Search :size="14" aria-hidden="true" />
                    <input v-model="query" class="input" type="search" placeholder="이름 찾기" aria-label="이름 찾기" />
                </label>
                <button
                    type="button"
                    class="btn btn-small"
                    :class="{ on: onlyMissed }"
                    :aria-pressed="onlyMissed"
                    @click="onlyMissed = !onlyMissed"
                >
                    빠진 날 있는 사람만
                </button>
                <button
                    type="button"
                    class="btn btn-small"
                    :class="{ on: missedFirst }"
                    :aria-pressed="missedFirst"
                    @click="missedFirst = !missedFirst"
                >
                    빠진 날 많은 순
                </button>
            </div>
        </div>

        <p v-if="isLoading && !activities.length" class="list-status" role="status">불러오는 중</p>
        <p v-else-if="loadError" class="list-status is-error" role="alert">{{ loadError }}</p>
        <div v-else-if="!rows.length" class="empty-state">
            {{ query.trim() ? `'${query.trim()}' 이름이 없습니다` : onlyMissed ? "빠진 날이 있는 사람이 없습니다" : "이 기간에 볼 사람이 없습니다" }}
        </div>

        <section v-else class="card grid-card" aria-label="일일보고 제출 표">
            <div class="grid-scroll">
                <table class="sub-grid" :class="`is-${mode}`">
                    <thead>
                        <tr>
                            <th scope="col" class="col-who">이름</th>
                            <th
                                v-for="header in headers"
                                :key="header.date"
                                scope="col"
                                class="col-day"
                                :class="{ 'is-today': header.date === today, 'is-holiday': header.holidayName }"
                                :title="header.holidayName || undefined"
                            >
                                <span class="day-week">{{ header.weekLabel }}</span>
                                <span class="day-num">{{ header.day }}</span>
                            </th>
                            <th scope="col" class="col-rate">제출</th>
                        </tr>
                    </thead>
                    <tbody v-for="team in rows" :key="teamKey(team)">
                        <tr class="team-row" :class="{ 'is-collapsed': isCollapsed(team) }">
                            <th scope="rowgroup" class="col-who">
                                <button
                                    type="button"
                                    class="team-toggle"
                                    :aria-expanded="!isCollapsed(team)"
                                    @click="toggleTeam(team)"
                                >
                                    <ChevronRight v-if="isCollapsed(team)" :size="14" aria-hidden="true" />
                                    <ChevronDown v-else :size="14" aria-hidden="true" />
                                    <span class="team-name">{{ team.teamName }}</span>
                                    <span class="team-size">{{ team.members.length }}명</span>
                                </button>
                            </th>
                            <template v-if="isCollapsed(team)">
                                <td
                                    v-for="count in team.dayCounts"
                                    :key="count.date"
                                    class="col-day"
                                    :class="{ 'is-today': count.date === today }"
                                >
                                    <span class="team-count" :class="dayCountTone(count)">{{ dayCountText(count) }}</span>
                                </td>
                                <td class="col-rate" :class="{ 'has-missed': team.submitted < team.due }">
                                    {{ team.submitted }}/{{ team.due }}
                                </td>
                            </template>
                            <td v-else :colspan="headers.length + 1" class="team-meta">
                                {{ team.submitted }}/{{ team.due }}
                            </td>
                        </tr>
                        <tr v-for="member in isCollapsed(team) ? [] : team.members" :key="member.memberId">
                            <th scope="row" class="col-who">{{ member.name }}</th>
                            <td
                                v-for="(cell, index) in member.cells"
                                :key="cell.date"
                                class="col-day"
                                :class="[`is-${cell.state}`, { 'is-today': cell.date === today }]"
                            >
                                <button
                                    v-if="cell.state === 'done'"
                                    type="button"
                                    class="cell-mark"
                                    :aria-label="cellTitle(member, headers[index], cell)"
                                    :title="cellTitle(member, headers[index], cell)"
                                    @click="openReport(member, cell)"
                                >
                                    <Check :size="15" :stroke-width="2.5" />
                                </button>
                                <span
                                    v-else
                                    class="cell-mark"
                                    :aria-label="cellTitle(member, headers[index], cell)"
                                    :title="cellTitle(member, headers[index], cell)"
                                >
                                    <X v-if="cell.state === 'missed'" :size="14" :stroke-width="2.5" />
                                    <template v-else-if="cell.state === 'off'">휴</template>
                                    <!-- 요약줄 '오늘 아직 안 냄'과 같은 말로 보인다. 예전에는 예정(·)과 구분이 안 됐다. -->
                                    <template v-else-if="cell.date === today">아직</template>
                                    <template v-else>·</template>
                                </span>
                            </td>
                            <td class="col-rate" :class="{ 'has-missed': member.missed }">
                                {{ member.submitted }}/{{ member.due }}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <p class="grid-legend">
                <span><i class="legend-mark is-done"><Check :size="12" :stroke-width="2.5" /></i>제출 · 눌러서 보기</span>
                <span><i class="legend-mark is-missed"><X :size="12" :stroke-width="2.5" /></i>미제출</span>
                <span><i class="legend-mark is-future is-text">아직</i>오늘 아직 안 냄</span>
                <span><i class="legend-mark is-future">·</i>예정</span>
                <span><i class="legend-mark is-off">휴</i>공휴일</span>
            </p>
        </section>
    </div>
</template>

<style scoped src="../styles/components/user-activities.css"></style>
