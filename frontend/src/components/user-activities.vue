<script setup>
import { onMounted ,ref } from "vue";
import useApi from "../composables/useApi";

const { GetUserActivities } = useApi();

const userActivities = ref([]);

async function fetchUserActivities() {
    const activities = await GetUserActivities(2026, 7);
    userActivities.value = activities;
}

onMounted(() => {
    fetchUserActivities();
});
</script>

<template>
    <div>
        <div v-for="activity in userActivities" :key="activity.report_date">
            <h3>{{ activity.report_date }}</h3>
            <ul>
                <li v-for="member in activity.members" :key="member.member_id">
                    {{ member.name }} - {{ member.count > 0 ? `제출 ${member.count}회` : '미제출' }}
                </li>
            </ul>
        </div>
    </div>
</template>
