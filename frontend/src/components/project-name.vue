<script setup>
import { computed, ref, onMounted, nextTick } from "vue";
import { Trash2, Check, Sparkles, Plus, X, ChevronDown } from "lucide-vue-next";
import useApi from "../composables/useApi";

const {
    getRegisteredProjectNames,
    postProjectName,
    deleteProjectName,
    updateProjectNameKeywords,
    recommendKeywords,
} = useApi();

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
const showAdd = ref(false);
const recommendOpen = ref(false);
const chipDraft = ref("");
const nameInput = ref(null);
const KEYWORD_PREVIEW = 3;

const hasRecommendation = computed(() => {
    const data = recommendation.value;
    if (!data) return false;
    return (
        (data.keywordAdditions && data.keywordAdditions.length > 0) ||
        (data.newProjects && data.newProjects.length > 0)
    );
});

const keywordList = (value) =>
    String(value || "")
        .split(/[,，|/]/)
        .map((text) => text.trim())
        .filter(Boolean);

const previewKeywords = (value) => keywordList(value).slice(0, KEYWORD_PREVIEW);
const extraKeywordCount = (value) =>
    Math.max(0, keywordList(value).length - KEYWORD_PREVIEW);
const editingChips = computed(() => keywordList(editingKeywords.value));

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
        showAdd.value = false;
        await fetchProjectNames();
    } catch (error) {
        const detail = error.response?.data?.detail;
        alert(detail || "프로젝트 명 등록에 실패했습니다.");
    }
};

const removeProjectName = async (name) => {
    if (confirm(`'${name}' 프로젝트 명을 삭제하시겠습니까?`)) {
        try {
            await deleteProjectName(name);
            await fetchProjectNames();
        } catch (error) {
            const detail = error.response?.data?.detail;
            alert(detail || "삭제에 실패했습니다.");
        }
    }
    if (editingName.value === name) cancelEdit();
};

const startEdit = (item) => {
    editingName.value = item.name;
    editingKeywords.value = item.keywords || "";
    chipDraft.value = "";
};

const toggleRow = (item) => {
    if (editingName.value === item.name) return;
    startEdit(item);
};

const toggleAdd = async () => {
    showAdd.value = !showAdd.value;
    if (!showAdd.value) return;
    await nextTick();
    nameInput.value?.focus();
};

const removeEditingChip = (keyword) => {
    editingKeywords.value = editingChips.value
        .filter((item) => item !== keyword)
        .join(", ");
};

const addEditingChip = () => {
    const extra = keywordList(chipDraft.value);
    if (!extra.length) return;
    editingKeywords.value = mergeKeywords(editingKeywords.value, extra);
    chipDraft.value = "";
};

const saveKeywords = async (item) => {
    savingName.value = item.name;
    try {
        await updateProjectNameKeywords(item.name, editingKeywords.value);
        item.keywords = editingKeywords.value.trim();
        editingName.value = "";
        chipDraft.value = "";
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
    chipDraft.value = "";
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
    <div class="page names-page">
        <section class="list-section">
            <div class="section-head">
                <div class="section-title">
                    <h2>등록된 프로젝트</h2>
                    <span v-if="!isLoading" class="count-chip">
                        {{ projectNames.length }}개 등록
                    </span>
                </div>
                <button
                    type="button"
                    class="btn btn-primary btn-small"
                    @click="toggleAdd"
                >
                    <Plus v-if="!showAdd" :size="14" />
                    <X v-else :size="14" />
                    {{ showAdd ? "취소" : "프로젝트" }}
                </button>
            </div>

            <form
                v-if="showAdd"
                class="card add-form"
                @submit.prevent="addProjectName"
            >
                <div class="field">
                    <label for="name-input">프로젝트 명</label>
                    <input
                        id="name-input"
                        ref="nameInput"
                        type="text"
                        v-model="newName"
                        class="input"
                        placeholder="예: 일일보고 취합"
                    />
                </div>
                <div class="field">
                    <label for="keywords-input">키워드</label>
                    <input
                        id="keywords-input"
                        type="text"
                        v-model="newKeywords"
                        class="input"
                        placeholder="쉼표로 구분"
                    />
                </div>
                <button class="btn btn-primary add-btn" type="submit">
                    <Plus :size="14" />
                    등록
                </button>
            </form>

            <div v-if="isLoading" class="empty-state">불러오는 중...</div>
            <div
                v-else-if="projectNames.length === 0 && !showAdd"
                class="empty-state"
            >
                등록된 프로젝트 명이 없습니다
            </div>
            <div v-else-if="projectNames.length" class="project-list">
                <article
                    v-for="item in projectNames"
                    :key="item.name"
                    class="project-row"
                    :class="{ editing: editingName === item.name }"
                >
                    <div class="project-row-head" @click="toggleRow(item)">
                        <h3 class="project-name">{{ item.name }}</h3>
                        <div
                            v-if="editingName !== item.name"
                            class="keyword-chips"
                        >
                            <span
                                v-for="keyword in previewKeywords(item.keywords)"
                                :key="keyword"
                                class="chip chip-muted"
                            >
                                {{ keyword }}
                            </span>
                            <span
                                v-if="extraKeywordCount(item.keywords)"
                                class="chip chip-more"
                            >
                                +{{ extraKeywordCount(item.keywords) }}
                            </span>
                            <span
                                v-if="!keywordList(item.keywords).length"
                                class="chip-empty"
                            >
                                키워드 없음
                            </span>
                        </div>
                        <div class="card-actions">
                            <button
                                class="btn btn-icon danger"
                                title="삭제"
                                @click.stop="removeProjectName(item.name)"
                            >
                                <Trash2 :size="14" />
                            </button>
                        </div>
                    </div>

                    <div
                        v-if="editingName === item.name"
                        class="project-row-edit"
                        @click.stop
                    >
                        <div class="keyword-chips">
                            <span
                                v-for="keyword in editingChips"
                                :key="keyword"
                                class="chip chip-edit"
                            >
                                {{ keyword }}
                                <button
                                    type="button"
                                    class="chip-remove"
                                    :aria-label="`${keyword} 삭제`"
                                    @click="removeEditingChip(keyword)"
                                >
                                    <X :size="11" />
                                </button>
                            </span>
                            <span v-if="!editingChips.length" class="chip-empty">
                                키워드 없음
                            </span>
                        </div>
                        <input
                            type="text"
                            v-model="chipDraft"
                            class="input chip-input"
                            placeholder="키워드 추가 후 Enter"
                            @keydown.enter.prevent="addEditingChip"
                        />
                        <div class="edit-actions">
                            <button
                                class="btn btn-primary btn-small"
                                :disabled="savingName === item.name"
                                @click="saveKeywords(item)"
                            >
                                <Check :size="14" />
                                {{ savingName === item.name ? "저장 중..." : "저장" }}
                            </button>
                            <button class="btn btn-small" @click="cancelEdit">
                                <X :size="14" />
                                취소
                            </button>
                        </div>
                    </div>
                </article>
            </div>
        </section>

        <section class="card recommend-card">
            <button
                type="button"
                class="recommend-toggle"
                :aria-expanded="recommendOpen"
                @click="recommendOpen = !recommendOpen"
            >
                <span class="recommend-toggle-copy">
                    키워드 추출
                </span>
                <ChevronDown
                    :size="16"
                    class="recommend-chevron"
                    :class="{ open: recommendOpen }"
                />
            </button>

            <div v-if="recommendOpen" class="recommend-body">
                <div class="recommend-grid">
                    <div class="field">
                        <label for="source-text">원문</label>
                        <textarea
                            id="source-text"
                            v-model="sourceText"
                            class="textarea"
                            rows="5"
                            placeholder="보고서 원문을 붙여넣으세요"
                        ></textarea>
                    </div>
                    <div class="recommend-side">
                        <p v-if="recommendError" class="error-text">
                            {{ recommendError }}
                        </p>
                        <button
                            class="btn btn-primary"
                            :disabled="isRecommending"
                            @click="requestRecommendation"
                        >
                            <Sparkles :size="14" />
                            {{ isRecommending ? "분석 중..." : "추천 받기" }}
                        </button>
                    </div>
                </div>

                <div
                    v-if="recommendation && !hasRecommendation"
                    class="empty-suggest"
                >
                    원문에서 근거를 찾지 못했습니다. 프로젝트명이 드러나는 문장을
                    포함해보세요.
                </div>

                <div
                    v-if="recommendation?.keywordAdditions?.length"
                    class="suggest-block"
                >
                    <h3 class="suggest-title">기존 프로젝트에 키워드 추가</h3>
                    <div class="suggest-grid">
                        <article
                            v-for="item in recommendation.keywordAdditions"
                            :key="item.projectName"
                            class="suggest-card"
                        >
                            <div class="suggest-card-head">
                                <h4>{{ item.projectName }}</h4>
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
                            </div>
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
                        </article>
                    </div>
                </div>

                <div
                    v-if="recommendation?.newProjects?.length"
                    class="suggest-block"
                >
                    <h3 class="suggest-title">신규 프로젝트 후보</h3>
                    <div class="suggest-grid">
                        <article
                            v-for="item in recommendation.newProjects"
                            :key="item.projectName"
                            class="suggest-card is-new"
                        >
                            <div class="suggest-card-head">
                                <h4>{{ item.projectName }}</h4>
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
                            </div>
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
                        </article>
                    </div>
                </div>
            </div>
        </section>
    </div>
</template>

<style scoped>
.names-page {
    max-width: 1120px;
}

.count-chip {
    display: inline-flex;
    align-items: center;
    padding: 5px 10px;
    border-radius: 999px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    color: var(--text-h);
    font-size: 12px;
    font-weight: 650;
}

.section-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
}

.section-title {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
}

.section-head h2 {
    margin: 0;
}

.list-section {
    margin-bottom: 24px;
}

.list-section h2 {
    color: var(--text-h);
}

.add-form {
    display: flex;
    align-items: flex-end;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 14px;
}

.add-form .field {
    flex: 1;
    min-width: 0;
}

.add-btn {
    flex-shrink: 0;
}

.project-list {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--bg-elevated);
    overflow: hidden;
}

.project-row {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
}

.project-row:last-child {
    border-bottom: none;
}

.project-row.editing {
    background: color-mix(in srgb, var(--accent) 7%, var(--bg-elevated));
}

.project-row-head {
    display: grid;
    grid-template-columns: minmax(140px, 220px) 1fr auto;
    align-items: center;
    gap: 12px;
    cursor: pointer;
}

.project-name {
    margin: 0;
    font-size: 15px;
    font-weight: 700;
    color: var(--text-h);
    line-height: 1.3;
    word-break: keep-all;
}

.project-row-edit {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-left: 0;
}

.keyword-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    min-width: 0;
}

.chip {
    display: inline-flex;
    align-items: center;
    max-width: 100%;
    padding: 3px 8px;
    border-radius: 999px;
    background: var(--accent-bg);
    color: var(--accent);
    font-size: 12px;
    font-weight: 600;
    line-height: 1.3;
    word-break: break-word;
}

.chip-new {
    background: color-mix(in srgb, var(--warning) 16%, transparent);
    color: var(--warning);
}

.chip-muted,
.chip-more {
    background: var(--bg-soft);
    color: var(--text-h);
}

.chip-more {
    color: var(--text);
    font-weight: 650;
}

.chip-edit {
    border: 1px solid var(--border);
    padding: 3px 8px;
    padding-right: 4px;
    gap: 4px;
    color: var(--text-h);
}

.chip-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    padding: 0;
    border: none;
    border-radius: 999px;
    background: transparent;
    color: var(--text);
    cursor: pointer;
}

.chip-remove:hover {
    background: var(--danger-bg);
    color: var(--danger);
}

.chip-empty {
    font-size: 12px;
    color: var(--text);
}

.chip-input {
    max-width: 280px;
}

.card-actions {
    display: flex;
    gap: 2px;
    flex-shrink: 0;
}

.edit-actions {
    display: flex;
    gap: 6px;
}

.btn-icon {
    padding: 6px;
    border: none;
    background: none;
    color: var(--text);
    opacity: 0.65;
    cursor: pointer;
    border-radius: var(--radius-sm);
}

.btn-icon:hover {
    opacity: 1;
    background: var(--accent-bg);
    color: var(--accent);
    border-color: transparent;
}

.btn-icon.danger:hover {
    background: var(--danger-bg);
    color: var(--danger);
}

.recommend-card {
    padding: 0;
}

.recommend-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 14px 16px;
    border: none;
    background: none;
    color: var(--text-h);
    font: inherit;
    font-size: 15px;
    font-weight: 650;
    cursor: pointer;
    text-align: left;
}

.recommend-toggle-copy {
    display: inline-flex;
    align-items: center;
    gap: 8px;
}

.recommend-chevron {
    color: var(--text);
    transition: transform 0.15s ease;
}

.recommend-chevron.open {
    transform: rotate(180deg);
}

.recommend-body {
    padding: 0 16px 16px;
}

.recommend-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.recommend-side {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
}

.error-text {
    margin: 0;
    color: var(--danger);
    font-size: 13px;
}

.empty-suggest,
.suggest-block {
    margin-top: 18px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
}

.empty-suggest {
    font-size: 13px;
    color: var(--text);
}

.suggest-title {
    margin: 0 0 10px;
    font-size: 13px;
    font-weight: 650;
    color: var(--text-h);
}

.suggest-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px;
    align-items: start;
}

.suggest-card {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 14px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--bg-elevated);
    min-width: 0;
}

.suggest-card.is-new {
    border-color: color-mix(in srgb, var(--warning) 35%, var(--border));
}

.suggest-card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
}

.suggest-card-head h4 {
    margin: 0;
    font-size: 15px;
    font-weight: 700;
    color: var(--text-h);
    line-height: 1.3;
    word-break: keep-all;
}

.suggest-reason {
    margin: 0;
    font-size: 12px;
    color: var(--text);
    line-height: 1.5;
}

@media (max-width: 860px) {
    .project-row-head {
        grid-template-columns: 1fr auto;
    }

    .project-row-head .keyword-chips {
        grid-column: 1 / -1;
        order: 3;
    }

    .recommend-side {
        justify-content: stretch;
    }

    .recommend-side .btn {
        width: 100%;
    }

    .add-form .field {
        min-width: 100%;
    }

    .chip-input {
        max-width: none;
    }
}
</style>
