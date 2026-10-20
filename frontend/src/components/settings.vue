<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { SETTINGS_TABS } from "../lib/nav";
import useApi from "../composables/useApi";
import { isAdmin, sessionToken } from "../composables/useSession";
import { selectedTeamId } from "../composables/useSelectedTeam";
import { selectedUserId } from "../composables/useSelectedUser";
import AppTabs from "./ui/AppTabs.vue";
import TeamSelect from "./team-select.vue";
import ProjectName from "./project-name.vue";

const route = useRoute();
const router = useRouter();
const { getMe, getTeams, postLogout } = useApi();
const accountName = ref("");
const accountTeam = ref("");

/** 탭마다 이 화면이 무엇을 바꾸는지 한 줄로 알려 준다. */
const tab = computed(() => {
    const value = String(route.params.tab || "teams");
    return SETTINGS_TABS.some((item) => item.id === value) ? value : "teams";
});

onMounted(async () => {
    try {
        const me = await getMe();
        accountName.value = me.name || "";
        const teams = await getTeams();
        const found = teams.find((team) => String(team.id) === String(me.team_id));
        accountTeam.value = found ? found.team_name : "";
    } catch {
        accountName.value = "";
    }
});

const logout = async () => {
    try {
        await postLogout();
    } catch {
        /* 세션이 이미 없어도 로그인 화면으로 보낸다. */
    }
    sessionToken.value = "";
    isAdmin.value = false;
    selectedUserId.value = null;
    selectedTeamId.value = null;
    sessionStorage.removeItem("reportData");
    sessionStorage.removeItem("reportRaw");
    sessionStorage.removeItem("reportDate");
    router.replace("/login");
};
</script>

<template>
    <div class="page">
        <section class="card account-card" aria-label="내 계정">
            <span class="account-avatar" aria-hidden="true">{{ (accountName || "?").slice(0, 1) }}</span>
            <div class="account-copy">
                <p class="account-name">{{ accountName || "로그인된 계정" }}</p>
                <p class="account-team">
                    <span v-if="accountTeam">{{ accountTeam }}</span>
                    <span v-else class="state-chip is-plain is-warning">부서 미지정</span>
                </p>
            </div>
            <button type="button" class="btn account-logout" @click="logout">로그아웃</button>
        </section>
        <AppTabs :tabs="SETTINGS_TABS" :active="tab" />
        <TeamSelect v-if="tab === 'teams'" embedded />
        <ProjectName v-else embedded />
    </div>
</template>

<style scoped src="../styles/components/settings.css"></style>
