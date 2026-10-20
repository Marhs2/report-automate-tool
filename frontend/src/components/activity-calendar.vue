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

<style scoped src="../styles/components/activity-calendar.css"></style>
