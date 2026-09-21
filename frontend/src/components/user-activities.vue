<script setup>
import { onMounted, ref, computed } from "vue";
import { useRouter } from "vue-router";
import { ChevronLeft, ChevronRight, X } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import { dayCounts } from "../lib/dayStatus";
import { peakDayLabel, peakSubmissionDay } from "../lib/standupInsights";
import AppPageHeader from "./ui/AppPageHeader.vue";

const router = useRouter();
const { alert: showAlert } = useDialog();
const { getUserActivities, getReports, getHolidays, getTeams } = useApi();

const WEEKDAY_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

const userActivities = ref([]);
const holidayNames = ref({});

const currentDate = new Date();
const selectedYear = ref(currentDate.getFullYear());
const selectedMonth = ref(currentDate.getMonth() + 1);
const selectedDate = ref("");

const teams = ref([]);
const filterTeam = ref("all");

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
    const isPhone =
        typeof window !== "undefined" &&
        window.matchMedia("(max-width: 860px)").matches;
    if (isPhone) {
        if (!selectedDate.value) return;
        const selectedTime = parseDate(selectedDate.value).getTime();
        if (selectedTime < start.getTime() || selectedTime > end.getTime()) {
            selectedDate.value = "";
        }
        return;
    }
    if (!selectedDate.value && todayInView) {
        selectedDate.value = today;
        return;
    }
    if (!selectedDate.value) return;
    const selectedTime = parseDate(selectedDate.value).getTime();
    if (selectedTime < start.getTime() || selectedTime > end.getTime()) {
        selectedDate.value = todayInView ? today : "";
    }
}

const isThisMonth = computed(
    () =>
        selectedYear.value === currentDate.getFullYear() &&
        selectedMonth.value === currentDate.getMonth() + 1,
);

function prevMonth() {
    if (selectedMonth.value === 1) {
        selectedMonth.value = 12;
        selectedYear.value--;
    } else {
        selectedMonth.value--;
    }
    fetchUserActivities();
}

function nextMonth() {
    if (selectedMonth.value === 12) {
        selectedMonth.value = 1;
        selectedYear.value++;
    } else {
        selectedMonth.value++;
    }
    fetchUserActivities();
}

function goThisMonth() {
    selectedYear.value = currentDate.getFullYear();
    selectedMonth.value = currentDate.getMonth() + 1;
    fetchUserActivities();
}

onMounted(() => {
    fetchUserActivities();
    fetchTeams();
});

const orderedActivities = computed(() =>
    userActivities.value
        .filter(
            (activity) =>
                filterTeam.value === "all" ||
                String(activity.team_id) === String(filterTeam.value),
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
    const submitted = entries.filter((entry) => entry.submitted);
    const missed = entries.filter((entry) => !entry.submitted);
    const groups = [];
    if (missed.length) {
        groups.push({ key: "missed", label: "미제출", people: missed });
    }
    if (submitted.length) {
        groups.push({ key: "submitted", label: "제출", people: submitted });
    }
    return groups;
};

const countsOf = (cell) => dayCounts(cell.entries || [], cell.isOffday);

/** 셀에 제출률만 있으면 "누가" 안 냈는지는 오른쪽 레일을 열어야 안다.
 *  실제로 챙겨야 하는 쪽은 미제출이므로 이름을 칸 안에 적는다. */
const CELL_NAME_LIMIT = 3;

const missingNamesOf = (cell) =>
    (cell.entries || [])
        .filter((entry) => !entry.submitted)
        .map((entry) => entry.name)
        .filter(Boolean);

const submittedNamesOf = (cell) =>
    (cell.entries || [])
        .filter((entry) => entry.submitted)
        .map((entry) => entry.name)
        .filter(Boolean);

const cellNote = (cell) => {
    if (cell.isOffday) {
        const submitted = submittedNamesOf(cell);
        if (!submitted.length) return null;
        return {
            tone: "off",
            text:
                submitted.length <= CELL_NAME_LIMIT
                    ? submitted.join(" · ")
                    : `${submitted.slice(0, 2).join(" · ")} 외 ${submitted.length - 2}명`,
        };
    }
    const total = (cell.entries || []).length;
    if (!total) return null;
    const missing = missingNamesOf(cell);
    if (!missing.length) return { tone: "full", text: "전원 제출" };
    if (missing.length === total) return { tone: "missed", text: "제출 없음" };
    return {
        tone: "missed",
        text:
            missing.length <= CELL_NAME_LIMIT
                ? missing.join(" · ")
                : `${missing.slice(0, 2).join(" · ")} 외 ${missing.length - 2}명`,
    };
};

const cellNoteTitle = (cell) => {
    if (cell.isOffday) return submittedNamesOf(cell).join(" · ");
    const missing = missingNamesOf(cell);
    return missing.length ? `미제출 ${missing.join(" · ")}` : "전원 제출";
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

const toggleDay = (dateStr) => {
    selectedDate.value = selectedDate.value === dateStr ? "" : dateStr;
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

const periodLabel = computed(
    () => `${selectedYear.value}년 ${selectedMonth.value}월`,
);

const pulseLabel = computed(() => {
    const today = inRangeDays.value.find((cell) => cell.isToday);
    if (today && !today.isOffday) {
        const counts = countsOf(today);
        return `오늘 ${counts.submitted}/${counts.submitted + counts.missed} 제출`;
    }
    if (today?.isOffday) return `오늘 · ${today.holidayName || "휴일"}`;
    return `${members.value.length}명 · 평일 ${weekdayCount.value}일`;
});

const peakLabel = computed(() =>
    peakDayLabel(
        peakSubmissionDay(
            inRangeDays.value.map((cell) => ({
                date: cell.date,
                weekday: cell.weekday,
                submitted: countsOf(cell).submitted,
                isOffday: cell.isOffday,
            })),
        ),
    ),
);

const progressByMember = computed(() => {
    const map = {};
    for (const activity of orderedActivities.value) {
        map[String(activity.member_id)] = progressOf(activity);
    }
    return map;
});
</script>

<template>
    <div class="page calendar-page is-wide">
        <AppPageHeader :title="periodLabel" :subtitle="pulseLabel">
            <template #filters>
                <div class="month-nav">
                    <button class="icon-btn" aria-label="이전 달" @click="prevMonth">
                        <ChevronLeft :size="16" />
                    </button>
                    <button class="icon-btn" aria-label="다음 달" @click="nextMonth">
                        <ChevronRight :size="16" />
                    </button>
                    <button v-if="!isThisMonth" class="btn btn-small" @click="goThisMonth">
                        이번 달로
                    </button>
                </div>
                <select
                    id="activity-filter-team"
                    class="team-filter"
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
        </AppPageHeader>

        <div v-if="orderedActivities.length === 0" class="empty-state">
            표시할 활동 기록이 없습니다
        </div>
        <div v-else class="calendar-workspace" :class="{ 'has-rail': Boolean(selectedCell) }">
            <div class="card calendar-card">
                <p v-if="peakLabel" class="cal-peak">{{ peakLabel }}</p>
                <div class="cal-weekdays">
                    <span
                        v-for="label in WEEKDAY_LABELS"
                        :key="label"
                        :class="{ weekend: label === '일' || label === '토' }"
                    >
                        {{ label }}
                    </span>
                </div>
                <div class="cal-weeks">
                    <div v-for="(week, weekIndex) in calendarWeeks" :key="weekIndex" class="cal-week">
                        <template v-for="cell in week" :key="cell.date">
                            <div v-if="cell.outside" class="cal-day outside">
                                <span class="cal-day-num">{{ cell.day }}</span>
                            </div>
                            <button
                                v-else
                                type="button"
                                class="cal-day"
                                :class="{
                                    weekend: cell.isWeekend,
                                    holiday: cell.isHoliday,
                                    today: cell.isToday,
                                    selected: selectedDate === cell.date,
                                }"
                                :aria-pressed="selectedDate === cell.date"
                                :aria-label="`${formatDotDate(cell.date)} 제출 ${countsOf(cell).submitted}${cell.isOffday ? '' : `, 미제출 ${countsOf(cell).missed}`}`"
                                @click="toggleDay(cell.date)"
                            >
                                <span class="cal-day-top">
                                    <span class="cal-day-num">{{ cell.day }}</span>
                                    <span v-if="cell.holidayName" class="cal-holiday" :title="cell.holidayName">
                                        {{ cell.holidayName }}
                                    </span>
                                    <span v-else-if="cell.isWeekend" class="cal-day-tag">휴무</span>
                                    <span v-else-if="cell.isFuture" class="cal-day-tag">예정</span>
                                    <!-- 표기를 하나로 맞춘다. 만점인 날만 숫자가 빠지는 일이 없어야 한다. -->
                                    <span
                                        v-if="!cell.isOffday && ratioOf(cell).total"
                                        class="cal-day-ratio"
                                    >
                                        {{ ratioOf(cell).submitted }}/{{ ratioOf(cell).total }}
                                    </span>
                                    <span
                                        v-else-if="cell.isOffday && countsOf(cell).submitted"
                                        class="cal-day-ratio is-off"
                                    >
                                        휴일 {{ countsOf(cell).submitted }}
                                    </span>
                                </span>
                                <span
                                    v-if="!cell.isOffday && ratioOf(cell).total"
                                    class="cal-meter"
                                >
                                    <span
                                        class="cal-meter-fill"
                                        :class="{ 'is-full': ratioOf(cell).pct === 100 }"
                                        :style="{ width: ratioOf(cell).pct + '%' }"
                                    />
                                </span>
                                <span
                                    v-if="cellNote(cell)"
                                    class="cal-names"
                                    :class="cellNote(cell).tone"
                                    :title="cellNoteTitle(cell)"
                                >
                                    {{ cellNote(cell).text }}
                                </span>
                            </button>
                        </template>
                    </div>
                </div>
            </div>

            <section
                v-if="selectedCell"
                class="card day-rail"
                :aria-label="`${formatDotDate(selectedCell.date)} 제출 목록`"
            >
                <div class="day-detail-head">
                    <p class="day-detail-title">
                        <strong>{{ formatDotDate(selectedCell.date) }} ({{ selectedCell.weekLabel }})</strong>
                        <span v-if="selectedCell.holidayName">{{ selectedCell.holidayName }}</span>
                    </p>
                    <button type="button" class="icon-btn" aria-label="닫기" @click="selectedDate = ''">
                        <X :size="15" />
                    </button>
                </div>
                <p class="day-rail-pulse">
                    제출 {{ countsOf(selectedCell).submitted }}
                    <template v-if="!selectedCell.isOffday"> · 미제출 {{ countsOf(selectedCell).missed }}</template>
                </p>
                <div
                    v-for="group in railGroups(selectedCell)"
                    :key="group.key"
                    class="rail-group"
                >
                    <h3 class="rail-group-head" :class="group.key">
                        {{ group.label }}
                        <span class="rail-group-count">{{ group.people.length }}</span>
                    </h3>
                    <div class="rail-chips">
                        <button
                            v-for="entry in group.people"
                            :key="entry.member_id"
                            type="button"
                            class="rail-chip"
                            :class="group.key"
                            :title="`${entry.name} · 이번 달 ${progressByMember[String(entry.member_id)]?.submitted || 0}/${progressByMember[String(entry.member_id)]?.total || 0}`"
                            @click="openCell({ member_id: entry.member_id, name: entry.name }, entry.item)"
                        >
                            {{ entry.name }}
                            <em>{{ progressByMember[String(entry.member_id)]?.submitted || 0 }}/{{ progressByMember[String(entry.member_id)]?.total || 0 }}</em>
                        </button>
                    </div>
                </div>
                <p v-if="!railGroups(selectedCell).length" class="day-detail-empty">
                    이 날 제출한 보고가 없습니다
                </p>
            </section>
        </div>
    </div>
</template>

<style scoped>
.calendar-page {
    max-width: none;
}

.calendar-workspace,
.calendar-workspace.has-rail {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    align-items: stretch;
    width: 100%;
    min-width: 0;
}

.calendar-workspace > .calendar-card,
.calendar-workspace > .day-rail {
    min-width: 0;
    width: 100%;
    max-width: 100%;
}

@media (min-width: 1280px) {
    .calendar-workspace.has-rail {
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(320px, 380px);
        align-items: start;
    }

    .calendar-workspace.has-rail > .day-rail {
        width: auto;
    }
}

.month-nav {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    flex-shrink: 0;
}

.icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: 50%;
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
    transition:
        background var(--dur-fast) var(--ease),
        color var(--dur-fast) var(--ease);
}

.icon-btn:hover {
    background: var(--surface-soft);
    color: var(--text-strong);
}

.team-filter {
    height: 32px;
    width: auto;
    min-width: 108px;
    padding: 0 var(--space-6) 0 var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    background: var(--surface);
    color: var(--text-strong);
    font: inherit;
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    cursor: pointer;
}

.team-filter:hover {
    border-color: var(--border-strong);
}

.team-filter:focus {
    outline: none;
    border-color: var(--accent);
}

.calendar-card {
    padding: var(--space-4);
    min-width: 0;
}

.cal-peak {
    margin: 0 0 var(--space-3);
    font-size: var(--fs-12);
    font-weight: var(--fw-medium);
    color: var(--text);
    word-break: keep-all;
}

.cal-weekdays {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: var(--space-2);
    margin-bottom: var(--space-2);
}

.cal-weekdays span {
    text-align: center;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
    padding: var(--space-1) 0;
}

.cal-weekdays .weekend {
    opacity: 0.7;
}

.cal-weeks {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.cal-week {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: var(--space-2);
}

/* 이름 한 줄이 들어가므로 예전보다 조금 높다. 그래도 한 달이 한 화면에 들어온다. */
.cal-day {
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    gap: var(--space-1);
    min-height: 76px;
    width: 100%;
    padding: var(--space-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    font: inherit;
    color: inherit;
    text-align: left;
    cursor: pointer;
}

/* 주말은 중립 톤, 공휴일은 위험 톤으로 구분한다. */
.cal-day.weekend {
    background: var(--surface-soft);
}

.cal-day.holiday {
    background: var(--danger-bg);
}

.cal-day.outside {
    opacity: 0.38;
    background: transparent;
    border-color: transparent;
    cursor: default;
}

.cal-day.today {
    border-color: var(--accent);
    outline: 1px solid var(--accent);
}

.cal-day.selected {
    border-color: var(--accent);
    background: var(--accent-soft);
    outline: 1px solid var(--accent);
}

.cal-day:not(.outside):not(.selected):hover {
    border-color: var(--border-strong);
}

.cal-day-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    min-width: 0;
}

.cal-day-num {
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    line-height: 1;
}

.cal-day.weekend .cal-day-num,
.cal-day.outside .cal-day-num {
    color: var(--text-muted);
}

.cal-day.holiday .cal-day-num,
.cal-holiday {
    color: var(--danger-fg);
}

.cal-day.today .cal-day-num {
    color: var(--accent-hover);
}

.cal-holiday {
    font-size: 10px;
    font-weight: var(--fw-semibold);
    line-height: 1.2;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    word-break: keep-all;
}

.cal-day-ratio {
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
    color: var(--text);
    white-space: nowrap;
}

.cal-day-ratio.is-off {
    color: var(--danger-fg);
}

/* 주말·공휴일·미래를 같은 자리에 같은 모양으로 표시한다. */
.cal-day-tag {
    font-size: 10px;
    font-weight: var(--fw-semibold);
    color: var(--text-muted);
    white-space: nowrap;
}

/* 칸 안의 이름 줄. 미제출이 있으면 미제출 이름, 없으면 '전원 제출'. */
.cal-names {
    display: block;
    margin-top: auto;
    font-size: 10px;
    font-weight: var(--fw-medium);
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text);
}

.cal-names.missed {
    color: var(--danger-fg);
}

.cal-names.full {
    color: var(--success-fg);
}

.cal-names.off {
    color: var(--text-muted);
}

/* 제출률 막대. 이름 목록 대신 하루 상태를 한 눈금으로 보여준다. */
.cal-meter {
    display: block;
    height: 4px;
    border-radius: var(--radius-pill);
    background: var(--border);
    overflow: hidden;
}

.cal-meter-fill {
    display: block;
    height: 100%;
    border-radius: var(--radius-pill);
    background: var(--warning-fg);
}

.cal-meter-fill.is-full {
    background: var(--success-fg);
}

.day-rail {
    position: static;
    padding: var(--space-3) var(--space-4);
    min-width: 0;
    max-height: none;
    overflow: visible;
}

@media (min-width: 1280px) {
    .day-rail {
        position: sticky;
        top: calc(var(--topbar-height) + var(--space-3));
        max-height: calc(100vh - var(--topbar-height) - var(--space-6));
        overflow: auto;
    }
}

.day-rail-pulse {
    margin: 0 0 var(--space-2);
    font-size: var(--fs-12);
    color: var(--text);
}

.day-detail-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-2);
}

.day-detail-title {
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    font-size: var(--fs-13);
    color: var(--text);
    word-break: keep-all;
}

.rail-group + .rail-group {
    margin-top: var(--space-3);
}

.rail-group-head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: 0 0 var(--space-1);
    font-family: var(--sans);
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.rail-group-head.missed {
    color: var(--danger-fg);
}

.rail-group-count {
    padding: 0 6px;
    border-radius: var(--radius-pill);
    background: var(--surface-soft);
    font-size: var(--fs-11);
    color: var(--text);
}

.rail-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.rail-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 28px;
    padding: 0 10px;
    border: none;
    border-radius: var(--radius-pill);
    background: var(--success-bg);
    color: var(--success-fg);
    font: inherit;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    white-space: nowrap;
    cursor: pointer;
}

.rail-chip em {
    font-style: normal;
    font-weight: var(--fw-medium);
    opacity: 0.8;
}

.rail-chip.missed {
    background: var(--danger-bg);
    color: var(--danger-fg);
}

.rail-chip:hover,
.rail-chip:focus-visible {
    background: var(--success-border);
}

.rail-chip.missed:hover,
.rail-chip.missed:focus-visible {
    filter: brightness(0.96);
}

.day-detail-empty {
    margin: 0;
    font-size: var(--fs-12);
    color: var(--text);
}

@media (max-width: 1279px) {
    .calendar-workspace,
    .calendar-workspace.has-rail {
        display: flex;
        flex-direction: column;
    }

    .calendar-card {
        order: 1;
    }

    .day-rail {
        order: 2;
        position: static;
        top: auto;
        max-height: none;
        overflow: visible;
    }
}

@media (max-width: 860px) {
    .cal-weekdays,
    .cal-week {
        gap: 4px;
    }

    .cal-holiday,
    .cal-names,
    .cal-meter,
    .cal-day-tag {
        display: none;
    }

    .cal-day {
        min-height: 48px;
        padding: 6px 4px;
        gap: 2px;
    }

    .cal-day-top {
        flex-direction: column;
        align-items: flex-start;
        gap: 2px;
    }

    .cal-day-num {
        font-size: 14px;
        font-weight: var(--fw-semibold);
    }

    .cal-day-ratio {
        font-size: 10px;
        line-height: 1.1;
    }

    .rail-chip {
        min-height: 32px;
    }

    .page-header-filters .team-filter {
        width: 100%;
        min-width: 0;
        height: 44px;
        font-size: 16px;
    }

    .month-nav {
        width: 100%;
        justify-content: space-between;
    }
}
</style>
