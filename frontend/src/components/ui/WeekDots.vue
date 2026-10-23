<script setup>
import { computed } from "vue";

/** 월~금 제출 점. days: [{ label: "월", state: "done" | "missing" | "today" | "today-done" | "future" | "holiday" }] */
const props = defineProps({
    days: { type: Array, required: true },
});

const STATE_WORDS = {
    done: "제출",
    "today-done": "오늘 제출",
    missing: "미제출",
    today: "오늘 아직",
    future: "예정",
    holiday: "휴일",
};

const summary = computed(() =>
    props.days.map((day) => `${day.label} ${STATE_WORDS[day.state] || ""}`.trim()).join(", "),
);
</script>

<template>
    <span class="week-dots" role="img" :aria-label="summary">
        <span
            v-for="(day, index) in days"
            :key="index"
            class="week-dot"
            :class="`is-${day.state}`"
            :title="`${day.label} ${STATE_WORDS[day.state] || ''}`"
        >
            <template v-if="day.state === 'holiday'">휴</template>
        </span>
    </span>
</template>

<style scoped src="../../styles/components/ui/WeekDots.css"></style>
