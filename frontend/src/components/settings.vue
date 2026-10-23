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
/** loading · ready · error: 계정 칸이 "로그인된 계정"으로 잠깐 잘못 보이지 않게 한다. */
const accountState = ref("loading");

const tab = computed(() => {
    const value = String(route.params.tab || "teams");
    return SETTINGS_TABS.some((item) => item.id === value) ? value : "teams";
});

const accountInitial = computed(() => (accountName.value || "?").slice(0, 1));

const loadAccount = async () => {
    accountState.value = "loading";
    try {
        const me = await getMe();
        accountName.value = me.name || "";
        const teams = await getTeams();
        const found = teams.find((team) => String(team.id) === String(me.team_id));
        accountTeam.value = found ? found.team_name : "";
        accountState.value = "ready";
    } catch {
        accountName.value = "";
        accountState.value = "error";
    }
};

onMounted(loadAccount);

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
    <div class="page settings">
        <section class="card account" aria-label="내 계정">
            <div v-if="accountState === 'loading'" class="account-who" aria-busy="true">
                <span class="account-avatar is-blank" aria-hidden="true"></span>
                <span class="account-lines" aria-hidden="true">
                    <span class="skeleton is-name"></span>
                    <span class="skeleton is-team"></span>
                </span>
                <span class="sr-only">계정 정보를 불러오는 중</span>
            </div>
            <div v-else-if="accountState === 'error'" class="account-who is-error" role="alert">
                <p class="account-error">계정 정보를 불러오지 못했습니다.</p>
                <button type="button" class="btn btn-small" @click="loadAccount">다시 시도</button>
            </div>
            <div v-else class="account-who">
                <span class="account-avatar" aria-hidden="true">{{ accountInitial }}</span>
                <span class="account-lines">
                    <span class="account-name">{{ accountName || "로그인된 계정" }}</span>
                    <span v-if="accountTeam" class="account-team">{{ accountTeam }}</span>
                    <span v-else class="account-flag">부서 미지정</span>
                </span>
            </div>
            <button type="button" class="btn account-logout" @click="logout">로그아웃</button>
        </section>

        <div class="settings-main">
            <AppTabs :tabs="SETTINGS_TABS" :active="tab" />
            <TeamSelect v-if="tab === 'teams'" embedded />
            <ProjectName v-else embedded />
        </div>
    </div>
</template>

<style scoped src="../styles/components/settings.css"></style>
