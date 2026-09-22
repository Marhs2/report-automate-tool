<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { SETTINGS_TABS } from "../lib/nav";
import useApi from "../composables/useApi";
import { isAdmin, sessionToken } from "../composables/useSession";
import { selectedTeamId } from "../composables/useSelectedTeam";
import { selectedUserId } from "../composables/useSelectedUser";
import AppPageHeader from "./ui/AppPageHeader.vue";
import AppTabs from "./ui/AppTabs.vue";
import TeamSelect from "./team-select.vue";
import ProjectName from "./project-name.vue";

const route = useRoute();
const router = useRouter();
const { getMe, getTeams, postLogout } = useApi();
const accountName = ref("");
const accountTeam = ref("");

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
        <AppPageHeader subtitle="내 부서 · 프로젝트명" />
        <AppTabs :tabs="SETTINGS_TABS" :active="tab" />
        <TeamSelect v-if="tab === 'teams'" embedded />
        <ProjectName v-else embedded />
        <section class="card account-card">
            <div class="account-copy">
                <p class="account-name">{{ accountName || "로그인된 계정" }}</p>
                <p v-if="accountTeam" class="account-team">{{ accountTeam }}</p>
            </div>
            <button type="button" class="btn account-logout" @click="logout">로그아웃</button>
        </section>
    </div>
</template>

<style scoped>
.account-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-top: 16px;
}

.account-name,
.account-team {
    margin: 0;
    word-break: keep-all;
}

.account-name {
    font-size: 15px;
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.account-team {
    margin-top: 2px;
    font-size: 13px;
    color: var(--text);
}

.account-logout {
    flex-shrink: 0;
    min-height: 44px;
}

@media (max-width: 860px) {
    .account-card {
        flex-direction: column;
        align-items: stretch;
    }

    .account-logout {
        width: 100%;
    }
}
</style>
