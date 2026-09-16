<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Plus } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { selectedTeamId } from "../composables/useSelectedTeam.js";
import { selectedUserId } from "../composables/useSelectedUser.js";

import { useRouter } from "vue-router";
import { useDialog } from "../composables/useDialog";
import AppPageHeader from "./ui/AppPageHeader.vue";

const router = useRouter();

const { getTeams, postTeams, setTeam } = useApi();
const { alert: showAlert } = useDialog();

const teams = ref([]);
const newTeam = ref("");
const query = ref("");
const selectedTeam = ref(selectedTeamId.value ?? "");
const isSaving = ref(false);
const isLoading = ref(true);
const loadError = ref("");

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
        showAlert("사용자를 먼저 선택해주세요.");
        return;
    }
    try {
        await setTeam(teamId, selectedUserId.value);
        selectedTeam.value = teamId;
        selectedTeamId.value = teamId;
    } catch (error) {
        console.error("팀 지정 실패:", error);
        showAlert("팀 지정에 실패했습니다.");
    }
};

const saveTeam = async () => {
    const name = newTeam.value.trim();
    if (!name) {
        showAlert("팀 이름을 입력해주세요");
        return;
    }
    isSaving.value = true;
    try {
        await postTeams(name);
        newTeam.value = "";
        teams.value = await getTeams();
        showAlert(`'${name}' 팀을 생성했습니다.`);
    } catch (error) {
        console.error("팀 생성 실패:", error);
        showAlert("팀 생성에 실패했습니다. 중복된 이름인지 확인해주세요.");
    } finally {
        isSaving.value = false;
    }
};

onMounted(async () => {
    isLoading.value = true;
    loadError.value = "";
    try {
        teams.value = await getTeams();
    } catch (error) {
        console.error("팀 목록 조회 실패:", error);
        teams.value = [];
        loadError.value = "팀을 불러오지 못했습니다. 잠시 후 다시 시도하세요.";
    } finally {
        isLoading.value = false;
    }
});
</script>

<template>
    <div class="page teams-page">
        <AppPageHeader subtitle="보고서를 작성할 팀을 선택하세요" />

        <div v-if="teams.length > 0" class="team-toolbar">
            <input
                v-model="query"
                class="input"
                type="search"
                placeholder="팀 이름 검색"
                aria-label="팀 이름 검색"
            />
            <span class="team-count"
                >{{ filteredTeams.length }}/{{ teams.length }}개</span
            >
        </div>

        <div v-if="isLoading" class="empty-state">팀을 불러오는 중...</div>
        <div v-else-if="loadError" class="empty-state">{{ loadError }}</div>
        <div v-else-if="teams.length === 0" class="empty-state">
            등록된 팀이 없습니다. 아래에서 생성하세요.
        </div>
        <div v-else-if="filteredTeams.length === 0" class="empty-state">
            '{{ query.trim() }}'에 해당하는 팀이 없습니다
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
            </button>
        </div>

        <form class="card add-card" @submit.prevent="saveTeam">
            <h2>새 팀</h2>
            <div class="add-row">
                <input
                    id="new-team"
                    type="text"
                    v-model="newTeam"
                    class="input"
                    placeholder="팀 이름을 입력하세요"
                    required
                />
                <button
                    class="btn btn-primary"
                    type="submit"
                    :disabled="isSaving"
                >
                    <Plus :size="14" />
                    {{ isSaving ? "생성 중..." : "생성" }}
                </button>
            </div>
        </form>
    </div>
</template>

<style scoped>
.teams-page {
    max-width: 720px;
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

.add-card h2 {
    margin: 0 0 var(--space-3);
}

.add-row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
}

.add-row .input {
    flex: 1;
    min-width: 0;
}

.add-row .btn {
    flex-shrink: 0;
}

@media (max-width: 860px) {
    .add-row {
        flex-direction: column;
        align-items: stretch;
    }
}
</style>
