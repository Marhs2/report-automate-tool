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
    gap: 12px;
}

.ios-title h1 {
    margin: 0;
    font-size: 34px;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1;
    color: #1c1c1e;
}

.ios-title p {
    margin: 4px 0 0;
    font-size: 15px;
    color: rgba(60, 60, 67, 0.6);
}

.ios-tools {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
}

.ios-nav {
    display: flex;
    align-items: center;
    gap: 4px;
}

.ios-today,
.ios-arrow {
    border: 0;
    background: transparent;
    color: #007aff;
    cursor: pointer;
}

.ios-today {
    min-height: 44px;
    padding: 0 8px;
    font: inherit;
    font-size: 17px;
    font-weight: 400;
}

.ios-arrow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: 50%;
}

.ios-arrow:hover,
.ios-today:hover {
    background: rgba(0, 122, 255, 0.08);
}

.team-filter {
    height: 32px;
    max-width: 160px;
    padding: 0 28px 0 10px;
    border: 0;
    border-radius: 8px;
    background: rgba(120, 120, 128, 0.12);
    color: #1c1c1e;
    font: inherit;
    font-size: 15px;
}

.ios-board {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.ios-weekdays,
.ios-grid {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
}

.ios-weekdays span {
    text-align: center;
    font-size: 13px;
    font-weight: 600;
    color: rgba(60, 60, 67, 0.6);
}

.ios-weekdays .sun,
.ios-num.sun,
.ios-num.holiday,
.ios-holiday {
    color: #ff3b30;
}

.ios-weekdays .sat,
.ios-num.sat {
    color: #007aff;
}

.ios-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    min-height: 48px;
    margin: 0;
    padding: 2px 0 4px;
    border: 0;
    background: transparent;
    cursor: pointer;
}

.ios-num {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    font-size: 17px;
    font-weight: 400;
    line-height: 1;
    color: #1c1c1e;
}

.ios-num.outside {
    color: rgba(60, 60, 67, 0.3);
}

.ios-num.outside.sun,
.ios-num.outside.sat,
.ios-num.outside.holiday {
    color: rgba(60, 60, 67, 0.3);
}

.ios-num.today {
    background: #ff3b30;
    color: #fff;
    font-weight: 600;
}

.ios-num.selected:not(.today) {
    background: #e5e5ea;
}

.ios-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #007aff;
}

.ios-dot.full {
    background: #34c759;
}

.ios-dot.is-empty {
    background: transparent;
}

.ios-agenda {
    min-width: 0;
    padding: 4px 0 8px;
}

.ios-agenda h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #1c1c1e;
}

.ios-holiday,
.ios-agenda-meta,
.ios-empty {
    margin: 4px 0 0;
    font-size: 13px;
}

.ios-agenda-meta,
.ios-empty {
    color: rgba(60, 60, 67, 0.6);
}

.agenda-group {
    margin-top: 16px;
}

.agenda-group h3 {
    margin: 0 0 4px;
    font-size: 13px;
    font-weight: 600;
    color: rgba(60, 60, 67, 0.6);
}

.agenda-row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    min-height: 44px;
    margin: 0;
    padding: 8px 0;
    border: 0;
    border-top: 1px solid rgba(60, 60, 67, 0.12);
    background: transparent;
    font: inherit;
    text-align: left;
    color: #1c1c1e;
}

.agenda-group .agenda-row:first-of-type {
    border-top: 0;
}

button.agenda-row {
    cursor: pointer;
}

.agenda-row.is-missed {
    color: rgba(60, 60, 67, 0.45);
}

.agenda-mark {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgba(60, 60, 67, 0.28);
    flex: 0 0 auto;
}

.agenda-mark.full {
    background: #34c759;
}

.agenda-name {
    font-size: 17px;
}

@media (min-width: 900px) {
    .ios-board {
        flex-direction: row;
        align-items: flex-start;
        gap: 36px;
    }

    .ios-month {
        flex: 0 0 420px;
        width: 420px;
    }

    .ios-agenda {
        flex: 1;
        padding-top: 28px;
    }
}

@media (max-width: 860px) {
    .ios-title h1 {
        font-size: 32px;
    }

    .ios-tools {
        align-items: flex-end;
    }

    .team-filter {
        max-width: 140px;
        font-size: 16px;
    }
}
</style>
