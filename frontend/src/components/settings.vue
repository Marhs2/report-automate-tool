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
const TAB_NOTES = {
};

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
        <p class="section-note">{{ TAB_NOTES[tab] }}</p>
        <TeamSelect v-if="tab === 'teams'" embedded />
        <ProjectName v-else embedded />
    </div>
</template>

<style scoped>
.account-card {
    display: flex;
    align-items: center;
    gap: var(--space-3);
}

.account-avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: var(--control-h-lg);
    height: var(--control-h-lg);
    flex-shrink: 0;
    border-radius: var(--radius-pill);
    background: var(--accent-soft);
    color: var(--accent-hover);
    font-size: var(--fs-16);
    font-weight: var(--fw-bold);
}

.account-copy {
    flex: 1;
    min-width: 0;
}

.account-name,
.account-team {
    margin: 0;
    word-break: keep-all;
}

.account-name {
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.account-team {
    margin-top: var(--space-1);
    font-size: var(--fs-13);
    color: var(--text);
}

.account-logout {
    flex-shrink: 0;
    min-height: var(--control-h-lg);
}

@media (max-width: 860px) {
    .account-card {
        flex-wrap: wrap;
    }

    .account-logout {
        width: 100%;
    }
}
</style>
