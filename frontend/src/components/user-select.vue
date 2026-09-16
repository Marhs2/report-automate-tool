<script setup>
import { computed, onMounted, ref } from "vue";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser.js";
import { useRouter } from "vue-router";
import { Plus } from "lucide-vue-next";
import { useDialog } from "../composables/useDialog";
import AppPageHeader from "./ui/AppPageHeader.vue";

const router = useRouter();

const { getUsers, postUsers } = useApi();
const { alert: showAlert } = useDialog();

const users = ref([]);
const newUser = ref("");
const query = ref("");
const selectedUser = ref(selectedUserId.value ?? "");
const isSaving = ref(false);

const filteredUsers = computed(() => {
    const q = query.value.trim().toLowerCase();
    if (!q) return users.value;
    return users.value.filter((user) =>
        String(user.name || "").toLowerCase().includes(q),
    );
});

const isSelected = (id) => String(selectedUser.value) === String(id);

const setUser = (id) => {
    if (id === undefined || id === null || id === "" || id === "선택") {
        showAlert("유저를 선택해주세요");
        return;
    }
    selectedUser.value = id;
    selectedUserId.value = id;
    router.push("/");
};

const saveUser = async () => {
    const name = newUser.value.trim();
    if (!name) {
        showAlert("이름을 입력해주세요");
        return;
    }
    isSaving.value = true;
    try {
        await postUsers(name);
        newUser.value = "";
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

onMounted(async () => {
    const data = await getUsers();
    users.value = data;
});
</script>

<template>
    <div class="page users-page">
        <AppPageHeader subtitle="보고서를 작성할 사용자를 선택하세요" />

        <div v-if="users.length > 0" class="user-toolbar">
            <input
                v-model="query"
                class="input"
                type="search"
                placeholder="이름 검색"
                aria-label="사용자 이름 검색"
            />
            <span class="user-count"
                >{{ filteredUsers.length }}/{{ users.length }}명</span
            >
        </div>

        <div v-if="users.length === 0" class="empty-state">
            등록된 사용자가 없습니다. 아래에서 생성하세요.
        </div>
        <div v-else-if="filteredUsers.length === 0" class="empty-state">
            '{{ query.trim() }}'에 해당하는 사용자가 없습니다
        </div>
        <div v-else class="user-grid">
            <button
                v-for="user in filteredUsers"
                :key="user.id"
                type="button"
                class="user-card"
                :class="{ selected: isSelected(user.id) }"
                @click="setUser(user.id)"
            >
                <span class="avatar">{{
                    String(user.name || "?").slice(0, 1)
                }}</span>
                <span class="user-name">{{ user.name }}</span>
            </button>
        </div>

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
.users-page {
    max-width: 720px;
}

.user-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
}

.user-toolbar .input {
    flex: 1;
    min-width: 0;
}

.user-count {
    flex-shrink: 0;
    font-size: 12px;
    font-weight: 650;
    color: var(--text);
}

.user-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 12px;
    margin-bottom: 28px;
    max-height: min(52vh, 420px);
    overflow-y: auto;
    padding-right: 4px;
}

.user-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 16px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--bg);
    cursor: pointer;
    text-align: left;
    font: inherit;
    color: inherit;
}

.user-card:hover {
    border-color: var(--accent);
}

.user-card.selected {
    border-color: var(--accent);
    background: var(--accent-bg);
}

.avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: var(--bg-soft);
    color: var(--text-h);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 650;
    flex-shrink: 0;
}

.user-card.selected .avatar {
    background: var(--accent);
    color: #fff;
}

.user-name {
    font-size: 15px;
    font-weight: 500;
    color: var(--text-h);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.add-card h2 {
    margin: 0 0 12px;
}

.add-row {
    display: flex;
    gap: 10px;
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
