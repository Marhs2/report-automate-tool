<script setup>
import { computed, onMounted, ref, watch } from "vue";
import useApi from "../composables/useApi";
import { selectedTeamId } from "../composables/useSelectedTeam.js";
import { selectedUserId } from "../composables/useSelectedUser.js";
import { isAdmin } from "../composables/useSession";
import { useDialog } from "../composables/useDialog";
import AppPageHeader from "./ui/AppPageHeader.vue";

defineProps({
    embedded: { type: Boolean, default: false },
});

const { getTeams, setTeam, getUsers } = useApi();
const { alert: showAlert } = useDialog();

const teams = ref([]);
const members = ref([]);
const query = ref("");
const selectedTeam = ref(selectedTeamId.value ?? "");
const isLoading = ref(true);
const loadError = ref("");

/** 부서마다 몇 명이 있는지. 0명이면 그 부서는 아직 아무 데도 쓰이지 않는다. */
const memberCountOf = (team) =>
    members.value.filter((member) => String(member.team_id) === String(team.id)).length;

watch(selectedTeamId, (id) => {
    selectedTeam.value = id ?? "";
});

const teamLabel = (team) => team?.team_name || team?.name || "";

const filteredTeams = computed(() => {
    const q = query.value.trim().toLowerCase();
    if (!q) return teams.value;
    return teams.value.filter((team) => String(teamLabel(team)).toLowerCase().includes(q));
});

const isSelected = (id) => String(selectedTeam.value) === String(id);

const assignTeam = async (teamId) => {
    if (selectedUserId.value == null || selectedUserId.value === "") {
        showAlert("로그인이 필요합니다.");
        return;
    }
    try {
        await setTeam(teamId, selectedUserId.value);
        selectedTeam.value = teamId;
        selectedTeamId.value = teamId;
    } catch (error) {
        console.error("부서 지정 실패:", error);
        showAlert("부서 지정에 실패했습니다.");
    }
};

const loadTeams = async () => {
    isLoading.value = true;
    loadError.value = "";
    try {
        teams.value = await getTeams();
    } catch (error) {
        console.error("부서 목록 조회 실패:", error);
        teams.value = [];
        loadError.value = "부서를 불러오지 못했습니다.";
    } finally {
        isLoading.value = false;
    }
    try {
        members.value = await getUsers();
    } catch (error) {
        console.error("사용자 목록 조회 실패:", error);
        members.value = [];
    }
};

onMounted(loadTeams);
</script>

<template>
    <div :class="embedded ? 'team-pick' : 'page'">
        <AppPageHeader v-if="!embedded" subtitle="보고서를 작성할 부서를 선택하세요" />

        <section class="card board" aria-labelledby="team-pick-title">
            <header class="board-head">
                <h2 id="team-pick-title" class="board-title">부서 선택</h2>
                <input
                    v-if="teams.length > 0"
                    v-model="query"
                    class="input board-search"
                    type="search"
                    placeholder="부서 이름 검색"
                    aria-label="부서 이름 검색"
                />
            </header>

            <div v-if="isLoading" aria-busy="true">
                <div v-for="n in 4" :key="n" class="skeleton-row" aria-hidden="true">
                    <span class="skeleton is-radio"></span>
                    <span class="skeleton is-name"></span>
                    <span class="skeleton is-count"></span>
                </div>
                <span class="sr-only">부서를 불러오는 중</span>
            </div>
            <div v-else-if="loadError" class="board-state is-error" role="alert">
                <p>{{ loadError }}</p>
                <button type="button" class="btn btn-small" @click="loadTeams">다시 시도</button>
            </div>
            <div v-else-if="teams.length === 0" class="board-state">
                <p>등록된 부서가 없습니다.</p>
                <router-link v-if="isAdmin" class="btn btn-small" to="/admin/teams">부서 만들기</router-link>
            </div>
            <div v-else-if="filteredTeams.length === 0" class="board-state">
                <p>'{{ query.trim() }}'에 해당하는 부서가 없습니다</p>
                <button type="button" class="btn btn-small btn-ghost" @click="query = ''">검색 지우기</button>
            </div>
            <div v-else class="team-options" role="radiogroup" aria-labelledby="team-pick-title">
                <button
                    v-for="team in filteredTeams"
                    :key="team.id"
                    type="button"
                    class="team-option"
                    :class="{ 'is-mine': isSelected(team.id) }"
                    role="radio"
                    :aria-checked="isSelected(team.id)"
                    @click="assignTeam(team.id)"
                >
                    <span class="team-radio" aria-hidden="true"></span>
                    <span class="team-name">{{ teamLabel(team) }}</span>
                    <span v-if="isSelected(team.id)" class="team-mine">내 부서</span>
                    <span class="team-count">{{ memberCountOf(team) }}명</span>
                </button>
            </div>
        </section>
    </div>
</template>

<style scoped src="../styles/components/team-select.css"></style>
