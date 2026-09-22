<script setup>
import { computed, onMounted, ref, watch } from "vue";
import useApi from "../composables/useApi";
import { selectedTeamId } from "../composables/useSelectedTeam.js";
import { selectedUserId } from "../composables/useSelectedUser.js";

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
    members.value.filter((member) => String(member.team_id) === String(team.id))
        .length;

watch(selectedTeamId, (id) => {
    selectedTeam.value = id ?? "";
});

const teamLabel = (team) => team?.team_name || team?.name || "";

const filteredTeams = computed(() => {
    const q = query.value.trim().toLowerCase();
    if (!q) return teams.value;
    return teams.value.filter((team) =>
        String(teamLabel(team)).toLowerCase().includes(q),
    );
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

onMounted(async () => {
    isLoading.value = true;
    loadError.value = "";
    try {
        teams.value = await getTeams();
    } catch (error) {
        console.error("부서 목록 조회 실패:", error);
        teams.value = [];
        loadError.value = "부서을 불러오지 못했습니다. 잠시 후 다시 시도하세요.";
    } finally {
        isLoading.value = false;
    }
    try {
        members.value = await getUsers();
    } catch (error) {
        console.error("사용자 목록 조회 실패:", error);
        members.value = [];
    }
});
</script>

<template>
    <div :class="embedded ? 'settings-pane' : 'page'">
        <AppPageHeader v-if="!embedded" subtitle="보고서를 작성할 부서를 선택하세요" />

        <div v-if="teams.length > 0" class="team-toolbar">
            <input
                v-model="query"
                class="input"
                type="search"
                placeholder="부서 이름 검색"
                aria-label="부서 이름 검색"
            />

        </div>

        <div v-if="isLoading" class="empty-state">부서을 불러오는 중...</div>
        <div v-else-if="loadError" class="empty-state">{{ loadError }}</div>
        <div v-else-if="teams.length === 0" class="empty-state">
            등록된 부서가 없습니다.
        </div>
        <div v-else-if="filteredTeams.length === 0" class="empty-state">
            '{{ query.trim() }}'에 해당하는 부서이 없습니다
        </div>
        <div v-else class="select-grid">
            <button
                v-for="team in filteredTeams"
                :key="team.id"
                type="button"
                class="select-card"
                :class="{ selected: isSelected(team.id) }"
                @click="assignTeam(team.id)"
            >
                <span class="avatar">{{
                    String(teamLabel(team) || "?").slice(0, 1)
                }}</span>
                <span class="select-card-name">{{ teamLabel(team) }}</span>
                <span class="select-card-meta">{{ memberCountOf(team) }}명</span>
            </button>
        </div>
    </div>
</template>

<style scoped>
.settings-pane {
    min-width: 0;
}

/* 카드 그리드(.select-grid/.select-card)는 components.css 전역 규칙을 쓴다. */
.team-toolbar {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
}

.team-toolbar .input {
    flex: 1;
    min-width: 0;
}

.team-count {
    flex-shrink: 0;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.select-card-meta {
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.team-note {
    margin: var(--space-3) 0 var(--space-5);
    font-size: var(--fs-12);
    color: var(--text);
    word-break: keep-all;
}

</style>
