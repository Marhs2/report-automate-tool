<script setup>
import { computed, ref, onMounted, nextTick } from "vue";
import { Trash2, X, ChevronDown } from "lucide-vue-next";
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

const suggestionLabel = (item, doneLabel, busyLabel, idleLabel) => {
    if (appliedNames.value.has(item.projectName)) return doneLabel;
    if (applyingName.value === item.projectName) return busyLabel;
    return idleLabel;
};

const suggestionLocked = (item) =>
    applyingName.value === item.projectName || appliedNames.value.has(item.projectName);

onMounted(() => {
    fetchProjectNames();
});
</script>

<template>
    <div :class="embedded ? 'projects-pane' : 'page'">
        <section class="card board" aria-labelledby="project-board-title">
            <header class="board-head">
                <h2 id="project-board-title" class="board-title">등록된 프로젝트</h2>
                <button
                    type="button"
                    class="btn btn-small"
                    :aria-expanded="showAdd"
                    aria-controls="project-add-form"
                    @click="toggleAdd"
                >
                    {{ showAdd ? "취소" : "프로젝트 추가" }}
                </button>
            </header>

            <form
                v-if="showAdd"
                id="project-add-form"
                class="add-form"
                @submit.prevent="addProjectName"
            >
                <div class="field">
                    <label for="name-input">프로젝트 명</label>
                    <input
                        id="name-input"
                        ref="nameInput"
                        v-model="newName"
                        type="text"
                        class="input"
                        placeholder="예: 일일보고 취합"
                    />
                </div>
                <div class="field">
                    <label for="keywords-input">키워드</label>
                    <input
                        id="keywords-input"
                        v-model="newKeywords"
                        type="text"
                        class="input"
                        placeholder="쉼표로 구분"
                    />
                </div>
                <button class="btn btn-primary add-submit" type="submit">등록</button>
            </form>

            <!-- 설정과 실제 보고가 따로 놀지 않게, 보고서에만 있는 이름을 바로 등록한다.
                 등록 목록을 못 불러왔으면 모든 이름이 미등록처럼 보여 중복 등록을 부르므로 숨긴다. -->
            <div v-if="unregisteredNames.length && !loadError" class="unregistered">
                <p class="unregistered-title">
                    보고서에는 있는데 등록되지 않은 프로젝트
                    <strong>{{ unregisteredNames.length }}개</strong>
                </p>
                <div class="unregistered-actions">
                    <button
                        v-for="name in unregisteredNames"
                        :key="name"
                        type="button"
                        class="btn btn-small"
                        :disabled="registeringName === name"
                        @click="registerUsedName(name)"
                    >
                        {{ name }} 등록
                    </button>
                    <button
                        v-if="unregisteredNames.length > 1"
                        type="button"
                        class="btn btn-small"
                        :disabled="Boolean(registeringName)"
                        @click="registerAllUsedNames"
                    >
                        전부 등록
                    </button>
                </div>
            </div>

            <div v-if="isLoading" aria-busy="true">
                <div v-for="n in 5" :key="n" class="skeleton-row" aria-hidden="true">
                    <span class="skeleton is-name"></span>
                    <span class="skeleton is-chip"></span>
                    <span class="skeleton is-chip"></span>
                </div>
                <span class="sr-only">프로젝트 명을 불러오는 중</span>
            </div>
            <div v-else-if="loadError" class="board-state is-error" role="alert">
                <p>{{ loadError }}</p>
                <button type="button" class="btn btn-small" @click="fetchProjectNames">다시 시도</button>
            </div>
            <p v-else-if="projectNames.length === 0 && !showAdd" class="board-state">
                등록된 프로젝트 명이 없습니다
            </p>
            <ul v-else-if="projectNames.length" class="project-rows">
                <li
                    v-for="item in projectNames"
                    :key="item.name"
                    class="project-row"
                    :class="{ 'is-editing': editingName === item.name }"
                >
                    <div class="project-head">
                        <button
                            type="button"
                            class="project-open"
                            :aria-expanded="editingName === item.name"
                            @click="toggleRow(item)"
                        >
                            <span class="project-name">{{ item.name }}</span>
                            <span v-if="editingName !== item.name" class="keyword-chips">
                                <span
                                    v-for="keyword in previewKeywords(item.keywords)"
                                    :key="keyword"
                                    class="chip"
                                >
                                    {{ keyword }}
                                </span>
                                <span v-if="extraKeywordCount(item.keywords)" class="chip is-muted">
                                    +{{ extraKeywordCount(item.keywords) }}
                                </span>
                                <span v-if="!keywordList(item.keywords).length" class="keyword-none">
                                    키워드 없음
                                </span>
                            </span>
                        </button>
                        <button
                            type="button"
                            class="icon-btn project-delete"
                            title="삭제"
                            :aria-label="`${item.name} 삭제`"
                            @click.stop="removeProjectName(item.name)"
                        >
                            <Trash2 :size="16" />
                        </button>
                    </div>

                    <div v-if="editingName === item.name" class="project-edit" @click.stop>
                        <div class="keyword-chips">
                            <span v-for="keyword in editingChips" :key="keyword" class="chip keyword-token">
                                {{ keyword }}
                                <button
                                    type="button"
                                    class="token-remove"
                                    :aria-label="`${keyword} 삭제`"
                                    @click="removeEditingChip(keyword)"
                                >
                                    <X :size="14" />
                                </button>
                            </span>
                            <span v-if="!editingChips.length" class="keyword-none">키워드 없음</span>
                        </div>
                        <div class="project-edit-bar">
                            <input
                                v-model="chipDraft"
                                type="text"
                                class="input token-input"
                                placeholder="키워드 추가 후 Enter"
                                :aria-label="`${item.name} 키워드 추가`"
                                @keydown.enter.prevent="addEditingChip"
                            />
                            <div class="edit-actions">
                                <button
                                    type="button"
                                    class="btn btn-primary btn-small"
                                    :disabled="savingName === item.name"
                                    @click="saveKeywords(item)"
                                >
                                    {{ savingName === item.name ? "저장 중..." : "저장" }}
                                </button>
                                <button type="button" class="btn btn-small" @click="cancelEdit">취소</button>
                            </div>
                        </div>
                    </div>
                </li>
            </ul>
        </section>

        <section class="card board recommend">
            <h2 class="recommend-heading">
                <button
                    type="button"
                    class="recommend-toggle"
                    :aria-expanded="recommendOpen"
                    aria-controls="recommend-body"
                    @click="recommendOpen = !recommendOpen"
                >
                    <span>키워드 추출</span>
                    <ChevronDown :size="18" class="recommend-chevron" :class="{ 'is-open': recommendOpen }" />
                </button>
            </h2>

            <div v-if="recommendOpen" id="recommend-body" class="recommend-body">
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
                <div class="recommend-actions">
                    <p v-if="recommendError" class="recommend-error" role="alert">
                        {{ recommendError }}
                    </p>
                    <button
                        type="button"
                        class="btn"
                        :disabled="isRecommending"
                        @click="requestRecommendation"
                    >
                        {{ isRecommending ? "분석 중..." : "추천 받기" }}
                    </button>
                </div>

                <p v-if="recommendation && !hasRecommendation" class="suggest-empty">
                    원문에서 근거를 찾지 못했습니다. 프로젝트명이 드러나는 문장을 포함해보세요.
                </p>

                <div v-if="recommendation?.keywordAdditions?.length" class="suggest-group">
                    <h3 class="suggest-title">기존 프로젝트에 키워드 추가</h3>
                    <ul class="suggest-rows">
                        <li
                            v-for="item in recommendation.keywordAdditions"
                            :key="item.projectName"
                            class="suggest-row"
                        >
                            <div class="suggest-head">
                                <span class="suggest-name">{{ item.projectName }}</span>
                                <button
                                    type="button"
                                    class="btn btn-small"
                                    :disabled="suggestionLocked(item)"
                                    @click="applyKeywordAddition(item)"
                                >
                                    {{ suggestionLabel(item, "반영됨", "반영 중...", "반영") }}
                                </button>
                            </div>
                            <div class="keyword-chips">
                                <span v-for="keyword in item.suggestedKeywords" :key="keyword" class="chip">
                                    {{ keyword }}
                                </span>
                            </div>
                            <p class="suggest-reason">{{ item.reason }}</p>
                        </li>
                    </ul>
                </div>

                <div v-if="recommendation?.newProjects?.length" class="suggest-group">
                    <h3 class="suggest-title">신규 프로젝트 후보</h3>
                    <ul class="suggest-rows">
                        <li
                            v-for="item in recommendation.newProjects"
                            :key="item.projectName"
                            class="suggest-row"
                        >
                            <div class="suggest-head">
                                <span class="suggest-name">{{ item.projectName }}</span>
                                <button
                                    type="button"
                                    class="btn btn-small"
                                    :disabled="suggestionLocked(item)"
                                    @click="applyNewProject(item)"
                                >
                                    {{ suggestionLabel(item, "등록됨", "등록 중...", "등록") }}
                                </button>
                            </div>
                            <div class="keyword-chips">
                                <span v-for="keyword in item.suggestedKeywords" :key="keyword" class="chip">
                                    {{ keyword }}
                                </span>
                                <span v-if="!(item.suggestedKeywords || []).length" class="keyword-none">
                                    키워드 없음
                                </span>
                            </div>
                            <p class="suggest-reason">{{ item.reason }}</p>
                        </li>
                    </ul>
                </div>
            </div>
        </section>
    </div>
</template>

<style scoped src="../styles/components/project-name.css"></style>
