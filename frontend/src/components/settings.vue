<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { SETTINGS_TABS } from "../lib/nav";
import AppPageHeader from "./ui/AppPageHeader.vue";
import AppTabs from "./ui/AppTabs.vue";
import UserSelect from "./user-select.vue";
import TeamSelect from "./team-select.vue";
import ProjectName from "./project-name.vue";

const route = useRoute();
const tab = computed(() => {
    const value = String(route.params.tab || "users");
    return SETTINGS_TABS.some((item) => item.id === value) ? value : "users";
});
</script>

<template>
    <div class="page">
        <AppPageHeader subtitle="사용자 · 부서 · 프로젝트명" />
        <AppTabs :tabs="SETTINGS_TABS" :active="tab" />
        <UserSelect v-if="tab === 'users'" embedded />
        <TeamSelect v-else-if="tab === 'teams'" embedded />
        <ProjectName v-else embedded />
    </div>
</template>
