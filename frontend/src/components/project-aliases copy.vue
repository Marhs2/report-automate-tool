<script setup>
import { ref, onMounted } from "vue";
import useAPI from "../composables/useApi";
import { Trash2 } from "lucide-vue-next";

const { getProjectAliases, postProjectAlias, deleteProjectAlias } = useAPI();

const aliases = ref([]);
const newAlias = ref("");
const newCanonical = ref("");
const isLoading = ref(false);

const fetchAliases = async () => {
    isLoading.value = true;
    try {
        aliases.value = await getProjectAliases();
    } catch (error) {
        console.error("별칭 조회 실패:", error);
    } finally {
        isLoading.value = false;
    }
};

const addAlias = async () => {
    const alias = newAlias.value.trim();
    const canonical = newCanonical.value.trim();
    if (!alias || !canonical) {
        alert("별칭과 대표 이름을 모두 입력해주세요.");
        return;
    }
    if (alias === canonical) {
        alert("별칭과 대표 이름이 같습니다.");
        return;
    }
    try {
        await postProjectAlias(alias, canonical);
        newAlias.value = "";
        newCanonical.value = "";
        await fetchAliases();
    } catch (error) {
        const detail = error.response?.data?.detail;
        alert(detail || "별칭 등록에 실패했습니다.");
    }
};

const removeAlias = async (id) => {
    if (!confirm("이 별칭을 삭제하시겠습니까?")) return;
    try {
        await deleteProjectAlias(id);
        await fetchAliases();
    } catch (error) {
        alert("삭제에 실패했습니다.");
    }
};

onMounted(() => {
    fetchAliases();
});
</script>

<template>
    <div class="page">
        <div class="page-header">
            <div>
                <h1>프로젝트 별칭 관리</h1>
                <p class="page-subtitle">
                    표기가 다른 프로젝트명을 같은 프로젝트로 묶습니다. 등록된
                    별칭은 보고서 저장·주간보고 생성 시 자동 적용됩니다.
                </p>
            </div>
        </div>

        <div class="card">
            <h2>새 별칭 등록</h2>
            <div class="add-form">
                <div class="field">
                    <label for="alias-input">별칭 (변환할 이름)</label>
                    <input
                        id="alias-input"
                        type="text"
                        v-model="newAlias"
                        class="input"
                        placeholder="예: A사 MES 구축"
                    />
                </div>
                <span class="arrow">→</span>
                <div class="field">
                    <label for="canonical-input">대표 이름 (통일할 이름)</label>
                    <input
                        id="canonical-input"
                        type="text"
                        v-model="newCanonical"
                        class="input"
                        placeholder="예: A사 MES"
                    />
                </div>
                <button class="btn btn-primary add-btn" @click="addAlias">
                    추가
                </button>
            </div>
        </div>

        <div class="card">
            <h2>등록된 별칭 목록</h2>
            <div v-if="isLoading" class="empty-state">불러오는 중...</div>
            <div v-else-if="aliases.length === 0" class="empty-state">
                등록된 별칭이 없습니다
            </div>
            <table v-else class="alias-table">
                <thead>
                    <tr>
                        <th>별칭</th>
                        <th></th>
                        <th>대표 이름</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="alias in aliases" :key="alias.id">
                        <td class="alias-name">{{ alias.alias_name }}</td>
                        <td class="arrow-cell">→</td>
                        <td class="canonical-name">
                            {{ alias.canonical_name }}
                        </td>
                        <td class="action-cell">
                            <button
                                class="btn btn-icon"
                                @click="removeAlias(alias.id)"
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
    min-width: 180px;
}

.add-form .arrow {
    font-size: 20px;
    font-weight: 700;
    color: var(--text);
    padding-bottom: 8px;
}

.add-btn {
    flex-shrink: 0;
    margin-bottom: 0;
}

.alias-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}

.alias-table th {
    text-align: left;
    padding: 10px 12px;
    border-bottom: 2px solid var(--border);
    color: var(--text);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

.alias-table td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
}

.alias-table tr:last-child td {
    border-bottom: none;
}

.alias-name {
    font-weight: 600;
    color: var(--text-h);
}

.arrow-cell {
    width: 30px;
    text-align: center;
    font-weight: 700;
    color: var(--text);
    opacity: 0.5;
}

.canonical-name {
    color: var(--accent);
    font-weight: 600;
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
    transition: opacity 0.15s, background 0.15s;
}

.btn-icon:hover {
    opacity: 1;
    background: color-mix(in srgb, var(--danger) 10%, transparent);
    color: var(--danger);
}
</style>
