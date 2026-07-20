<script setup>
import { ref } from "vue";
const ifJoin = ref(false);

window.addEventListener("DOMContentLoaded", () => {
  ifJoin.value = true;
});

</script>
<template>
    <header>
        <router-link to="/">project List</router-link> |
        <router-link to="/report">report</router-link> |
        <router-link to="/activities">activities</router-link> |
        <router-link to="/weekly">weekly report download</router-link>
    </header>

    <RouterView> </RouterView>
</template>
