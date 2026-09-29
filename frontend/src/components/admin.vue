<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import { ADMIN_TABS } from "../lib/nav";
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
        <p class="section-note">사용자의 부서를 바꾸고, 비밀번호가 없는 계정에 임시 비밀번호를 넣어요. 부서를 새로 만들 수도 있어요.</p>
        <AppTabs :tabs="ADMIN_TABS" :active="tab" />
        <UserSelect v-if="tab === 'users'" embedded />
        <AdminTeams v-else embedded />
    </div>
</template>
