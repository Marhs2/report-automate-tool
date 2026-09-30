<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ChevronLeft, ChevronRight } from "lucide-vue-next";
import useApi from "../composables/useApi";
import AppPageHeader from "./ui/AppPageHeader.vue";
import { useDialog } from "../composables/useDialog";
import { AGENDA_NAME_LIMIT, dayCounts, previewPeople } from "../lib/dayStatus";

const router = useRouter();
const { alert: showAlert } = useDialog();
const { getUserActivities, getReports, getHolidays, getTeams, getUsers } = useApi();
/** 관리자 계정 id. 보고를 안 쓰는 관리자는 미제출로 세지 않는다. */
const adminIds = ref(new Set());

const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

const userActivities = ref([]);
const holidayNames = ref({});

const currentDate = new Date();
const selectedYear = ref(currentDate.getFullYear());
const selectedMonth = ref(currentDate.getMonth() + 1);
const selectedDate = ref("");

const teams = ref([]);
const filterTeam = ref("all");
const nameQuery = ref("");
const expandedGroups = ref({});

const parseDate = (dateStr) => new Date(`${dateStr}T00:00:00`);

const formatDate = (date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
};

const startOfToday = () => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return today;
};

const fetchTeams = async () => {
    try {
        const users = await getUsers().catch(() => []);
        adminIds.value = new Set(
            (users || []).filter((user) => user.is_admin).map((user) => String(user.id)),
        );
        teams.value = await getTeams();
    } catch (error) {
        console.error("Error fetching teams:", error);
        showAlert("팀을 불러오지 못했습니다.");
    }
};


function metaFor(dateStr) {
    const date = parseDate(dateStr);
    const weekDay = date.getDay();
    const today = startOfToday();
    const holidayName = holidayNames.value[dateStr] || "";
    const isWeekend = weekDay === 0 || weekDay === 6;
    const isHoliday = Boolean(holidayName);
    return {
        date: dateStr,
        day: date.getDate(),
        weekday: weekDay,
        weekLabel: WEEKDAY_LABELS[weekDay],
        holidayName,
        isWeekend,
        isHoliday,
        isOffday: isWeekend || isHoliday,
        isToday: date.getTime() === today.getTime(),
        isFuture: date.getTime() > today.getTime(),
    };
}

const formatDotDate = (dateStr) => {
    const [year, month, day] = String(dateStr).split("-");
    if (!year || !month || !day) return dateStr;
    return `${year}.${month}.${day}`;
};

const canOpenCell = (item) => Boolean(item?.count > 0);

const openCell = async (activity, item) => {
    if (!canOpenCell(item)) return;
    let reportId = item.report_id;
    if (!reportId) {
        try {
            const reports = await getReports();
            const found = (reports || []).find(
                (report) =>
                    String(report.member_id) === String(activity.member_id) &&
                    report.report_date === item.report_date,
            );
            reportId = found?.id;
        } catch (error) {
            console.error("보고서 찾기 실패:", error);
        }
    }
    if (!reportId) return;
    // 어디서 왔는지 남긴다. 달력에서 열었으면 크럼도 "사용자 활동"이어야 한다.
    router.push({
        name: "report-result",
        params: { id: reportId },
        query: { from: "activities" },
    });
};

async function fetchHolidaysForView() {
    const map = {};
    const rows = await getHolidays(selectedYear.value);
    for (const row of rows || []) {
        if (row?.date) map[row.date] = row.name;
    }
    holidayNames.value = map;
}

async function fetchUserActivities() {
    await fetchHolidaysForView();
    userActivities.value = await getUserActivities(
        selectedYear.value,
        selectedMonth.value,
    );
    selectDefaultDay();
}

function selectDefaultDay() {
    const today = formatDate(startOfToday());
    const { start, end } = rangeBounds.value;
    const todayTime = parseDate(today).getTime();
    const todayInView =
        todayTime >= start.getTime() && todayTime <= end.getTime();
    const fallback = todayInView ? today : formatDate(start);
    if (!selectedDate.value) {
        selectedDate.value = fallback;
        return;
    }
    const selectedTime = parseDate(selectedDate.value).getTime();
    if (selectedTime < start.getTime() || selectedTime > end.getTime()) {
        selectedDate.value = fallback;
    }
}

const isThisMonth = computed(
    () =>
        selectedYear.value === currentDate.getFullYear() &&
        selectedMonth.value === currentDate.getMonth() + 1,
);

function prevMonth() {
    closeAgenda();
    if (selectedMonth.value === 1) {
        selectedMonth.value = 12;
        selectedYear.value--;
    } else {
        selectedMonth.value--;
    }
    fetchUserActivities();
}

function nextMonth() {
    closeAgenda();
    if (selectedMonth.value === 12) {
        selectedMonth.value = 1;
        selectedYear.value++;
    } else {
        selectedMonth.value++;
    }
    fetchUserActivities();
}

function goThisMonth() {
    closeAgenda();
    selectedYear.value = currentDate.getFullYear();
    selectedMonth.value = currentDate.getMonth() + 1;
    fetchUserActivities();
}

const isNarrow = ref(
    typeof window !== "undefined" && window.matchMedia("(max-width: 860px)").matches,
);
const agendaOpen = ref(false);
let narrowQuery = null;

const syncNarrow = () => {
    isNarrow.value = Boolean(narrowQuery?.matches);
    if (!isNarrow.value) closeAgenda();
};

const openAgenda = () => {
    agendaOpen.value = true;
    document.documentElement.classList.add("is-overlay-open");
};

const closeAgenda = () => {
    agendaOpen.value = false;
    document.documentElement.classList.remove("is-overlay-open");
};

const onAgendaKey = (event) => {
    if (event.key === "Escape") closeAgenda();
};

watch(agendaOpen, (open) => {
    if (open) window.addEventListener("keydown", onAgendaKey);
    else window.removeEventListener("keydown", onAgendaKey);
});

onMounted(() => {
    narrowQuery = window.matchMedia("(max-width: 860px)");
    syncNarrow();
    narrowQuery.addEventListener("change", syncNarrow);
    fetchUserActivities();
    fetchTeams();
});

onUnmounted(() => {
    narrowQuery?.removeEventListener("change", syncNarrow);
    window.removeEventListener("keydown", onAgendaKey);
    document.documentElement.classList.remove("is-overlay-open");
});

const orderedActivities = computed(() =>
    userActivities.value
        .filter(
            (activity) =>
                filterTeam.value === "all" ||
                String(activity.team_id) === String(filterTeam.value),
        )
        .filter(
            (activity) =>
                !adminIds.value.has(String(activity.member_id)) ||
                Number(activity.total_count) > 0,
        )
        .map((activity) => ({
            ...activity,
            activities: [...(activity.activities || [])].sort((left, right) =>
                left.report_date.localeCompare(right.report_date),
            ),
        })),
);

const activityLookup = computed(() => {
    const byMember = new Map();
    for (const activity of orderedActivities.value) {
        const byDate = new Map();
        for (const item of activity.activities || []) {
            byDate.set(item.report_date, item);
        }
        byMember.set(String(activity.member_id), byDate);
    }
    return byMember;
});

const members = computed(() =>
    orderedActivities.value.map((activity) => ({
        member_id: activity.member_id,
        name: activity.name,
    })),
);

const entriesForDate = (dateStr) =>
    members.value.map((member) => {
        const item =
            activityLookup.value
                .get(String(member.member_id))
                ?.get(dateStr) || { report_date: dateStr, count: 0 };
        return {
            ...member,
            item,
            submitted: Boolean(item.count > 0),
        };
    });

const visibleEntries = (cell) =>
    cell.isOffday
        ? cell.entries.filter((entry) => entry.submitted)
        : cell.entries;

/** 인원이 많으면 한 줄로 나열하기 어렵다. 먼저 챙겨야 하는 미제출을 위로 올린다. */
const railGroups = (cell) => {
    const entries = visibleEntries(cell);
    const byName = (left, right) =>
        String(left.name || "").localeCompare(String(right.name || ""), "ko");
    const submitted = entries
        .filter((entry) => entry.submitted)
        .sort(byName);
    const missed = entries.filter((entry) => !entry.submitted).sort(byName);
    const groups = [];
    if (missed.length) {
        groups.push({ key: "missed", label: "미제출", people: missed });
    }
    if (submitted.length) {
        groups.push({ key: "submitted", label: "제출", people: submitted });
    }
    return groups;
};

const rosterCount = (cell) => (cell ? visibleEntries(cell).length : 0);

const expandKey = (cell, groupKey) => `${cell?.date || ""}:${groupKey}`;

const expandGroup = (key) => {
    const current = Number(expandedGroups.value[key]) || AGENDA_NAME_LIMIT;
    expandedGroups.value = {
        ...expandedGroups.value,
        [key]: current + AGENDA_NAME_LIMIT,
    };
};

/** 인원이 많으면 다섯 명씩 열고, 이름은 검색으로 찾는다. */
const agendaGroups = (cell) =>
    railGroups(cell)
        .map((group) => {
            const key = expandKey(cell, group.key);
            const preview = previewPeople(group.people, {
                query: nameQuery.value,
                visible: expandedGroups.value[key] || AGENDA_NAME_LIMIT,
                limit: AGENDA_NAME_LIMIT,
            });
            return {
                ...group,
                expandKey: key,
                people: preview.matched,
                shown: preview.shown,
                hidden: preview.hidden,
                next: preview.next,
            };
        })
        .filter((group) => group.people.length);

watch(selectedDate, () => {
    nameQuery.value = "";
    expandedGroups.value = {};
});

const showNameSearch = (cell) => rosterCount(cell) > 8;

const personTitle = (entry) => {
    const progress = progressByMember.value[String(entry.member_id)];
    if (!progress?.total) return entry.name;
    return `${entry.name} · 이번 달 ${progress.submitted}/${progress.total}`;
};

const countsOf = (cell) => dayCounts(cell.entries || [], cell.isOffday);

/** 칸에는 숫자만 둔다. 이름은 날짜를 열었을 때 목록으로 본다. */
const dayStatusLabel = (cell) => {
    const { submitted, total } = ratioOf(cell);
    if (cell.isOffday) {
        if (cell.holidayName && submitted) return `${cell.holidayName} ${submitted}`;
        if (cell.holidayName) return cell.holidayName;
        if (submitted) return `휴일 ${submitted}`;
        return "휴일";
    }
    if (cell.isFuture) return "예정";
    if (!total) return "";
    if (submitted === 0) return "제출 없음";
    if (submitted === total) return "전원 제출";
    return `${submitted}/${total}`;
};

/** 셀에 이름을 나열하는 대신 제출률만 막대로 보여준다. */
const ratioOf = (cell) => {
    const { submitted, missed } = countsOf(cell);
    const total = submitted + missed;
    return {
        submitted,
        total,
        pct: total ? Math.round((submitted / total) * 100) : 0,
    };
};

const dotKind = (cell) => {
    if (cell.outside) return "";
    const { submitted, total } = ratioOf(cell);
    if (!submitted) return "";
    if (!cell.isOffday && !cell.isFuture && total && submitted === total) return "full";
    return "partial";
};

const selectDay = (cell) => {
    if (cell.outside) {
        const date = parseDate(cell.date);
        selectedYear.value = date.getFullYear();
        selectedMonth.value = date.getMonth() + 1;
        selectedDate.value = cell.date;
        fetchUserActivities();
    } else {
        selectedDate.value = cell.date;
    }
    if (isNarrow.value) openAgenda();
};

const agendaTitle = (cell) => {
    const [, month, day] = String(cell.date).split("-");
    const longWeek = ["일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일"];
    return `${Number(month)}월 ${Number(day)}일 ${longWeek[cell.weekday] || ""}`;
};

const rangeBounds = computed(() => {
    return {
        start: new Date(selectedYear.value, selectedMonth.value - 1, 1),
        end: new Date(selectedYear.value, selectedMonth.value, 0),
    };
});

const calendarWeeks = computed(() => {
    const { start, end } = rangeBounds.value;
    const gridStart = new Date(start);
    gridStart.setDate(gridStart.getDate() - gridStart.getDay());
    const gridEnd = new Date(end);
    gridEnd.setDate(gridEnd.getDate() + (6 - gridEnd.getDay()));

    const weeks = [];
    const cursor = new Date(gridStart);
    while (cursor.getTime() <= gridEnd.getTime()) {
        const week = [];
        for (let i = 0; i < 7; i++) {
            const dateStr = formatDate(cursor);
            const inRange =
                cursor.getTime() >= start.getTime() &&
                cursor.getTime() <= end.getTime();
            week.push({
                ...metaFor(dateStr),
                outside: !inRange,
                entries: inRange ? entriesForDate(dateStr) : [],
            });
            cursor.setDate(cursor.getDate() + 1);
        }
        weeks.push(week);
    }
    return weeks;
});

const inRangeDays = computed(() =>
    calendarWeeks.value.flat().filter((cell) => !cell.outside),
);

const selectedCell = computed(
    () =>
        inRangeDays.value.find((cell) => cell.date === selectedDate.value) ||
        null,
);

const weekdayCount = computed(
    () => inRangeDays.value.filter((cell) => !cell.isOffday).length,
);

const progressOf = (activity) => {
    const submitted = (activity.activities || []).filter(
        (item) => item.count > 0,
    ).length;
    const total = weekdayCount.value || (activity.activities || []).length;
    return {
        submitted,
        total,
        pct: total ? Math.round((submitted / total) * 100) : 0,
    };
};

const calendarCells = computed(() => calendarWeeks.value.flat());

const progressByMember = computed(() => {
    const map = {};
    for (const activity of orderedActivities.value) {
        map[String(activity.member_id)] = progressOf(activity);
    }
    return map;
});
</script>

<template>
    <div class="page">
        <AppPageHeader :title="`${selectedYear}년 ${selectedMonth}월`">
            <template #filters>
                <select
                    id="activity-filter-team"
                    class="input team-filter"
                    v-model="filterTeam"
                    aria-label="팀"
                    autocomplete="off"
                >
                    <option value="all">전체 팀</option>
                    <option v-for="team in teams" :key="team.id" :value="String(team.id)">
                        {{ team.team_name }}
                    </option>
                </select>
            </template>
            <template #actions>
                <button
                    v-if="!isThisMonth"
                    type="button"
                    class="btn btn-small"
                    @click="goThisMonth"
                >
                    이번 달
                </button>
                <div class="month-nav">
                    <button type="button" class="icon-btn" aria-label="이전 달" @click="prevMonth">
                        <ChevronLeft :size="16" />
                    </button>
                    <button type="button" class="icon-btn" aria-label="다음 달" @click="nextMonth">
                        <ChevronRight :size="16" />
                    </button>
                </div>
            </template>
        </AppPageHeader>

        <div v-if="orderedActivities.length === 0" class="empty-state">
            표시할 활동 기록이 없습니다
        </div>

        <div v-else class="activity-board">
            <section class="card month-card" aria-label="달력">
                <div class="weekdays">
                    <span
                        v-for="(label, index) in WEEKDAY_LABELS"
                        :key="label"
                        :class="{ sun: index === 0, sat: index === 6 }"
                    >
                        {{ label }}
                    </span>
                </div>
                <div class="month-grid">
                    <button
                        v-for="cell in calendarCells"
                        :key="cell.date"
                        type="button"
                        class="day-cell"
                        :aria-pressed="selectedDate === cell.date"
                        :aria-label="`${formatDotDate(cell.date)} ${dayStatusLabel(cell)}`"
                        @click="selectDay(cell)"
                    >
                        <span
                            class="day-num"
                            :class="{
                                sun: cell.weekday === 0,
                                sat: cell.weekday === 6,
                                holiday: cell.isHoliday,
                                outside: cell.outside,
                                today: cell.isToday && !cell.outside,
                                selected: selectedDate === cell.date,
                            }"
                        >
                            {{ cell.day }}
                        </span>
                        <span class="day-dot" :class="dotKind(cell) || 'is-empty'"></span>
                    </button>
                </div>
                <p class="dot-legend">
                    <span><i class="day-dot full" aria-hidden="true"></i>전원 제출</span>
                    <span><i class="day-dot partial" aria-hidden="true"></i>일부 제출</span>
                    <span>날짜를 누르면 누가 냈는지 보여요</span>
                </p>
            </section>

            <section v-if="selectedCell && !isNarrow" class="card agenda" :aria-label="agendaTitle(selectedCell)">
                <div class="section-head">
                    <h2>{{ agendaTitle(selectedCell) }}</h2>
                </div>
                <p v-if="selectedCell.holidayName" class="agenda-holiday">{{ selectedCell.holidayName }}</p>
                <p class="agenda-meta">
                    제출 {{ countsOf(selectedCell).submitted }}
                    <template v-if="!selectedCell.isOffday">
                        · 미제출 {{ countsOf(selectedCell).missed }}
                    </template>
                </p>
                <div
                    v-if="!selectedCell.isOffday && (countsOf(selectedCell).submitted + countsOf(selectedCell).missed)"
                    class="agenda-bar"
                    role="img"
                    :aria-label="`제출 ${countsOf(selectedCell).submitted}명, 미제출 ${countsOf(selectedCell).missed}명`"
                >
                    <span class="is-saved" :style="{ flexGrow: countsOf(selectedCell).submitted }"></span>
                    <span class="is-missing" :style="{ flexGrow: countsOf(selectedCell).missed }"></span>
                </div>

                <label v-if="showNameSearch(selectedCell)" class="agenda-search">
                    <input
                        v-model="nameQuery"
                        class="input"
                        type="search"
                        placeholder="이름 검색"
                        aria-label="이름 검색"
                        autocomplete="off"
                    />
                </label>

                <div
                    v-for="group in agendaGroups(selectedCell)"
                    :key="group.expandKey"
                    class="agenda-group"
                >
                    <h3>
                        <span class="state-chip" :class="group.key === 'missed' ? 'is-danger' : 'is-success'">
                            {{ group.label }} {{ group.people.length }}
                        </span>
                    </h3>
                    <div class="agenda-chips">
                        <button
                            v-for="entry in group.shown.filter((person) => person.submitted)"
                            :key="entry.member_id"
                            type="button"
                            class="person-chip"
                            :title="personTitle(entry)"
                            @click="openCell({ member_id: entry.member_id, name: entry.name }, entry.item)"
                        >
                            {{ entry.name }}
                        </button>
                        <span
                            v-for="entry in group.shown.filter((person) => !person.submitted)"
                            :key="entry.member_id"
                            class="person-chip is-missed"
                            :title="personTitle(entry)"
                        >
                            {{ entry.name }}
                        </span>
                    </div>
                    <button
                        v-if="group.hidden"
                        type="button"
                        class="more-people"
                        @click="expandGroup(group.expandKey)"
                    >
                        {{ group.next }}명 더 보기
                    </button>
                </div>
                <p v-if="!railGroups(selectedCell).length" class="agenda-empty">
                    이 날 제출한 보고가 없습니다
                </p>
                <p
                    v-else-if="nameQuery.trim() && !agendaGroups(selectedCell).length"
                    class="agenda-empty"
                >
                    해당하는 사람이 없습니다
                </p>
            </section>
        <Teleport to="body">
            <div
                v-if="isNarrow && agendaOpen && selectedCell"
                class="app-dialog-overlay"
                @click.self="closeAgenda"
            >
                <div
                    class="card app-dialog agenda agenda-sheet"
                    role="dialog"
                    aria-modal="true"
                    :aria-label="agendaTitle(selectedCell)"
                >
                    <div class="section-head">
                        <h2>{{ agendaTitle(selectedCell) }}</h2>
                    </div>
                    <p v-if="selectedCell.holidayName" class="agenda-holiday">{{ selectedCell.holidayName }}</p>
                    <p class="agenda-meta">
                        제출 {{ countsOf(selectedCell).submitted }}
                        <template v-if="!selectedCell.isOffday">
                            · 미제출 {{ countsOf(selectedCell).missed }}
                        </template>
                    </p>
                    <div
                        v-if="!selectedCell.isOffday && (countsOf(selectedCell).submitted + countsOf(selectedCell).missed)"
                        class="agenda-bar"
                        role="img"
                        :aria-label="`제출 ${countsOf(selectedCell).submitted}명, 미제출 ${countsOf(selectedCell).missed}명`"
                    >
                        <span class="is-saved" :style="{ flexGrow: countsOf(selectedCell).submitted }"></span>
                        <span class="is-missing" :style="{ flexGrow: countsOf(selectedCell).missed }"></span>
                    </div>
                    <label v-if="showNameSearch(selectedCell)" class="agenda-search">
                        <input
                            v-model="nameQuery"
                            class="input"
                            type="search"
                            placeholder="이름 검색"
                            aria-label="이름 검색"
                            autocomplete="off"
                        />
                    </label>
                    <div
                        v-for="group in agendaGroups(selectedCell)"
                        :key="`sheet-${group.expandKey}`"
                        class="agenda-group"
                    >
                        <h3>
                        <span class="state-chip" :class="group.key === 'missed' ? 'is-danger' : 'is-success'">
                            {{ group.label }} {{ group.people.length }}
                        </span>
                    </h3>
                        <div class="agenda-chips">
                            <button
                                v-for="entry in group.shown.filter((person) => person.submitted)"
                                :key="entry.member_id"
                                type="button"
                                class="person-chip"
                                :title="personTitle(entry)"
                                @click="openCell({ member_id: entry.member_id, name: entry.name }, entry.item)"
                            >
                                {{ entry.name }}
                            </button>
                            <span
                                v-for="entry in group.shown.filter((person) => !person.submitted)"
                                :key="entry.member_id"
                                class="person-chip is-missed"
                                :title="personTitle(entry)"
                            >
                                {{ entry.name }}
                            </span>
                        </div>
                        <button
                            v-if="group.hidden"
                            type="button"
                            class="more-people"
                            @click="expandGroup(group.expandKey)"
                        >
                            {{ group.next }}명 더 보기
                        </button>
                    </div>
                    <p v-if="!railGroups(selectedCell).length" class="agenda-empty">
                        이 날 제출한 보고가 없습니다
                    </p>
                    <p
                        v-else-if="nameQuery.trim() && !agendaGroups(selectedCell).length"
                        class="agenda-empty"
                    >
                        해당하는 사람이 없습니다
                    </p>
                    <div class="app-dialog-actions">
                        <button class="btn" type="button" @click="closeAgenda">닫기</button>
                    </div>
                </div>
            </div>
        </Teleport>

        </div>
    </div>
</template>

<style scoped>
.month-nav {
    display: flex;
    align-items: center;
    gap: var(--space-1);
}

.icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: var(--control-h-sm);
    height: var(--control-h-sm);
    padding: 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
    transition:
        background var(--dur-fast) var(--ease),
        border-color var(--dur-fast) var(--ease),
        color var(--dur-fast) var(--ease);
}

.icon-btn:hover {
    background: var(--surface-soft);
    border-color: var(--border-strong);
    color: var(--text-strong);
}

.icon-btn:focus-visible {
    outline: none;
    border-color: var(--accent);
    box-shadow: var(--focus-ring);
}

.team-filter {
    width: 180px;
    height: var(--control-h);
}

.activity-board {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
}

.weekdays,
.month-grid {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
}

.weekdays span {
    text-align: center;
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-muted);
}

.weekdays .sun,
.day-num.sun,
.day-num.holiday,
.agenda-holiday {
    color: var(--danger-fg);
}

.weekdays .sat,
.day-num.sat {
    color: var(--info-fg);
}

.day-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
    min-height: var(--control-h-lg);
    margin: 0;
    padding: var(--space-1) 0;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    cursor: pointer;
}

.day-cell:hover {
    background: var(--surface-soft);
}

.day-num {
    display: flex;
    align-items: center;
    justify-content: center;
    width: var(--control-h-sm);
    height: var(--control-h-sm);
    border-radius: 50%;
    font-size: var(--fs-14);
    font-weight: var(--fw-medium);
    line-height: 1;
    color: var(--text-strong);
}

.day-num.outside,
.day-num.outside.sun,
.day-num.outside.sat,
.day-num.outside.holiday {
    color: var(--text-muted);
}

.day-num.today {
    box-shadow: inset 0 0 0 1px var(--accent);
    color: var(--accent);
    font-weight: var(--fw-semibold);
}

.day-num.selected {
    background: var(--accent);
    box-shadow: none;
    color: var(--text-on-accent);
    font-weight: var(--fw-semibold);
}

.day-dot {
    width: var(--space-1);
    height: var(--space-1);
    border-radius: 50%;
    background: var(--accent);
}

.day-dot.full {
    background: var(--success-fg);
}

.day-dot.partial {
    background: var(--warning-fg);
}

.day-dot.is-empty {
    background: transparent;
}

.section-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-2);
}

.section-head h2 {
    margin: 0;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.agenda-holiday,
.agenda-meta,
.agenda-empty {
    margin: 0;
    font-size: var(--fs-13);
}

.agenda-meta,
.agenda-empty {
    color: var(--text-muted);
}

.agenda-group {
    margin-top: var(--space-4);
}

.agenda-group h3 {
    margin: 0 0 var(--space-2);
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-muted);
}

.agenda-search {
    display: block;
    margin-top: var(--space-3);
}

.agenda-search .input {
    width: 100%;
    height: var(--control-h);
}

.agenda-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
}

.person-chip {
    display: inline-flex;
    align-items: center;
    max-width: 100%;
    min-height: var(--control-h-sm);
    margin: 0;
    padding: var(--space-1) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    font: inherit;
    font-size: var(--fs-13);
    line-height: 1.2;
    color: var(--text-strong);
}

button.person-chip {
    cursor: pointer;
}

button.person-chip:hover {
    border-color: var(--accent);
    color: var(--accent);
}

/* 미제출은 면을 칠하지 않고 테두리와 글자색으로만 구분한다. */
.person-chip.is-missed {
    border-color: var(--danger-border);
    background: transparent;
    color: var(--danger-fg);
}

.agenda-bar {
    display: flex;
    gap: 2px;
    height: 6px;
    margin-top: var(--space-3);
    overflow: hidden;
    border-radius: var(--radius-xs);
    background: var(--surface-soft);
}

.agenda-bar .is-saved {
    background: var(--success-fg);
}

.agenda-bar .is-missing {
    background: var(--danger-border);
}

.dot-legend {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-4);
    margin: var(--space-3) 0 0;
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
    font-size: var(--fs-12);
    color: var(--text-muted);
}

.dot-legend span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.dot-legend span:last-child {
    margin-left: auto;
}

.dot-legend .day-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
}

.more-people {
    margin-top: var(--space-2);
    padding: var(--space-1) 0;
    border: 0;
    background: transparent;
    font: inherit;
    font-size: var(--fs-13);
    color: var(--accent);
    cursor: pointer;
}

@media (min-width: 900px) {
    .activity-board {
        flex-direction: row;
        align-items: flex-start;
    }

    .month-card {
        flex: 0 0 420px;
        width: 420px;
    }

    .agenda {
        position: sticky;
        top: var(--space-4);
        flex: 1;
        min-width: 0;
        max-height: calc(100vh - var(--topbar-height) - calc(var(--space-8) * 2));
        overflow: auto;
    }
}

.agenda-sheet {
    display: flex;
    flex-direction: column;
    max-height: min(78vh, 640px);
    overflow: auto;
}

.agenda-sheet .app-dialog-actions {
    position: sticky;
    bottom: 0;
    margin-top: var(--space-4);
    padding-top: var(--space-3);
    background: var(--surface);
}

@media (max-width: 860px) {
    /* 달 이동은 제목 줄에, 팀 고르기는 그 아래 한 줄로. */
    .page-header {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
    }

    .page-header :deep(.page-header-filters) {
        grid-column: 1 / -1;
        grid-row: 2;
    }

    .dot-legend span:last-child {
        margin-left: 0;
    }

    .team-filter {
        width: 100%;
        min-width: 0;
        max-width: none;
        height: var(--control-h-lg);
        font-size: var(--fs-16);
    }

    .month-nav .icon-btn {
        width: var(--control-h-lg);
        height: var(--control-h-lg);
    }

    .agenda-search .input,
    .person-chip,
    .more-people {
        min-height: var(--control-h-lg);
    }

    .agenda-search .input {
        height: var(--control-h-lg);
    }
}
</style>
