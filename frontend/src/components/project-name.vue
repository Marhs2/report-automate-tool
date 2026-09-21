<script setup>
import { computed, ref, onMounted, nextTick } from "vue";
import { Trash2, Check, Sparkles, Plus, X, ChevronDown } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";

const {
    getProjectNames,
    getRegisteredProjectNames,
    postProjectName,
    deleteProjectName,
    updateProjectNameKeywords,
    recommendKeywords,
} = useApi();
const { alert: showAlert, confirm: askConfirm } = useDialog();

defineProps({
    embedded: { type: Boolean, default: false },
});

const projectNames = ref([]);
const usedNames = ref([]);
const loadError = ref("");
const registeringName = ref("");
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
    loadError.value = "";
    try {
        projectNames.value = await getRegisteredProjectNames();
    } catch (error) {
        console.error("프로젝트 명 조회 실패:", error);
        projectNames.value = [];
        // 조용히 비우면 "0개 등록"으로 보여서 설정이 비어 있는 줄 안다.
        loadError.value =
            "프로젝트 명을 불러오지 못했습니다. 백엔드가 켜져 있는지 확인해주세요.";
    } finally {
        isLoading.value = false;
    }
    try {
        usedNames.value = await getProjectNames();
    } catch (error) {
        console.error("보고서 프로젝트 조회 실패:", error);
        usedNames.value = [];
    }
};

/** 보고서에는 나오는데 설정에 없는 이름.
 *  목록 필터에는 있는 프로젝트가 설정에는 0개인 상태를 그대로 두지 않는다. */
const unregisteredNames = computed(() => {
    const registered = new Set(
        projectNames.value.map((item) => String(item.name || "").trim()),
    );
    return usedNames.value
        .map((name) => String(name || "").trim())
        .filter((name) => name && !registered.has(name));
});

const registerUsedName = async (name) => {
    registeringName.value = name;
    try {
        await postProjectName(name, "");
        await fetchProjectNames();
    } catch (error) {
        const detail = error.response?.data?.detail;
        showAlert(detail || "프로젝트 명 등록에 실패했습니다.");
    } finally {
        registeringName.value = "";
    }
};

const registerAllUsedNames = async () => {
    for (const name of [...unregisteredNames.value]) {
        await registerUsedName(name);
    }
};

const addProjectName = async () => {
    const name = newName.value.trim();
    if (!name) {
        showAlert("프로젝트 명을 입력해주세요.");
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
        showAlert(detail || "프로젝트 명 등록에 실패했습니다.");
    }
};

const removeProjectName = async (name) => {
    if (await askConfirm(`'${name}' 프로젝트 명을 삭제하시겠습니까?`)) {
        try {
            await deleteProjectName(name);
            await fetchProjectNames();
        } catch (error) {
            const detail = error.response?.data?.detail;
            showAlert(detail || "삭제에 실패했습니다.");
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
        showAlert(`'${item.name}' 키워드가 저장되었습니다.`);
    } catch (error) {
        const detail = error.response?.data?.detail;
        showAlert(detail || "키워드 저장에 실패했습니다.");
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
        showAlert(`'${item.projectName}'은 등록된 프로젝트가 아닙니다.`);
        return;
    }
    applyingName.value = item.projectName;
    try {
        const keywords = mergeKeywords(target.keywords, item.suggestedKeywords);
        await updateProjectNameKeywords(item.projectName, keywords);
        target.keywords = keywords;
        markApplied(item.projectName);
        showAlert(`'${item.projectName}' 키워드를 반영했습니다.`);
    } catch (error) {
        const detail = error.response?.data?.detail;
        showAlert(detail || "키워드 반영에 실패했습니다.");
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
        showAlert(`'${item.projectName}' 프로젝트를 등록했습니다.`);
    } catch (error) {
        const detail = error.response?.data?.detail;
        showAlert(detail || "프로젝트 등록에 실패했습니다.");
    } finally {
        applyingName.value = "";
    }
};

onMounted(() => {
    fetchProjectNames();
});
</script>

<template>
    <div :class="embedded ? 'settings-pane' : 'page'">
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

            <p v-if="loadError" class="error-text" role="alert">{{ loadError }}</p>

            <!-- 설정과 실제 보고가 따로 놀지 않게, 보고서에만 있는 이름을 바로 등록한다. -->
            <div v-if="unregisteredNames.length" class="unregistered">
                <p class="unregistered-copy">
                    보고서에는 있는데 등록되지 않은 프로젝트 {{ unregisteredNames.length }}개
                </p>
                <div class="unregistered-chips">
                    <button
                        v-for="name in unregisteredNames"
                        :key="name"
                        type="button"
                        class="btn btn-small"
                        :disabled="registeringName === name"
                        @click="registerUsedName(name)"
                    >
                        <Plus :size="13" />
                        {{ name }}
                    </button>
                    <button
                        v-if="unregisteredNames.length > 1"
                        type="button"
                        class="btn btn-primary btn-small"
                        :disabled="Boolean(registeringName)"
                        @click="registerAllUsedNames"
                    >
                        전부 등록
                    </button>
                </div>
            </div>

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
                                type="button"
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
                                    class="chip is-accent"
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
.settings-pane {
    min-width: 0;
}

/* .count-chip, .chip 기본 모양은 components.css 전역 규칙을 쓴다.
   전역 .chip은 중립색이므로 액센트가 필요한 키워드 칩은 템플릿에서 `chip is-accent`를 붙인다. */
.section-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
}

.section-title {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
}

.section-head h2 {
    margin: 0;
}

.list-section {
    margin-bottom: var(--space-6);
}

.unregistered {
    margin-bottom: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--warning-border);
    border-radius: var(--radius);
    background: var(--warning-bg);
}

.unregistered-copy {
    margin: 0 0 var(--space-2);
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--warning-fg);
    word-break: keep-all;
}

.unregistered-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
}

.list-section h2 {
    color: var(--text-strong);
}

.add-form {
    display: flex;
    align-items: flex-end;
    gap: var(--space-3);
    flex-wrap: wrap;
    margin-bottom: var(--space-3);
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
    background: var(--surface);
    overflow: hidden;
}

.project-row {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--border);
}

.project-row:last-child {
    border-bottom: none;
}

.project-row.editing {
    background: var(--accent-soft);
}

.project-row-head {
    display: grid;
    grid-template-columns: minmax(140px, 220px) 1fr auto;
    align-items: center;
    gap: var(--space-3);
    cursor: pointer;
}

.project-name {
    margin: 0;
    font-size: 15px;
    font-weight: var(--fw-bold);
    color: var(--text-strong);
    line-height: 1.3;
    word-break: keep-all;
}

.project-row-edit {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding-left: 0;
}

.keyword-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    min-width: 0;
}

/* 키워드는 길 수 있으므로 전역 .chip의 nowrap 대신 줄바꿈을 허용한다. */
.chip {
    max-width: 100%;
    white-space: normal;
    word-break: break-word;
}

.chip-new {
    background: var(--warning-bg);
    color: var(--warning-fg);
}

.chip-muted {
    color: var(--text-strong);
}

.chip-edit {
    border: 1px solid var(--border);
    padding-right: var(--space-1);
    background: var(--accent-soft);
    color: var(--text-strong);
}

.chip-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    padding: 0;
    border: none;
    border-radius: var(--radius-pill);
    background: transparent;
    color: var(--text);
    cursor: pointer;
}

.chip-remove:hover {
    background: var(--danger-bg);
    color: var(--danger-fg);
}

.chip-empty {
    font-size: var(--fs-12);
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
    gap: var(--space-2);
}

.btn-icon {
    padding: var(--space-2);
    border: none;
    background: none;
    color: var(--text);
    opacity: 0.65;
    cursor: pointer;
    border-radius: var(--radius-pill);
}

.btn-icon:hover {
    opacity: 1;
    background: var(--accent-soft);
    color: var(--accent);
    border-color: transparent;
}

.btn-icon.danger:hover {
    background: var(--danger-bg);
    color: var(--danger-fg);
}

.recommend-card {
    padding: 0;
}

.recommend-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: var(--space-3) var(--space-4);
    border: none;
    background: none;
    color: var(--text-strong);
    font: inherit;
    font-size: 15px;
    font-weight: var(--fw-semibold);
    cursor: pointer;
    text-align: left;
}

.recommend-toggle-copy {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
}

.recommend-chevron {
    color: var(--text);
    transition: transform var(--dur-fast) var(--ease);
}

.recommend-chevron.open {
    transform: rotate(180deg);
}

.recommend-body {
    padding: 0 var(--space-4) var(--space-4);
}

.recommend-grid {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
}

.recommend-side {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-3);
}

.error-text {
    margin: 0;
    color: var(--danger-fg);
    font-size: var(--fs-13);
}

.empty-suggest,
.suggest-block {
    margin-top: var(--space-4);
    padding-top: var(--space-4);
    border-top: 1px solid var(--border);
}

.empty-suggest {
    font-size: var(--fs-13);
    color: var(--text);
}

.suggest-title {
    margin: 0 0 var(--space-2);
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.suggest-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: var(--space-3);
    align-items: start;
}

.suggest-card {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    min-width: 0;
}

.suggest-card.is-new {
    border-color: var(--warning-border);
}

.suggest-card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-2);
}

.suggest-card-head h4 {
    margin: 0;
    font-size: 15px;
    font-weight: var(--fw-bold);
    color: var(--text-strong);
    line-height: 1.3;
    word-break: keep-all;
}

.suggest-reason {
    margin: 0;
    font-size: var(--fs-12);
    color: var(--text);
    line-height: var(--lh-base);
}

@media (max-width: 860px) {
    .section-head {
        flex-wrap: wrap;
        gap: 10px;
    }

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
