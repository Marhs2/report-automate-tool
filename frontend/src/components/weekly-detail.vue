<template>
    <div class="page report-doc is-wide">
        <AppPageHeader :title="userName || '주간 보고서'" :subtitle="reportData?.report_date || '주간 상세'">
            <template #actions>
                <button type="button" class="btn btn-small" @click="goBack">목록</button>
            </template>
        </AppPageHeader>

        <div v-if="reportData" class="content-container single">
            <div class="json-container">
                <div class="card">
                    <div class="meta-grid">
                        <AppField label="보고일자">
                            <input class="input" v-model="reportData.report_date" />
                        </AppField>
                        <AppField label="작성자">
                            <input class="input" v-model="reportData.author" />
                        </AppField>
                        <AppField label="센터">
                            <input class="input" v-model="reportData.center" />
                        </AppField>
                        <AppField label="진행 주차">
                            <input class="input" v-model="reportData.week_label_done" />
                        </AppField>
                        <AppField label="향후 주차">
                            <input class="input" :value="nextWeek" readonly tabindex="-1" />
                        </AppField>
                    </div>
                </div>

                <div
                    class="card project-block"
                    v-for="(block, index) in projectBlocks"
                    :key="block.key"
                    :data-accent="projectAccentIndex(index)"
                >
                    <div class="project-head">
                        <input
                            class="input project-name-input"
                            :value="blockTitle(block)"
                            placeholder="프로젝트"
                            @input="setBlockTitle(block, $event.target.value)"
                        />
                        <button type="button" class="btn btn-danger" @click="removeProject(block)">삭제</button>
                    </div>
                    <div class="split">
                        <div class="field-group">
                            <h2>진행</h2>
                            <div
                                v-for="(_, itemIndex) in (block.done?.items || [])"
                                :key="`done-${block.key}-${itemIndex}`"
                                class="task-row"
                            >
                                <input class="input" v-model="block.done.items[itemIndex]" />
                                <button type="button" class="btn remove-btn" @click="removeAt(block.done.items, itemIndex)">-</button>
                            </div>
                            <button type="button" class="btn add-btn" @click="addItem(block, 'done')">+</button>
                        </div>
                        <div class="field-group">
                            <h2>다음</h2>
                            <div
                                v-for="(_, itemIndex) in (block.next?.items || [])"
                                :key="`next-${block.key}-${itemIndex}`"
                                class="task-row"
                            >
                                <input class="input" v-model="block.next.items[itemIndex]" />
                                <button type="button" class="btn remove-btn" @click="removeAt(block.next.items, itemIndex)">-</button>
                            </div>
                            <button type="button" class="btn add-btn" @click="addItem(block, 'next')">+</button>
                        </div>
                    </div>
                </div>
                <button type="button" class="btn" @click="addProject">프로젝트 추가</button>

                <div class="card save-bar">
                    <span class="member-id-display">사용자: {{ userName }}</span>
                    <div class="save-actions">
                        <p v-if="confirmQuestions.length" class="confirm-hint">
                            저장 시 확인 질문 {{ confirmQuestions.length }}개
                        </p>
                        <button class="btn" @click="copyReport" :disabled="isSaving">복사</button>
                        <button class="btn btn-primary" @click="saveReport" :disabled="isSaving">
                            {{ isSaving ? "저장 중..." : "저장" }}
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div v-else class="empty-state">보고서 데이터가 없습니다.</div>
    </div>
</template>

<script setup>
import { computed, ref, onMounted, watch } from "vue";
import useApi from "../composables/useApi";
import { useRoute, useRouter } from "vue-router";
import { useDialog } from "../composables/useDialog";
import { projectAccentIndex } from "../lib/projectAccent";
import {
    emptySection,
    formatDeck,
    nextWeekLabel,
    toWeeklyDeck,
} from "../lib/weeklyDeck";
import AppPageHeader from "./ui/AppPageHeader.vue";
import AppField from "./ui/AppField.vue";

const route = useRoute();
const router = useRouter();
const goBack = () => router.push("/weekly");

const reportData = ref(null);
const userName = ref("");
const isSaving = ref(false);
const { getUsers, getWeeklyReportById, updateWeeklyReport } = useApi();
const { alert: showAlert, confirm: askConfirm } = useDialog();

const nextWeek = computed(() => {
    if (!reportData.value) return "";
    return (
        nextWeekLabel(
            reportData.value.week_label_done,
            reportData.value.report_date,
        ) ||
        reportData.value.week_label_next ||
        ""
    );
});

watch(nextWeek, (label) => {
    if (reportData.value && label) {
        reportData.value.week_label_next = label;
    }
});

const confirmQuestions = computed(() => {
    const items = reportData.value?.confirmQuestions;
    if (!Array.isArray(items)) return [];
    return items
        .map((item, index) => ({
            id: item?.id || `q-${index}`,
            text: String(item?.text || "").trim(),
            ifNo: String(item?.ifNo || "").trim(),
        }))
        .filter((item) => item.text)
        .slice(0, 3);
});

const removeAt = (list, index) => {
    list.splice(index, 1);
};

const projectBlocks = computed(() => {
    const data = reportData.value;
    if (!data) return [];
    const order = [];
    const seen = new Map();
    const add = (section, kind, index) => {
        const key = section.title || `__blank_${kind}_${index}`;
        if (!seen.has(key)) {
            const block = { key, done: null, next: null };
            seen.set(key, block);
            order.push(block);
        }
        seen.get(key)[kind] = section;
    };
    (data.done || []).forEach((section, index) => add(section, "done", index));
    (data.next || []).forEach((section, index) => add(section, "next", index));
    return order;
});

const blockTitle = (block) => block.done?.title || block.next?.title || "";

const setBlockTitle = (block, title) => {
    if (block.done) block.done.title = title;
    if (block.next) block.next.title = title;
};

const addItem = (block, kind) => {
    if (!reportData.value) return;
    const list = kind === "done" ? reportData.value.done : reportData.value.next;
    if (!block[kind]) {
        const section = emptySection();
        section.title = blockTitle(block);
        list.push(section);
        return;
    }
    block[kind].items.push("");
};

const removeProject = (block) => {
    if (!reportData.value) return;
    if (block.done) {
        const index = reportData.value.done.indexOf(block.done);
        if (index >= 0) reportData.value.done.splice(index, 1);
    }
    if (block.next) {
        const index = reportData.value.next.indexOf(block.next);
        if (index >= 0) reportData.value.next.splice(index, 1);
    }
};

const addProject = () => {
    if (!reportData.value) return;
    reportData.value.done.push(emptySection());
};



watch(
    reportData,
    (newVal) => {
        if (newVal) sessionStorage.setItem("reportData", JSON.stringify(newVal));
    },
    { deep: true },
);

onMounted(async () => {
    const reportId = route.params.id;
    if (reportId) {
        try {
            const data = await getWeeklyReportById(reportId);
            reportData.value = toWeeklyDeck(data.report);
            if (!reportData.value.author) {
                reportData.value.author = data.memberName || "";
            }
            userName.value = data.memberName || `사용자 ${data.memberId}`;
            sessionStorage.setItem("reportData", JSON.stringify(reportData.value));
            sessionStorage.setItem("selectedUser", String(data.memberId));
        } catch (error) {
            console.error("보고서 불러오기 실패:", error);
            showAlert("보고서를 불러오는데 실패했습니다.");
        }
        return;
    }
    const stored = sessionStorage.getItem("reportData");
    if (stored) reportData.value = toWeeklyDeck(JSON.parse(stored));
    const userId = localStorage.getItem("report-selectedUser") || "";
    if (userId) {
        getUsers()
            .then((users) => {
                const found = users.find((u) => String(u.id) === String(userId));
                userName.value = found ? found.name : `사용자 ${userId}`;
            })
            .catch(() => {
                userName.value = `사용자 ${userId}`;
            });
    }
});

const copyReport = async () => {
    if (!reportData.value) return;
    try {
        await navigator.clipboard.writeText(formatDeck(reportData.value));
        showAlert("보고서가 클립보드에 복사되었습니다.");
    } catch (error) {
        console.error("복사 실패:", error);
        showAlert("복사에 실패했습니다.");
    }
};

const persistReport = async () => {
    const reportId = route.params.id;
    isSaving.value = true;
    try {
        await updateWeeklyReport(reportId, JSON.stringify(reportData.value));
        showAlert("주간 보고서가 저장되었습니다.");
    } catch (error) {
        console.error("저장 실패:", error);
        showAlert("주간 보고서 저장에 실패했습니다.");
    } finally {
        isSaving.value = false;
    }
};

const saveReport = async () => {
    if (!reportData.value) return;
    const reportId = route.params.id;
    if (!reportId) {
        showAlert("저장할 주간 보고서 ID가 없습니다.");
        return;
    }
    const questions = confirmQuestions.value;
    for (const [index, question] of questions.entries()) {
        const ok = await askConfirm(question.text, {
            title: `저장 전 확인 ${index + 1}/${questions.length}`,
            help: "아니요면 해당 항목을 고친 뒤 다시 저장하세요.",
            confirmLabel: "네",
            cancelLabel: "아니요",
        });
        if (!ok) return;
    }
    await persistReport();
};
</script>

<style scoped>
.save-actions {
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
}

.confirm-hint {
    margin: 0;
    margin-right: auto;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--accent);
}

.json-container,
.project-block,
.split,
.field-group,
.meta-grid {
    min-width: 0;
    max-width: 100%;
}

.meta-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-3);
}

.meta-grid :deep(.input) {
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
}

.project-head {
    min-width: 0;
}

.project-head :deep(.project-name-input) {
    width: auto;
    min-width: 0;
    flex: 1;
}

.project-head :deep(.btn) {
    flex-shrink: 0;
}

.split {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: var(--space-4);
}

.split h2 {
    margin: 0 0 var(--space-2);
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.task-row :deep(.input) {
    width: auto;
    min-width: 0;
    flex: 1;
}

.project-block {
    margin-bottom: var(--space-3);
    overflow: hidden;
}

@media (max-width: 1100px) {
    .meta-grid,
    .split {
        grid-template-columns: minmax(0, 1fr);
    }
}
</style>
