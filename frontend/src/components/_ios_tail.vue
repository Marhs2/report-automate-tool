<template>
    <div class="page calendar-page">
        <header class="ios-head">
            <div class="ios-title">
                <h1>{{ selectedMonth }}월</h1>
                <p>{{ selectedYear }}</p>
            </div>
            <div class="ios-tools">
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
                <div class="ios-nav">
                    <button
                        v-if="!isThisMonth"
                        type="button"
                        class="ios-today"
                        @click="goThisMonth"
                    >
                        오늘
                    </button>
                    <button type="button" class="ios-arrow" aria-label="이전 달" @click="prevMonth">
                        <ChevronLeft :size="18" />
                    </button>
                    <button type="button" class="ios-arrow" aria-label="다음 달" @click="nextMonth">
                        <ChevronRight :size="18" />
                    </button>
                </div>
            </div>
        </header>

        <div v-if="orderedActivities.length === 0" class="empty-state">
            표시할 활동 기록이 없습니다
        </div>

        <div v-else class="ios-board">
            <div class="ios-month">
                <div class="ios-weekdays">
                    <span
                        v-for="(label, index) in WEEKDAY_LABELS"
                        :key="label"
                        :class="{ sun: index === 0, sat: index === 6 }"
                    >
                        {{ label }}
                    </span>
                </div>
                <div class="ios-grid">
                    <button
                        v-for="cell in calendarCells"
                        :key="cell.date"
                        type="button"
                        class="ios-cell"
                        :aria-pressed="selectedDate === cell.date"
                        :aria-label="`${formatDotDate(cell.date)} ${dayStatusLabel(cell)}`"
                        @click="selectDay(cell)"
                    >
                        <span
                            class="ios-num"
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
                        <span class="ios-dot" :class="dotKind(cell) || 'is-empty'"></span>
                    </button>
                </div>
            </div>

            <section v-if="selectedCell" class="ios-agenda" :aria-label="agendaTitle(selectedCell)">
                <h2>{{ agendaTitle(selectedCell) }}</h2>
                <p v-if="selectedCell.holidayName" class="ios-holiday">{{ selectedCell.holidayName }}</p>
                <p class="ios-agenda-meta">
                    제출 {{ countsOf(selectedCell).submitted }}
                    <template v-if="!selectedCell.isOffday">
                        · 미제출 {{ countsOf(selectedCell).missed }}
                    </template>
                </p>

                <div
                    v-for="group in railGroups(selectedCell)"
                    :key="group.key"
                    class="agenda-group"
                >
                    <h3>{{ group.label }}</h3>
                    <template v-for="entry in group.people" :key="entry.member_id">
                        <button
                            v-if="entry.submitted"
                            type="button"
                            class="agenda-row"
                            @click="openCell({ member_id: entry.member_id, name: entry.name }, entry.item)"
                        >
                            <span class="agenda-mark full"></span>
                            <span class="agenda-name">{{ entry.name }}</span>
                        </button>
                        <div v-else class="agenda-row is-missed">
                            <span class="agenda-mark"></span>
                            <span class="agenda-name">{{ entry.name }}</span>
                        </div>
                    </template>
                </div>
                <p v-if="!railGroups(selectedCell).length" class="ios-empty">
                    이 날 제출한 보고가 없습니다
                </p>
            </section>
        </div>
    </div>
</template>

<style scoped>
.calendar-page {
    max-width: 880px;
}

.ios-head {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: var(--space-3);
}

.ios-title h1 {
    margin: 0;
    font-size: var(--fs-30);
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1;
    color: var(--text-strong);
}

.ios-title p {
    margin: var(--space-1) 0 0;
    font-size: var(--fs-14);
    color: var(--text-muted);
}

.ios-tools {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: var(--space-2);
}

.ios-nav {
    display: flex;
    align-items: center;
    gap: var(--space-1);
}

.ios-today,
.ios-arrow {
    border: 0;
    background: transparent;
    color: var(--accent);
    cursor: pointer;
}

.ios-today {
    min-height: var(--control-h-lg);
    padding: 0 var(--space-2);
    font: inherit;
    font-size: var(--fs-16);
    font-weight: 400;
}

.ios-arrow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: var(--control-h-lg);
    height: var(--control-h-lg);
    border-radius: 50%;
}

.ios-arrow:hover,
.ios-today:hover {
    background: var(--accent-soft);
}

.team-filter {
    height: var(--control-h-sm);
    max-width: 160px;
    padding: 0 calc(var(--space-6) + var(--space-1)) 0 var(--space-3);
    border: 0;
    border-radius: var(--radius-sm);
    background: var(--surface-soft);
    color: var(--text-strong);
    font: inherit;
    font-size: var(--fs-14);
}

.ios-board {
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
}

.ios-weekdays,
.ios-grid {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
}

.ios-weekdays span {
    text-align: center;
    font-size: var(--fs-13);
    font-weight: 600;
    color: var(--text-muted);
}

.ios-weekdays .sun,
.ios-num.sun,
.ios-num.holiday,
.ios-holiday {
    color: var(--danger-fg);
}

.ios-weekdays .sat,
.ios-num.sat {
    color: var(--accent);
}

.ios-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
    min-height: var(--control-h-lg);
    margin: 0;
    padding: var(--space-1) 0 var(--space-1);
    border: 0;
    background: transparent;
    cursor: pointer;
}

.ios-num {
    display: flex;
    align-items: center;
    justify-content: center;
    width: var(--control-h-sm);
    height: var(--control-h-sm);
    border-radius: 50%;
    font-size: var(--fs-16);
    font-weight: 400;
    line-height: 1;
    color: var(--text-strong);
}

.ios-num.outside {
    color: var(--text-muted);
}

.ios-num.outside.sun,
.ios-num.outside.sat,
.ios-num.outside.holiday {
    color: var(--text-muted);
}

.ios-num.today {
    background: var(--danger-fg);
    color: var(--text-on-accent);
    font-weight: 600;
}

.ios-num.selected:not(.today) {
    background: var(--border);
}

.ios-dot {
    width: var(--space-1);
    height: var(--space-1);
    border-radius: 50%;
    background: var(--accent);
}

.ios-dot.full {
    background: var(--success-fg);
}

.ios-dot.is-empty {
    background: transparent;
}

.ios-agenda {
    min-width: 0;
    padding: var(--space-1) 0 var(--space-2);
}

.ios-agenda h2 {
    margin: 0;
    font-size: var(--fs-20);
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text-strong);
}

.ios-holiday,
.ios-agenda-meta,
.ios-empty {
    margin: var(--space-1) 0 0;
    font-size: var(--fs-13);
}

.ios-agenda-meta,
.ios-empty {
    color: var(--text-muted);
}

.agenda-group {
    margin-top: var(--space-4);
}

.agenda-group h3 {
    margin: 0 0 var(--space-1);
    font-size: var(--fs-13);
    font-weight: 600;
    color: var(--text-muted);
}

.agenda-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    width: 100%;
    min-height: var(--control-h-lg);
    margin: 0;
    padding: var(--space-2) 0;
    border: 0;
    border-top: 1px solid var(--border);
    background: transparent;
    font: inherit;
    text-align: left;
    color: var(--text-strong);
}

.agenda-group .agenda-row:first-of-type {
    border-top: 0;
}

button.agenda-row {
    cursor: pointer;
}

.agenda-row.is-missed {
    color: var(--text-muted);
}

.agenda-mark {
    width: var(--space-2);
    height: var(--space-2);
    border-radius: 50%;
    background: var(--border-strong);
    flex: 0 0 auto;
}

.agenda-mark.full {
    background: var(--success-fg);
}

.agenda-name {
    font-size: var(--fs-16);
}

@media (min-width: 900px) {
    .ios-board {
        flex-direction: row;
        align-items: flex-start;
        gap: var(--control-h);
    }

    .ios-month {
        flex: 0 0 420px;
        width: 420px;
    }

    .ios-agenda {
        flex: 1;
        padding-top: calc(var(--space-6) + var(--space-1));
    }
}

@media (max-width: 860px) {
    .ios-title h1 {
        font-size: var(--fs-30);
    }

    .ios-tools {
        align-items: flex-end;
    }

    .team-filter {
        max-width: 140px;
        font-size: var(--fs-16);
    }
}
</style>
