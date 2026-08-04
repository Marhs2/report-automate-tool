<script setup>
import { ref, onMounted } from "vue";
import useAPI from "../composables/useApi";
import { Trash2 } from "lucide-vue-next";

const {
    getRegisteredProjectNames,
    postProjectName,
    deleteProjectName,
} = useAPI();

const projectNames = ref([]);
const newName = ref("");
const isLoading = ref(false);

const fetchProjectNames = async () => {
    isLoading.value = true;
    try {
        projectNames.value = await getRegisteredProjectNames();
    } catch (error) {
        console.error("프로젝트 명 조회 실패:", error);
    } finally {
        isLoading.value = false;
    }
};

const addProjectName = async () => {
    const name = newName.value.trim();
    if (!name) {
        alert("프로젝트 명을 입력해주세요.");
        return;
    }
    try {
        await postProjectName(name);
        newName.value = "";
        await fetchProjectNames();
    } catch (error) {
        const detail = error.response?.data?.detail;
        alert(detail || "프로젝트 명 등록에 실패했습니다.");
    }
};

const removeProjectName = async (name) => {
    if (!confirm(`'${name}' 프로젝트 명을 삭제하시겠습니까?`)) return;
    try {
        await deleteProjectName(name);
        await fetchProjectNames();
    } catch (error) {
        const detail = error.response?.data?.detail;
        alert(detail || "삭제에 실패했습니다.");
    }
};

onMounted(() => {
    fetchProjectNames();
});
</script>

<template>
    <div class="page">
        <div class="page-header">
            <div>
                <h1>프로젝트 명 관리</h1>
                <p class="page-subtitle">
                    등록된 프로젝트 명은 보고서 작성 시 AI가 프로젝트를
                    구분하는 데 사용됩니다
                </p>
            </div>
        </div>

        <div class="card">
            <h2>새 프로젝트 명 등록</h2>
            <div class="add-form">
                <div class="field">
                    <label for="name-input">프로젝트 명</label>
                    <input
                        id="name-input"
                        type="text"
                        v-model="newName"
                        class="input"
                        placeholder="예: A사 MES 구축"
                        @keyup.enter="addProjectName"
                    />
                </div>
                <button class="btn btn-primary add-btn" @click="addProjectName">
                    등록
                </button>
            </div>
        </div>

        <div class="card">
            <h2>등록된 프로젝트 명 목록</h2>
            <div v-if="isLoading" class="empty-state">불러오는 중...</div>
            <div v-else-if="projectNames.length === 0" class="empty-state">
                등록된 프로젝트 명이 없습니다
            </div>
            <table v-else class="name-table">
                <thead>
                    <tr>
                        <th>프로젝트 명</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="item in projectNames" :key="item.name">
                        <td class="name-cell">{{ item.name }}</td>
                        <td class="action-cell">
                            <button
                                class="btn btn-icon"
                                @click="removeProjectName(item.name)"
                                title="삭제"
                            >
                                <Trash2 :size="14" />
                            </button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>

<style scoped>
.add-form {
    display: flex;
    align-items: flex-end;
    gap: 12px;
    flex-wrap: wrap;
}

.add-form .field {
    flex: 1;
    min-width: 220px;
}

.add-btn {
    flex-shrink: 0;
    margin-bottom: 0;
}

.name-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}

.name-table th {
    text-align: left;
    padding: 10px 12px;
    border-bottom: 2px solid var(--border);
    color: var(--text);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

.name-table td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
}

.name-table tr:last-child td {
    border-bottom: none;
}

.name-cell {
    font-weight: 600;
    color: var(--text-h);
}

.action-cell {
    width: 40px;
    text-align: center;
}

.btn-icon {
    padding: 6px;
    border: none;
    background: none;
    color: var(--text);
    opacity: 0.6;
    cursor: pointer;
    border-radius: var(--radius-sm);
    transition:
        opacity 0.15s,
        background 0.15s;
}

.btn-icon:hover {
    opacity: 1;
    background: color-mix(in srgb, var(--danger) 10%, transparent);
    color: var(--danger);
}
</style>
