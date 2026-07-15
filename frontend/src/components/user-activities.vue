<script setup>
import { onMounted, ref } from "vue";
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
    <div style="max-width: 800px; ">
        <div v-for="activity in userActivities" :key="activity.report_date" style="display: flex; flex-direction: row; justify-content: space-evenly; align-items: center">
            <h4>{{ activity.name }}</h4>
            <div v-for="item in activity.activities" :key="item.id">
                <input type="checkbox" :checked="item.count > 0" readonly />
            </div>
        </div>
    </div>
</template>

<style></style>
