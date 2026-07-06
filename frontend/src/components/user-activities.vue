<script setup>
import { onMounted } from "vue";
import { GetUserActivities } from "../composables/useApi";

const userActivities = ref([]);

async function fetchUserActivities() {
    const activities = await GetUserActivities();
    userActivities.value = activities;
}

onMounted(() => {
    fetchUserActivities();
});
</script>

<template>
    <div>
        <ul>
            <li v-for="activity in userActivities" :key="activity.id">
                {{ activity.name }}
            </li>
        </ul>
    </div>
</template>
