<script setup>
import { onMounted, ref } from "vue";
import useApi from "../composables/useApi";

const { GetUserActivities } = useApi();

const userActivities = ref([]);

const date = new Date();


async function fetchUserActivities() {
    const activities = await GetUserActivities(date.getFullYear(), date.getMonth() + 1);
    userActivities.value = activities;
}

onMounted(() => {
    fetchUserActivities();
});
</script>

<template>
    <div style="max-width: 800px; ">
        <h1>{{ date.getFullYear() }}년 {{ date.getMonth() + 1 }}월</h1>
        <div v-for="activity in userActivities" :key="activity.report_date" style="display: flex; flex-direction: row; justify-content: space-evenly; align-items: center">
            <h4>{{ activity.name }}</h4>
            <div v-for="item in activity.activities" :key="item.id">
                <div class="log" :class="item.count > 0 ? 'commited' : ''" ></div>
            </div>
        </div>
    </div>
</template>

<style>
.commited {
    background-color: limegreen;
    position: relative;

    &::after{
        position: absolute;
        top: -8px;
        right: 1px;
        content: '✓';
        color: white;
        font-size: 10px;
        font-weight: bold;
    }
}

.log {
    width: 10px;
    height: 10px;
    border-radius: 3px;
    border: 1.5px solid white;
}
</style>
