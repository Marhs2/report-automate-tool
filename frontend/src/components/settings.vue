<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { SETTINGS_TABS } from "../lib/nav";
import AppPageHeader from "./ui/AppPageHeader.vue";
import AppTabs from "./ui/AppTabs.vue";
import TeamSelect from "./team-select.vue";
import ProjectName from "./project-name.vue";

const route = useRoute();
const tab = computed(() => {
    const value = String(route.params.tab || "teams");
    return SETTINGS_TABS.some((item) => item.id === value) ? value : "teams";
});
</script>

<template>
    <div class="page">
        <AppPageHeader subtitle="내 부서 · 프로젝트명" />
        <AppTabs :tabs="SETTINGS_TABS" :active="tab" />
        <TeamSelect v-if="tab === 'teams'" embedded />
        <ProjectName v-else embedded />
    </div>
</template>
