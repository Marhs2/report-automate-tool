<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { ADMIN_TABS } from "../lib/nav";
import AppPageHeader from "./ui/AppPageHeader.vue";
import AppTabs from "./ui/AppTabs.vue";
import UserSelect from "./user-select.vue";
import AdminTeams from "./admin-teams.vue";

const route = useRoute();
const tab = computed(() => {
    const value = String(route.params.tab || "users");
    return ADMIN_TABS.some((item) => item.id === value) ? value : "users";
});
</script>

<template>
    <div class="page">
        <AppPageHeader subtitle="사용자 · 부서" />
        <AppTabs :tabs="ADMIN_TABS" :active="tab" />
        <UserSelect v-if="tab === 'users'" embedded />
        <AdminTeams v-else embedded />
    </div>
</template>
