<script setup>
import { computed, ref, onMounted } from "vue";
import useAPI from "../composables/useApi";
import { Trash2, Check, Pencil } from "lucide-vue-next";

const {
    getRegisteredProjectNames,
    postProjectName,
    deleteProjectName,
    updateProjectNameKeywords,
    recommendKeywords,
} = useAPI();

const projectNames = ref([]);
const newName = ref("");
const newKeywords = ref("");
const isLoading = ref(false);

const editingName = ref("");
const editingKeywords = ref("");
const savingName = ref("");

const sourceText = ref("");
const isRecommending = ref(false);
const recommendError = ref("");
const recommendation = ref(null);
const applyingName = ref("");
const appliedNames = ref(new Set());

const hasRecommendation = computed(() => {
    const data = recommendation.value;
    if (!data) return false;
    return (
        (data.keywordAdditions && data.keywordAdditions.length > 0) ||
        (data.newProjects && data.newProjects.length > 0)
    );
});

const unwrapKeywords = (payload) => {
    let data = payload?.keywords ?? payload;
    if (typeof data === "string") {
        try {
            data = JSON.parse(data);
        } catch {
            data = null;
        }
    }
    return {
        keywordAdditions: data?.keywordAdditions || [],
        newProjects: data?.newProjects || [],
    };
};

const mergeKeywords = (current, extra) => {
    const merged = [];
    const seen = new Set();
    for (const value of [...String(current || "").split(/[,，|/]/), ...(extra || [])]) {
        const text = String(value || "").trim();
        const key = text.toLowerCase();
        if (!text || seen.has(key)) continue;
        seen.add(key);
        merged.push(text);
    }
    return merged.join(", ");
};

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

const requestRecommendation = async () => {
    const report = sourceText.value.trim();
    if (!report) {
        recommendError.value = "원문을 입력해주세요.";
        return;
    }
    recommendError.value = "";
    isRecommending.value = true;
    recommendation.value = null;
    appliedNames.value = new Set();
    try {
        recommendation.value = unwrapKeywords(await recommendKeywords(report));
    } catch (error) {
        recommendError.value =
            error.response?.data?.detail || "키워드 추천에 실패했습니다.";
    } finally {
        isRecommending.value = false;
    }
};

const markApplied = (name) => {
    const next = new Set(appliedNames.value);
    next.add(name);
    appliedNames.value = next;
};

const applyKeywordAddition = async (item) => {
    const target = projectNames.value.find((row) => row.name === item.projectName);
    if (!target) {
        alert(`'${item.projectName}'은 등록된 프로젝트가 아닙니다.`);
        return;
    }
    applyingName.value = item.projectName;
    try {
        const keywords = mergeKeywords(target.keywords, item.suggestedKeywords);
        await updateProjectNameKeywords(item.projectName, keywords);
        target.keywords = keywords;
        markApplied(item.projectName);
        alert(`'${item.projectName}' 키워드를 반영했습니다.`);
    } catch (error) {
        const detail = error.response?.data?.detail;
        alert(detail || "키워드 반영에 실패했습니다.");
    } finally {
        applyingName.value = "";
    }
};

const applyNewProject = async (item) => {
    applyingName.value = item.projectName;
    try {
        await postProjectName(
            item.projectName,
            (item.suggestedKeywords || []).join(", "),
        );
        markApplied(item.projectName);
        await fetchProjectNames();
        alert(`'${item.projectName}' 프로젝트를 등록했습니다.`);
    } catch (error) {
        const detail = error.response?.data?.detail;
        alert(detail || "프로젝트 등록에 실패했습니다.");
    } finally {
        applyingName.value = "";
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
                    구분하는 데 사용됩니다. 키워드는 원문에 화면·기능명만
                    적혀 있을 때 프로젝트를 찾는 데 도움을 줍니다
                </p>
            </div>
        </div>

        <div class="card">
            <h2>원문으로 키워드 추천받기</h2>
            <p class="card-hint">
                보고서를 넣으면 기존 프로젝트 키워드와 새 프로젝트 후보를
                골라 줍니다. 반영·등록을 눌러야 저장됩니다.
            </p>
            <div class="field">
                <label for="source-text">원문</label>
                <textarea
                    id="source-text"
                    v-model="sourceText"
                    class="textarea"
                    rows="10"
                    placeholder="보고서 원문을 붙여넣으세요"
                ></textarea>
            </div>
            <p v-if="recommendError" class="error-text">{{ recommendError }}</p>
            <div class="recommend-actions">
                <button
                    class="btn btn-primary"
                    :disabled="isRecommending"
                    @click="requestRecommendation"
                >
                    {{ isRecommending ? "분석 중..." : "추천 받기" }}
                </button>
            </div>
        </div>

        <div v-if="recommendation && !hasRecommendation" class="card">
            <h2>추천 결과</h2>
            <p class="card-hint">
                원문에서 근거를 찾지 못했습니다. 프로젝트명이 드러나는 문장을
                포함해보세요.
            </p>
        </div>

        <div
            v-if="recommendation?.keywordAdditions?.length"
            class="card"
        >
            <h2>기존 프로젝트에 키워드 추가</h2>
            <ul class="suggest-list">
                <li
                    v-for="item in recommendation.keywordAdditions"
                    :key="item.projectName"
                    class="suggest-item"
                >
                    <div class="suggest-body">
                        <h3>{{ item.projectName }}</h3>
                        <div class="keyword-chips">
                            <span
                                v-for="keyword in item.suggestedKeywords"
                                :key="keyword"
                                class="chip"
                            >
                                {{ keyword }}
                            </span>
                        </div>
                        <p class="suggest-reason">{{ item.reason }}</p>
                    </div>
                    <button
                        class="btn btn-primary btn-small"
                        :disabled="
                            applyingName === item.projectName ||
                            appliedNames.has(item.projectName)
                        "
                        @click="applyKeywordAddition(item)"
                    >
                        {{
                            appliedNames.has(item.projectName)
                                ? "반영됨"
                                : applyingName === item.projectName
                                  ? "반영 중..."
                                  : "반영"
                        }}
                    </button>
                </li>
            </ul>
        </div>

        <div v-if="recommendation?.newProjects?.length" class="card">
            <h2>신규 프로젝트 후보</h2>
            <ul class="suggest-list">
                <li
                    v-for="item in recommendation.newProjects"
                    :key="item.projectName"
                    class="suggest-item"
                >
                    <div class="suggest-body">
                        <h3>{{ item.projectName }}</h3>
                        <div class="keyword-chips">
                            <span
                                v-for="keyword in item.suggestedKeywords"
                                :key="keyword"
                                class="chip chip-new"
                            >
                                {{ keyword }}
                            </span>
                            <span
                                v-if="!(item.suggestedKeywords || []).length"
                                class="chip-empty"
                            >
                                키워드 없음
                            </span>
                        </div>
                        <p class="suggest-reason">{{ item.reason }}</p>
                    </div>
                    <button
                        class="btn btn-primary btn-small"
                        :disabled="
                            applyingName === item.projectName ||
                            appliedNames.has(item.projectName)
                        "
                        @click="applyNewProject(item)"
                    >
                        {{
                            appliedNames.has(item.projectName)
                                ? "등록됨"
                                : applyingName === item.projectName
                                  ? "등록 중..."
                                  : "등록"
                        }}
                    </button>
                </li>
            </ul>
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
.card + .card {
    margin-top: 16px;
}

.card h2 {
    display: block;
    margin: 0 0 8px;
}

.card-hint {
    display: block;
    font-size: 13px;
    color: var(--text);
    margin: 0 0 14px;
    line-height: 1.5;
}

.recommend-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 12px;
}

.error-text {
    margin-top: 8px;
    color: var(--danger);
    font-size: 13px;
}

.suggest-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.suggest-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 0;
    border-bottom: 1px solid var(--border);
}

.suggest-item:last-child {
    border-bottom: none;
    padding-bottom: 0;
}

.suggest-body {
    min-width: 0;
    flex: 1;
}

.suggest-body h3 {
    margin-bottom: 8px;
}

.keyword-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 8px;
}

.chip {
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    border-radius: 999px;
    background: var(--accent-bg);
    color: var(--accent);
    font-size: 12px;
    font-weight: 600;
}

.chip-new {
    background: color-mix(in srgb, var(--warning) 16%, transparent);
    color: var(--warning);
}

.chip-empty {
    font-size: 12px;
    color: var(--text);
}

.suggest-reason {
    font-size: 13px;
    color: var(--text);
}

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

.name-table tbody tr {
    transition: background 0.15s;
}

.name-table tbody tr:hover {
    background: var(--bg-soft);
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
    background: var(--accent-bg);
    color: var(--accent);
    border-color: transparent;
}

.action-cell .btn-icon:hover {
    background: var(--danger-bg);
    color: var(--danger);
}
</style>
