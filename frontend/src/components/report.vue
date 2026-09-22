<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from "vue";
import { useRouter } from "vue-router";
import { UploadCloud } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { useDialog } from "../composables/useDialog";
import {
    PASTE_TEMPLATES,
    applyTemplate,
    hasTypedContent,
    templateById,
} from "../lib/reportTemplates";
import { todayString } from "../lib/dateScope";

const {
    postReport,
    postReportPptx,
    getReportDraft,
    postReportDraft,
    getUserActivities,
    getUsers,
    getReports,
} = useApi();
const router = useRouter();
const { alert: showAlert, confirm: askConfirm } = useDialog();

const input = ref("");
const file = ref(null);
const buttonType = ref("text");
const date = ref(todayString());

const aiLoading = ref(false);
const draftSaving = ref(false);
const draftSavedAt = ref("");
const formError = ref("");
const userName = ref("");
const alreadySaved = ref(false);
const elapsed = ref(0);
const prevPlans = ref([]);
const prevPlansDate = ref("");
const isDragging = ref(false);
let elapsedTimer = null;

const elapsedLabel = computed(() => {
    const minutes = Math.floor(elapsed.value / 60);
    const seconds = elapsed.value % 60;
    return minutes > 0 ? `${minutes}분 ${seconds}초` : `${seconds}초`;
});

const startElapsedTimer = () => {
    stopElapsedTimer();
    elapsed.value = 0;
    elapsedTimer = setInterval(() => {
        elapsed.value += 1;
    }, 1000);
};

const stopElapsedTimer = () => {
    if (elapsedTimer !== null) {
        clearInterval(elapsedTimer);
        elapsedTimer = null;
    }
};

const getSelectedMemberId = () => {
    const value = selectedUserId.value;
    if (value === null || value === undefined || value === "선택") return null;
    const memberId = Number(value);
    return Number.isInteger(memberId) && memberId > 0 ? memberId : null;
};

const hasUser = computed(() => getSelectedMemberId() !== null);

const activeTemplateId = ref("");

const activeTemplate = computed(() => templateById(activeTemplateId.value));

/** 이미 쓴 글이 있으면 말없이 덧붙이지 않는다.
 *  저장된 하루 위에 템플릿이 붙어 버리면 사고다. 바꿀지 덧붙일지 먼저 묻는다. */
const insertTemplate = async (template) => {
    if (!hasTypedContent(input.value)) {
        activeTemplateId.value = template?.id || "";
        input.value = applyTemplate(input.value, template, "replace");
        return;
    }
    const replace = await askConfirm(
        `쓰던 내용을 '${template.label}' 형식으로 바꿀까요?`,
        {
            title: "형식 넣기",
            help: "아니요를 누르면 쓰던 내용 아래에 형식을 덧붙입니다.",
            confirmLabel: "바꾸기",
            cancelLabel: "아래에 덧붙이기",
        },
    );
    activeTemplateId.value = template?.id || "";
    input.value = applyTemplate(
        input.value,
        template,
        replace ? "replace" : "append",
    );
};

const loadUserName = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null) {
        userName.value = "";
        return;
    }
    try {
        const users = await getUsers();
        const found = users.find((u) => String(u.id) === String(memberId));
        userName.value = found ? found.name : `사용자 ${memberId}`;
    } catch {
        userName.value = `사용자 ${memberId}`;
    }
};

const loadSavedState = async () => {
    const memberId = getSelectedMemberId();
    alreadySaved.value = false;
    if (memberId === null || !date.value) return;
    try {
        const rows = await getUserActivities(
            Number(date.value.slice(0, 4)),
            Number(date.value.slice(5, 7)),
            date.value,
            date.value,
        );
        const mine = (rows || []).find(
            (row) => String(row.member_id) === String(memberId),
        );
        alreadySaved.value = Boolean(mine && (mine.activities || []).some((a) => a.count > 0));
    } catch {
        alreadySaved.value = false;
    }
};

const loadDraft = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null || input.value.trim()) return;
    try {
        const draft = await getReportDraft(memberId, date.value);
        input.value = draft.raw_text;
    } catch (error) {
        if (error.response?.status !== 404) {
            console.error("원문 초안 불러오기 실패:", error);
        }
    }
};

/** 로그인 사용자의 가장 최근 보고에서 '다음 계획'을 가져온다.
 *  오늘 보고를 쓸 때 어제 약속한 일부터 보여야 한다. */
const loadPrevPlans = async () => {
    prevPlans.value = [];
    prevPlansDate.value = "";
    const memberId = getSelectedMemberId();
    if (memberId === null || !date.value) return;
    try {
        const rows = await getReports();
        const mine = (rows || [])
            .filter(
                (row) =>
                    String(row.member_id) === String(memberId) &&
                    row.report_date &&
                    row.report_date < date.value,
            )
            .sort((a, b) =>
                String(b.report_date).localeCompare(String(a.report_date)),
            );
        const latest = mine[0];
        if (!latest) return;
        let parsed = latest.parsed_json;
        if (typeof parsed === "string") {
            try {
                parsed = JSON.parse(parsed);
            } catch {
                return;
            }
        }
        const items = [];
        for (const project of parsed?.projects || []) {
            for (const plan of project.nextPlans || []) {
                const text = String(plan || "").trim();
                if (!text) continue;
                items.push({
                    project: project.projectName || "미분류 프로젝트",
                    text,
                });
            }
        }
        if (items.length) {
            prevPlans.value = items;
            prevPlansDate.value = latest.report_date;
        }
    } catch {
        prevPlans.value = [];
    }
};

const prevPlansLabel = computed(() => {
    const count = prevPlans.value.length;
    if (!count) return "";
    const parts = String(prevPlansDate.value).split("-");
    const month = Number(parts[1]);
    const day = Number(parts[2]);
    const when = month && day ? `${month}.${day}` : prevPlansDate.value;
    return `${when} 계획 ${count}건`;
});

const statusLabel = computed(() => {
    if (alreadySaved.value) return "제출됨";
    if (draftSavedAt.value) return "초안 있음";
    return "미제출";
});

const statusDetail = computed(() => {
    if (alreadySaved.value) return "다시 제출하면 덮어씀";
    if (draftSavedAt.value) return "아직 미제출";
    return "";
});

const insertPrevPlans = () => {
    const lines = prevPlans.value.map(
        (item) => `- [${item.project}] ${item.text}`,
    );
    const base = input.value.trim() ? input.value.replace(/\s+$/, "") + "\n" : "";
    input.value = base + lines.join("\n");
};

const refreshMeta = async () => {
    await loadUserName();
    await loadSavedState();
    await loadPrevPlans();
};

onMounted(async () => {
    await refreshMeta();
    await loadDraft();
});
onUnmounted(() => {
    stopElapsedTimer();
});
watch(date, async () => {
    draftSavedAt.value = "";
    await loadSavedState();
    await loadPrevPlans();
    await loadDraft();
});
watch(selectedUserId, refreshMeta);

const selectType = (nextType) => {
    buttonType.value = nextType;
};

const acceptFile = (selected) => {
    if (!selected) return false;
    if (!selected.name.toLowerCase().endsWith(".pptx")) {
        formError.value = "PPTX 파일만 올릴 수 있습니다.";
        file.value = null;
        return false;
    }
    formError.value = "";
    file.value = selected;
    return true;
};

const uploadFile = (event) => {
    const selected = event.target.files?.[0] || null;
    if (!acceptFile(selected)) event.target.value = "";
};

/* 드래그해서 놓기. 점선 박스 안의 '파일 고르기'만 되면 손이 한 번 더 간다. */
const onDragOver = (event) => {
    event.preventDefault();
    isDragging.value = true;
};

const onDragLeave = () => {
    isDragging.value = false;
};

const onDrop = (event) => {
    event.preventDefault();
    isDragging.value = false;
    acceptFile(event.dataTransfer?.files?.[0] || null);
};

const clearFile = () => {
    file.value = null;
};

/** AI를 돌리지 않고 원문만 저장한다. 고치려고 매번 추출할 필요가 없어야 한다. */
const saveDraft = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null) {
        formError.value = "로그인이 필요합니다.";
        router.push("/login");
        return;
    }
    if (!input.value.trim()) {
        formError.value = "저장할 내용을 입력해주세요.";
        return;
    }
    formError.value = "";
    draftSaving.value = true;
    try {
        await postReportDraft(input.value, date.value, memberId);
        const now = new Date();
        draftSavedAt.value = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    } catch (error) {
        const detail = error.response?.data?.detail;
        formError.value = detail || "초안 저장에 실패했습니다.";
    } finally {
        draftSaving.value = false;
    }
};

const sendReport = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null) {
        formError.value = "로그인이 필요합니다.";
        router.push("/login");
        return;
    }

    if (buttonType.value === "text") {
        if (!input.value.trim()) {
            formError.value = "보고서 내용을 입력해주세요.";
            return;
        }
    } else if (!file.value) {
        formError.value = "PPTX 파일을 선택해주세요.";
        return;
    }

    formError.value = "";
    aiLoading.value = true;
    startElapsedTimer();

    try {
        let parsed;
        let rawText;

        if (buttonType.value === "text") {
            rawText = input.value;
            parsed = await postReport(
                { content: rawText },
                date.value,
                memberId,
            );
        } else {
            const res = await postReportPptx(file.value, date.value, memberId);
            parsed = res.parsed;
            rawText = res.raw_text;
        }

        sessionStorage.setItem("reportData", JSON.stringify(parsed));
        sessionStorage.setItem("reportRaw", rawText);
        sessionStorage.setItem("reportDate", date.value);
        await router.push({ name: "report-result" });
    } catch (error) {
        console.error("보고서 전송 실패:", error);
        const detail = error.response?.data?.detail;
        const message =
            detail ||
            "보고서 전송에 실패했습니다. 입력한 내용은 유지되니 다시 시도해주세요.";
        formError.value = message;
        showAlert(message);
    } finally {
        stopElapsedTimer();
        aiLoading.value = false;
    }
};
</script>

<template>
    <div class="page">
        <div v-if="!hasUser" class="card">
            <p class="form-hint">로그인이 필요합니다.</p>
            <div class="form-actions">
                <router-link class="btn btn-primary" to="/login">로그인</router-link>
            </div>
        </div>

        <div v-else class="card write-card">
            <div class="write-head">
                <span class="write-author">{{ userName || "나" }}</span>
                <input
                    type="date"
                    id="date"
                    class="input write-date"
                    v-model="date"
                    aria-label="보고 날짜"
                    required
                />
                <span
                    class="status-chip"
                    :class="alreadySaved ? 'is-saved' : 'is-draft'"
                    :title="statusDetail"
                >
                    {{ statusLabel }}
                    <span v-if="statusDetail" class="status-chip-more"> · {{ statusDetail }}</span>
                </span>
                <button
                    type="button"
                    class="write-mode-link"
                    @click="selectType(buttonType === 'text' ? 'file' : 'text')"
                >
                    {{ buttonType === "text" ? "PPTX 올리기" : "직접 입력하기" }}
                </button>
            </div>

            <div v-if="buttonType === 'text'" class="field write-field">
                <textarea
                    id="report-input"
                    v-model="input"
                    :placeholder="activeTemplate?.hint || '오늘 한 일, 진행 상황, 이슈, 다음 계획을 자유롭게 쓰거나 붙여넣으세요.'"
                    rows="10"
                    class="textarea"
                ></textarea>
                <!-- 좁은 화면에서는 글을 먼저 보여주고, 형식은 한 줄로 옆으로 넘긴다. -->
                <div class="write-helpers">
                    <span class="write-helpers-label">형식</span>
                    <div class="template-chips" role="group" aria-label="붙여넣기 형식">
                        <button
                            v-for="template in PASTE_TEMPLATES"
                            :key="template.id"
                            type="button"
                            class="btn btn-small"
                            :class="{ on: activeTemplateId === template.id }"
                            :aria-pressed="activeTemplateId === template.id"
                            :title="template.hint"
                            @click="insertTemplate(template)"
                        >
                            {{ template.label }}
                        </button>
                    </div>
                    <button
                        v-if="prevPlans.length"
                        type="button"
                        class="btn btn-small write-prev-plans"
                        :title="`${prevPlansDate} 보고의 다음 계획 ${prevPlans.length}건을 붙입니다`"
                        @click="insertPrevPlans"
                    >
                        {{ prevPlansLabel }}
                    </button>
                </div>
            </div>

            <div
                v-else
                class="field file-drop-area"
                :class="{ 'is-dragging': isDragging }"
                @dragover="onDragOver"
                @dragenter="onDragOver"
                @dragleave="onDragLeave"
                @drop="onDrop"
            >
                <UploadCloud :size="22" aria-hidden="true" />
                <p class="file-drop-copy">
                    PPTX 파일을 고르거나 여기로 놓으세요
                </p>
                <label class="file-drop-pick" for="pptx-input">파일 고르기</label>
                <input
                    id="pptx-input"
                    class="file-drop-input"
                    type="file"
                    accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    @change="uploadFile"
                />
                <p v-if="file" class="file-name">
                    {{ file.name }}
                    <button type="button" class="file-clear" @click="clearFile">지우기</button>
                </p>
            </div>

            <p v-if="formError" class="form-error" role="alert">
                {{ formError }}
            </p>
            <div v-if="aiLoading" class="ai-progress" role="status">
                <p class="ai-progress-title">
                    로컬 AI가 정리하고 있어요 · {{ elapsedLabel }} 경과
                </p>
                <p class="ai-progress-help">
                    보통 1~3분, 최대 10분까지 걸릴 수 있어요. 이 화면을 유지해주세요.
                    입력한 내용은 그대로 남습니다.
                </p>
            </div>
            <div class="form-actions">
                <span v-if="draftSavedAt" class="draft-note" role="status">
                    {{ draftSavedAt }} 초안 저장됨
                </span>
                <!-- AI를 돌리지 않고도 저장할 수 있어야 한다. 고칠 때마다 추출할 이유가 없다. -->
                <button
                    v-if="buttonType === 'text'"
                    class="btn"
                    @click="saveDraft"
                    :disabled="aiLoading || draftSaving || !input.trim()"
                >
                    {{ draftSaving ? "저장 중..." : "초안만 저장" }}
                </button>
          
                <button
                    class="btn btn-primary"
                    @click="sendReport"
                    :disabled="aiLoading"
                >
                    {{ aiLoading ? `정리 중... (${elapsedLabel})` : "제출" }}
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.write-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2) var(--space-3);
    margin-bottom: var(--space-4);
}

.write-author {
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.write-date {
    width: auto;
    height: 32px;
    font-size: var(--fs-13);
}

.write-mode-link {
    margin-left: auto;
    padding: 0;
    border: none;
    background: none;
    font: inherit;
    font-size: var(--fs-13);
    color: var(--text);
    text-decoration: underline;
    text-underline-offset: 3px;
    cursor: pointer;
}

.write-mode-link:hover {
    color: var(--text-strong);
}

/* 입력칸 위에 항상 보이는 보조 줄. 접어두면 아무도 못 찾는다. */
.write-field {
    display: flex;
    flex-direction: column;
}

.write-helpers {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    order: 1;
    gap: var(--space-2) var(--space-3);
    margin-bottom: var(--space-2);
}

.write-field .textarea {
    order: 2;
}

.write-helpers-label {
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.write-prev-plans {
    margin-left: auto;
    border-color: var(--accent-border);
    background: var(--accent-soft);
    color: var(--text-strong);
}

.template-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
}

.template-chips .on {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--text-strong);
}

.form-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-2);
    margin-top: var(--space-4);
}

.draft-note {
    margin-right: auto;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--success-fg);
}

.form-error {
    margin-top: var(--space-3);
    color: var(--danger-fg);
    font-size: var(--fs-13);
}

.form-hint {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text);
}

/* 드래그해서 놓는 칸. 파일 입력은 숨기고 라벨을 버튼처럼 쓴다. */
.file-drop-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-6) var(--space-5);
    border: 1px dashed var(--border-strong);
    border-radius: var(--radius-sm);
    background: var(--bg);
    text-align: center;
    transition:
        border-color var(--dur-fast) var(--ease),
        background var(--dur-fast) var(--ease);
}

.file-drop-area svg {
    color: var(--text);
}

.file-drop-area:hover,
.file-drop-area:focus-within,
.file-drop-area.is-dragging {
    border-color: var(--accent);
    background: var(--accent-soft);
}

.file-drop-copy {
    margin: 0;
    font-size: var(--fs-14);
    font-weight: var(--fw-medium);
    color: var(--text-strong);
}

.file-drop-pick {
    display: inline-flex;
    align-items: center;
    height: 32px;
    padding: 0 var(--space-4);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-pill);
    background: var(--surface);
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    color: var(--text-strong);
    cursor: pointer;
}

.file-drop-pick:hover {
    border-color: var(--accent);
}

.file-drop-input {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    border: 0;
}

.file-name {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    margin: 0;
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.file-clear {
    padding: 0;
    border: none;
    background: none;
    font: inherit;
    font-size: var(--fs-12);
    font-weight: var(--fw-medium);
    color: var(--text);
    text-decoration: underline;
    text-underline-offset: 3px;
    cursor: pointer;
}

.ai-progress {
    margin-top: var(--space-4);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-sm);
    background: var(--accent-soft);
}

.ai-progress-title {
    margin: 0;
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.ai-progress-help {
    margin: var(--space-2) 0 0;
    font-size: var(--fs-13);
    color: var(--text);
}

@media (max-width: 860px) {
    .write-card {
        padding-bottom: 88px;
    }

    .write-head {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: 8px 12px;
    }

    .write-author {
        min-width: 0;
    }

    .write-date {
        width: auto;
        min-width: 148px;
        min-height: 44px;
        height: 44px;
        font-size: 16px;
    }

    .status-chip {
        justify-self: start;
        max-width: 100%;
    }

    .status-chip-more {
        display: none;
    }

    .write-mode-link {
        margin-left: 0;
        justify-self: end;
        min-height: 44px;
        text-align: right;
    }

    .write-field {
        gap: 10px;
    }

    .write-field .textarea {
        order: 1;
        min-height: 42dvh;
        font-size: 16px;
        line-height: 1.5;
    }

    .write-helpers {
        order: 2;
        margin-bottom: 0;
    }

    .write-helpers {
        flex-wrap: nowrap;
        align-items: center;
        gap: 8px;
        margin: 0 -4px;
        padding: 2px 4px 6px;
        overflow-x: auto;
        overscroll-behavior-x: contain;
    }

    .write-helpers-label,
    .template-chips,
    .write-prev-plans {
        flex: none;
    }

    .template-chips {
        flex-wrap: nowrap;
    }

    .write-prev-plans {
        margin-left: 0;
        width: auto;
        white-space: nowrap;
    }

    .file-drop-copy {
        font-size: 14px;
    }

    .file-drop-pick {
        min-height: 44px;
        height: 44px;
        padding: 0 18px;
    }

    .form-actions {
        position: sticky;
        bottom: calc(var(--bottom-nav-offset) + 8px);
        z-index: 8;
        flex-wrap: wrap;
        justify-content: stretch;
        margin: 16px -14px -14px;
        padding: 10px 14px;
        background: var(--surface);
        border-top: 1px solid var(--border);
    }

    .form-actions .btn {
        flex: 1 1 calc(50% - 6px);
    }

    .form-actions .btn-primary {
        flex: 1 1 100%;
    }

    .draft-note {
        width: 100%;
        margin-right: 0;
    }
}
</style>
