<script setup>
import { computed, onMounted, ref } from "vue";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser.js";
import { selectedTeamId } from "../composables/useSelectedTeam.js";
import { Plus } from "lucide-vue-next";
import { useDialog } from "../composables/useDialog";
import AppPageHeader from "./ui/AppPageHeader.vue";

const props = defineProps({
    embedded: { type: Boolean, default: false },
});

const { getUsers, postUsers, getTeams, setTeam, changeMyPassword, setMemberPassword } = useApi();
const { alert: showAlert } = useDialog();

const users = ref([]);
const teams = ref([]);
const newUser = ref("");
const newPassword = ref("");
const query = ref("");
const teamFilter = ref("all");
const selectedUser = ref(selectedUserId.value ?? "");
const isSaving = ref(false);
const assigningId = ref("");
const currentPassword = ref("");
const nextPassword = ref("");
const passwordSaving = ref(false);
const tempPasswords = ref({});
const tempSavingId = ref("");

const CHOSUNG = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];

const nameChosung = (name) => {
    const ch = String(name || "").trim().charAt(0);
    if (!ch) return "#";
    const code = ch.charCodeAt(0);
    if (code >= 0xac00 && code <= 0xd7a3) {
        return CHOSUNG[Math.floor((code - 0xac00) / 588)];
    }
    if (/[A-Za-z]/.test(ch)) return ch.toUpperCase();
    return "#";
};

const isSelected = (id) => String(selectedUser.value) === String(id);
const isMe = (user) => String(user.id) === String(selectedUserId.value);

const teamNameOf = (user) => {
    const found = teams.value.find(
        (team) => String(team.id) === String(user.team_id),
    );
    return found?.team_name || "미지정";
};

const isUnassigned = (user) => !user.team_id || teamNameOf(user) === "미지정";

const unassignedCount = computed(() => users.value.filter(isUnassigned).length);

const realTeams = computed(() =>
    teams.value.filter((team) => String(team.team_name).trim() !== "미지정"),
);

const selectedRecord = computed(() =>
    users.value.find((user) => isSelected(user.id)) || null,
);

const filteredUsers = computed(() => {
    const q = query.value.trim().toLowerCase();
    let list = users.value;
    if (q) {
        list = list.filter((user) => {
            const name = String(user.name || "").toLowerCase();
            const team = teamNameOf(user).toLowerCase();
            return name.includes(q) || team.includes(q);
        });
    }
    if (teamFilter.value === "unassigned") {
        list = list.filter(isUnassigned);
    } else if (teamFilter.value !== "all") {
        list = list.filter(
            (user) => String(user.team_id) === String(teamFilter.value),
        );
    }
    return [...list].sort((a, b) =>
        String(a.name || "").localeCompare(String(b.name || ""), "ko"),
    );
});

const userGroups = computed(() => {
    const groups = new Map();
    for (const user of filteredUsers.value) {
        const letter = nameChosung(user.name);
        if (!groups.has(letter)) groups.set(letter, []);
        groups.get(letter).push(user);
    }
    return [...groups.entries()].map(([letter, items]) => ({ letter, items }));
});

const teamCount = (teamId) =>
    users.value.filter((user) => String(user.team_id) === String(teamId)).length;

const jumpToGroup = (letter) => {
    document
        .getElementById(`user-group-${letter}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
};

const assignTeam = async (user, teamId) => {
    if (!teamId || String(teamId) === String(user.team_id)) return;
    assigningId.value = String(user.id);
    try {
        await setTeam(Number(teamId), user.id);
        user.team_id = Number(teamId);
        if (isMe(user)) selectedTeamId.value = Number(teamId);
    } catch (error) {
        console.error("부서 지정 실패:", error);
        const detail = error?.response?.data?.detail;
        showAlert(
            typeof detail === "string" && detail.trim()
                ? detail
                : "부서 지정에 실패했습니다.",
        );
    } finally {
        assigningId.value = "";
    }
};

const saveUser = async () => {
    const name = newUser.value.trim();
    const password = newPassword.value;
    if (!name) {
        showAlert("이름을 입력해주세요");
        return;
    }
    if (!password || password.length < 4) {
        showAlert("비밀번호는 4자 이상이어야 합니다.");
        return;
    }
    isSaving.value = true;
    try {
        await postUsers(name, null, password);
        newUser.value = "";
        newPassword.value = "";
        users.value = await getUsers();
        showAlert(`'${name}' 사용자를 생성했습니다.`);
    } catch (error) {
        console.error("사용자 생성 실패:", error);
        const detail = error?.response?.data?.detail;
        const message =
            typeof detail === "string" && detail.trim()
                ? detail
                : "사용자 생성에 실패했습니다.";
        showAlert(message);
    } finally {
        isSaving.value = false;
    }
};

const saveMyPassword = async () => {
    if (!currentPassword.value || !nextPassword.value) {
        showAlert("현재 비밀번호와 새 비밀번호를 입력해주세요.");
        return;
    }
    if (nextPassword.value.length < 4) {
        showAlert("새 비밀번호는 4자 이상이어야 합니다.");
        return;
    }
    passwordSaving.value = true;
    try {
        await changeMyPassword(currentPassword.value, nextPassword.value);
        currentPassword.value = "";
        nextPassword.value = "";
        showAlert("비밀번호를 바꿨습니다.");
    } catch (error) {
        const detail = error?.response?.data?.detail;
        showAlert(
            typeof detail === "string" && detail.trim()
                ? detail
                : "비밀번호를 바꾸지 못했습니다.",
        );
    } finally {
        passwordSaving.value = false;
    }
};

const giveTempPassword = async (user) => {
    const secret = String(tempPasswords.value[user.id] || "");
    if (secret.length < 4) {
        showAlert("임시 비밀번호는 4자 이상이어야 합니다.");
        return;
    }
    tempSavingId.value = String(user.id);
    try {
        await setMemberPassword(user.id, secret);
        user.has_password = true;
        tempPasswords.value[user.id] = "";
        showAlert(`${user.name}에게 임시 비밀번호를 넣었습니다. 본인에게만 알려주세요.`);
    } catch (error) {
        const detail = error?.response?.data?.detail;
        showAlert(
            typeof detail === "string" && detail.trim()
                ? detail
                : "임시 비밀번호를 넣지 못했습니다.",
        );
    } finally {
        tempSavingId.value = "";
    }
};

onMounted(async () => {
    users.value = await getUsers();
    selectedUser.value = selectedUserId.value ?? "";
    try {
        teams.value = await getTeams();
    } catch (error) {
        console.error("부서 목록 조회 실패:", error);
        teams.value = [];
    }
});
</script>

<template>
    <div :class="embedded ? 'settings-pane' : 'page'">
        <AppPageHeader v-if="!embedded" subtitle="사용자" />

        <div v-if="users.length > 0" class="user-toolbar">
            <input
                v-model="query"
                class="input"
                type="search"
                placeholder="이름 또는 부서 검색"
                aria-label="사용자 검색"
            />
            <span class="user-count"
                >{{ filteredUsers.length }}/{{ users.length }}명</span
            >
        </div>

        <div v-if="users.length > 0" class="team-filters" role="tablist" aria-label="부서 필터">
            <button
                type="button"
                class="team-chip"
                :class="{ 'is-on': teamFilter === 'all' }"
                @click="teamFilter = 'all'"
            >
                전체 {{ users.length }}
            </button>
            <button
                type="button"
                class="team-chip"
                :class="{ 'is-on': teamFilter === 'unassigned' }"
                @click="teamFilter = 'unassigned'"
            >
                미지정 {{ unassignedCount }}
            </button>
            <button
                v-for="team in realTeams"
                :key="team.id"
                type="button"
                class="team-chip"
                :class="{ 'is-on': teamFilter === String(team.id) }"
                @click="teamFilter = String(team.id)"
            >
                {{ team.team_name }} {{ teamCount(team.id) }}
            </button>
        </div>

        <nav v-if="userGroups.length > 1" class="letter-jump" aria-label="초성 바로가기">
            <button
                v-for="group in userGroups"
                :key="`jump-${group.letter}`"
                type="button"
                class="letter-chip"
                @click="jumpToGroup(group.letter)"
            >
                {{ group.letter }}
            </button>
        </nav>

        <div v-if="embedded && unassignedCount" class="team-gap" role="status">
            <p class="team-gap-copy">
                부서 미지정 {{ unassignedCount }}명.
                비밀번호가 없는 사람만 임시 비밀번호를 넣어 줄 수 있습니다.
            </p>
        </div>

        <div v-if="users.length === 0" class="empty-state">
            등록된 사용자가 없습니다. 아래에서 생성하세요.
        </div>
        <div v-else-if="filteredUsers.length === 0" class="empty-state">
            조건에 맞는 사용자가 없습니다
        </div>
        <div v-else class="user-groups">
            <section
                v-for="group in userGroups"
                :id="`user-group-${group.letter}`"
                :key="group.letter"
                class="user-group"
            >
                <h3 class="group-head">{{ group.letter }} <span>{{ group.items.length }}</span></h3>
                <div class="user-rows">
                    <div
                        v-for="user in group.items"
                        :key="user.id"
                        class="user-row"
                        :class="{ selected: isMe(user) }"
                    >
                        <span class="avatar">{{ String(user.name || "?").slice(0, 1) }}</span>
                        <span class="user-row-name">
                            {{ user.name }}
                            <em v-if="isUnassigned(user)">미지정</em>
                        </span>
                        <label class="user-row-team">
                            <span class="sr-only">부서</span>
                            <select
                                class="input"
                                :value="String(user.team_id || '')"
                                :disabled="teams.length === 0 || assigningId === String(user.id)"
                                @change="assignTeam(user, $event.target.value)"
                            >
                                <option value="" disabled>부서 선택</option>
                                <option v-for="team in teams" :key="team.id" :value="String(team.id)">
                                    {{ team.team_name }}
                                </option>
                            </select>
                        </label>
                        <span v-if="isMe(user)" class="user-row-now">로그인 중</span>
                        <div v-else-if="!user.has_password" class="user-row-temp">
                            <input
                                class="input"
                                type="password"
                                :value="tempPasswords[user.id] || ''"
                                placeholder="임시 비밀번호"
                                minlength="4"
                                @input="tempPasswords[user.id] = $event.target.value"
                            />
                            <button
                                type="button"
                                class="btn btn-small"
                                :disabled="tempSavingId === String(user.id)"
                                @click="giveTempPassword(user)"
                            >
                                넣기
                            </button>
                        </div>
                    </div>
                </div>
            </section>
        </div>

        <form v-if="selectedRecord" class="card add-card" @submit.prevent="saveMyPassword">
            <h2>내 비밀번호 변경</h2>
            <div class="add-row">
                <input
                    type="password"
                    v-model="currentPassword"
                    class="input"
                    placeholder="현재 비밀번호"
                    autocomplete="current-password"
                    required
                />
                <input
                    type="password"
                    v-model="nextPassword"
                    class="input"
                    placeholder="새 비밀번호 (4자 이상)"
                    minlength="4"
                    autocomplete="new-password"
                    required
                />
                <button class="btn btn-primary" type="submit" :disabled="passwordSaving">
                    {{ passwordSaving ? "변경 중..." : "변경" }}
                </button>
            </div>
        </form>

        <form class="card add-card" @submit.prevent="saveUser">
            <h2>새 사용자</h2>
            <div class="add-row">
                <input
                    id="new-user"
                    type="text"
                    v-model="newUser"
                    class="input"
                    placeholder="이름을 입력하세요"
                    required
                />
                <input
                    id="new-user-password"
                    type="password"
                    v-model="newPassword"
                    class="input"
                    placeholder="비밀번호 (4자 이상)"
                    required
                    minlength="4"
                    autocomplete="new-password"
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
.settings-pane {
    min-width: 0;
}

.user-toolbar {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--bg);
    padding: var(--space-2) 0;
}

.user-toolbar .input {
    flex: 1;
    min-width: 0;
}

.user-count {
    flex-shrink: 0;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.team-filters,
.letter-jump {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
}

.team-chip,
.letter-chip {
    flex-shrink: 0;
    min-height: 32px;
    padding: 0 10px;
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    background: var(--surface);
    color: var(--text);
    font: inherit;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    cursor: pointer;
}

.team-chip.is-on,
.letter-chip:focus-visible {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent-hover);
}

.team-gap {
    margin: 0 0 var(--space-3);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--warning-border);
    border-radius: var(--radius);
    background: var(--warning-bg);
    color: var(--warning-fg);
    font-size: var(--fs-13);
    word-break: keep-all;
}

.team-gap-copy {
    margin: 0;
}

.user-groups {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    margin-bottom: var(--space-5);
}

.group-head {
    margin: 0 0 var(--space-2);
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.group-head span {
    font-weight: var(--fw-medium);
    color: var(--text-muted);
}

.user-rows {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    overflow: hidden;
}

.user-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-4);
    border-bottom: 1px solid var(--border);
}

.user-row:last-child {
    border-bottom: none;
}

.user-row.selected {
    background: var(--accent-soft);
}

.user-row-name {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
    font-size: var(--fs-14);
    font-weight: var(--fw-medium);
    color: var(--text-strong);
}

.user-row-name em {
    font-style: normal;
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
    color: var(--text-muted);
}

.user-row-team {
    flex-shrink: 0;
}

.user-row-team-name {
    flex-shrink: 0;
    min-width: 148px;
    font-size: var(--fs-13);
    color: var(--text);
}

.user-row-team-name {
    flex-shrink: 0;
    min-width: 148px;
    font-size: var(--fs-13);
    color: var(--text);
}

.user-row-team .input {
    width: auto;
    min-width: 148px;
    height: 32px;
    padding: 0 28px 0 12px;
    line-height: 30px;
    font-size: var(--fs-13);
}

.user-row-now {
    flex-shrink: 0;
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
    color: var(--accent-hover);
}

.user-row-temp {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
}

.user-row-temp .input {
    width: 148px;
    height: 32px;
}

.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
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
    .add-row,
    .user-row {
        flex-direction: column;
        align-items: stretch;
    }

    .user-row-team .input,
    .user-row-temp .input {
        width: 100%;
    }
}
</style>
