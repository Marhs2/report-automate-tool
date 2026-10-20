<script setup>
import { computed, onMounted, ref } from "vue";
import { Plus } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import AppPageHeader from "./ui/AppPageHeader.vue";

defineProps({
    embedded: { type: Boolean, default: false },
});

const { getTeams, postTeams, getUsers, postTeamLeader } = useApi();
const { alert: showAlert } = useDialog();

const teams = ref([]);
const members = ref([]);
const newTeam = ref("");
const query = ref("");
const isSaving = ref(false);
const isLoading = ref(true);
const loadError = ref("");

const teamLabel = (team) => team?.team_name || team?.name || "";

const membersOf = (team) =>
    members.value.filter((member) => String(member.team_id) === String(team.id));
const memberCountOf = (team) => membersOf(team).length;

/** 다른 부서로 옮긴 사람은 팀장이 아니다(서버도 같은 기준). */
const leaderValue = (team) =>
    membersOf(team).some((member) => String(member.id) === String(team.leader_id))
        ? String(team.leader_id)
        : "";

const leaderSaving = ref(null);
const setLeader = async (team, value) => {
    const memberId = value ? Number(value) : null;
    leaderSaving.value = team.id;
    try {
        await postTeamLeader(team.id, memberId);
        teams.value = teams.value.map((row) =>
            row.id === team.id ? { ...row, leader_id: memberId } : row,
        );
    } catch (error) {
        const detail = error?.response?.data?.detail;
        showAlert(
            typeof detail === "string" && detail.trim() ? detail : "팀장을 바꾸지 못했습니다.",
        );
        teams.value = await getTeams().catch(() => teams.value);
    } finally {
        leaderSaving.value = null;
    }
};

const filteredTeams = computed(() => {
    const q = query.value.trim().toLowerCase();
    if (!q) return teams.value;
    return teams.value.filter((team) =>
        String(teamLabel(team)).toLowerCase().includes(q),
    );
});

const saveTeam = async () => {
    const name = newTeam.value.trim();
    if (!name) {
        showAlert("부서 이름을 입력해주세요");
        return;
    }
    isSaving.value = true;
    try {
        await postTeams(name);
        newTeam.value = "";
        teams.value = await getTeams();
        showAlert(`'${name}' 부서를 만들었습니다.`);
    } catch (error) {
        const detail = error?.response?.data?.detail;
        showAlert(
            typeof detail === "string" && detail.trim()
                ? detail
                : "부서를 만들지 못했습니다. 중복된 이름인지 확인해주세요.",
        );
    } finally {
        isSaving.value = false;
    }
};

onMounted(async () => {
    isLoading.value = true;
    loadError.value = "";
    try {
        const [teamRows, userRows] = await Promise.all([getTeams(), getUsers()]);
        teams.value = teamRows;
        members.value = userRows;
    } catch (error) {
        console.error("부서 목록 조회 실패:", error);
        teams.value = [];
        loadError.value = "부서를 불러오지 못했습니다.";
    } finally {
        isLoading.value = false;
    }
});
</script>

<template>
    <div :class="embedded ? 'settings-pane' : 'page'">
        <AppPageHeader v-if="!embedded" subtitle="부서" />

        <div v-if="teams.length > 0" class="team-toolbar">
            <input
                v-model="query"
                class="input"
                type="search"
                placeholder="부서 이름 검색"
                aria-label="부서 이름 검색"
            />
            <span class="team-count"
                >{{ filteredTeams.length }}/{{ teams.length }}개</span
            >
        </div>

        <div v-if="isLoading" class="empty-state">부서를 불러오는 중...</div>
        <div v-else-if="loadError" class="empty-state">{{ loadError }}</div>
        <div v-else-if="teams.length === 0" class="empty-state">
            등록된 부서가 없습니다. 아래에서 만드세요.
        </div>
        <div v-else-if="filteredTeams.length === 0" class="empty-state">
            '{{ query.trim() }}'에 해당하는 부서가 없습니다
        </div>
        <div v-else class="team-board">
            <div
                v-for="team in filteredTeams"
                :key="team.id"
                class="select-card"
            >
                <span class="avatar">{{
                    String(teamLabel(team) || "?").slice(0, 1)
                }}</span>
                <span class="select-card-name">{{ teamLabel(team) }}</span>
                <span class="select-card-meta">{{ memberCountOf(team) }}명</span>
                <select
                    class="input team-leader"
                    :value="leaderValue(team)"
                    :disabled="leaderSaving === team.id || !memberCountOf(team)"
                    :aria-label="`${teamLabel(team)} 팀장`"
                    @change="setLeader(team, $event.target.value)"
                >
                    <option value="">팀장 없음</option>
                    <option v-for="member in membersOf(team)" :key="member.id" :value="String(member.id)">
                        팀장 · {{ member.name }}
                    </option>
                </select>
            </div>
        </div>

        <form class="card add-card" @submit.prevent="saveTeam">
            <h2>새 부서</h2>
            <div class="add-row">
                <input
                    id="new-team"
                    type="text"
                    v-model="newTeam"
                    class="input"
                    placeholder="부서 이름을 입력하세요"
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

<style scoped src="../styles/components/admin-teams.css"></style>
