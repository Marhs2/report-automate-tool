<script setup>
import { ref, onMounted } from "vue";
import useAPI from "../composables/useApi";
import { Trash2, Check, Pencil } from "lucide-vue-next";

const {
    getRegisteredProjectNames,
    postProjectName,
    deleteProjectName,
    updateProjectNameKeywords,
} = useAPI();

const projectNames = ref([]);
const newName = ref("");
const newKeywords = ref("");
const isLoading = ref(false);

// 편집 중인 행 (name) 과 입력 값
const editingName = ref("");
const editingKeywords = ref("");
const savingName = ref("");

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
        await postProjectName(name, newKeywords.value.trim());
        newName.value = "";
        newKeywords.value = "";
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

const startEdit = (item) => {
    editingName.value = item.name;
    editingKeywords.value = item.keywords || "";
};

const saveKeywords = async (item) => {
    savingName.value = item.name;
    try {
        await updateProjectNameKeywords(item.name, editingKeywords.value);
        item.keywords = editingKeywords.value.trim();
        editingName.value = "";
        alert(`'${item.name}' 키워드가 저장되었습니다.`);
    } catch (error) {
        const detail = error.response?.data?.detail;
        alert(detail || "키워드 저장에 실패했습니다.");
    } finally {
        savingName.value = "";
    }
};

const cancelEdit = () => {
    editingName.value = "";
    editingKeywords.value = "";
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
                    구분하는 데 사용됩니다. 키워드는 원문에 화면·기능명만
                    적혀 있을 때 프로젝트를 찾는 데 도움을 줍니다
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
                        placeholder="예: 일일보고 취합·주간보고 자동화 도구"
                        @keyup.enter="addProjectName"
                    />
                </div>
                <div class="field">
                    <label for="keywords-input"
                        >키워드 (쉼표로 구분, 선택)</label
                    >
                    <input
                        id="keywords-input"
                        type="text"
                        v-model="newKeywords"
                        class="input"
                        placeholder="예: 보고서, 취합, 주간보고"
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
                        <th>키워드</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="item in projectNames" :key="item.name">
                        <td class="name-cell">{{ item.name }}</td>
                        <td class="keywords-cell">
                            <template v-if="editingName === item.name">
                                <input
                                    type="text"
                                    v-model="editingKeywords"
                                    class="input keywords-input"
                                    placeholder="쉼표로 구분 (예: 보고서, 취합)"
                                    @keyup.enter="saveKeywords(item)"
                                />
                                <button
                                    class="btn btn-icon"
                                    @click="saveKeywords(item)"
                                    :disabled="savingName === item.name"
                                    title="저장"
                                >
                                    <Check :size="14" />
                                </button>
                                <button
                                    class="btn btn-icon"
                                    @click="cancelEdit"
                                    title="취소"
                                >
                                    <span class="cancel-text">취소</span>
                                </button>
                            </template>
                            <template v-else>
                                <span class="keywords-text">{{
                                    item.keywords || "—"
                                }}</span>
                                <button
                                    class="btn btn-icon"
                                    @click="startEdit(item)"
                                    title="키워드 수정"
                                >
                                    <Pencil :size="14" />
                                </button>
                            </template>
                        </td>
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
    white-space: nowrap;
}

.keywords-cell {
    min-width: 260px;
}

.keywords-text {
    color: var(--text);
    margin-right: 8px;
}

.keywords-input {
    max-width: 260px;
    margin-right: 6px;
}

.cancel-text {
    font-size: 12px;
    color: var(--text);
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
