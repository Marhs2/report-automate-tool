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
import { onlyStructuredLineReport } from "../lib/lineReport.js";
import LineWriter from "./ui/line-writer.vue";

const {
    postReport,
    postReportPptx,
    getReportDraft,
    postReportDraft,
    getUserActivities,
    getUsers,
    getProjectNames,
    postProjectName,
} = useApi();
const router = useRouter();
const { alert: showAlert, confirm: askConfirm } = useDialog();

const input = ref("");
const file = ref(null);
const buttonType = ref("text");
/** 좁은 화면 기본은 한 줄씩 쓰기. 메신저 대화를 통째로 붙이려면 붙여넣기로 바꾼다. */
const pasteOnNarrow = ref(false);
const date = ref(todayString());

const aiLoading = ref(false);
const draftSaving = ref(false);
const draftSavedAt = ref("");
const formError = ref("");
const userName = ref("");
const alreadySaved = ref(false);
const elapsed = ref(0);
const isDragging = ref(false);
const knownProjects = ref([]);
const lineWriter = ref(null);
const isNarrow = ref(
    typeof window !== "undefined" &&
        window.matchMedia("(max-width: 860px)").matches,
);
let narrowQuery = null;
let elapsedTimer = null;
const useLines = computed(
    () => isNarrow.value && buttonType.value === "text" && !pasteOnNarrow.value,
);
const inputMode = computed(() => {
    if (buttonType.value === "file") return "file";
    return useLines.value ? "lines" : "paste";
});
const inputModes = computed(() =>
    isNarrow.value
        ? [
              { id: "lines", label: "한 줄씩" },
              { id: "paste", label: "붙여넣기" },
          ]
        : [
              { id: "paste", label: "텍스트" },
              { id: "file", label: "PPTX 올리기" },
          ],
);
/** AI가 나누는 항목. 작성 화면 옆에서 무엇이 어떻게 나뉘는지 미리 보여 준다. */
const EXTRACT_KINDS = [
    { label: "프로젝트", hint: "정식명 · 별칭으로 묶음", tone: "neutral" },
    { label: "완료", hint: "끝낸 일", tone: "success" },
    { label: "진행 중", hint: "아직 하는 일", tone: "info" },
    { label: "이슈", hint: "막힌 점", tone: "warning" },
    { label: "협조 요청", hint: "필요한 도움", tone: "request" },
    { label: "다음 계획", hint: "다음에 할 일", tone: "muted" },
];

const elapsedLabel = computed(() => {
    const minutes = Math.floor(elapsed.value / 60);
    const seconds = elapsed.value % 60;
    return minutes > 0 ? `${minutes}분 ${seconds}초` : `${seconds}초`;
});

const waitStages = [
    { label: "글을 읽고 있어요" },
    { label: "항목을 나누고 있어요" },
    { label: "문장을 다듬고 있어요" },
];

const waitStage = computed(() => {
    if (elapsed.value >= 20) return 2;
    if (elapsed.value >= 8) return 1;
    return 0;
});

const waitDateLabel = computed(() => {
    const [, month, day] = String(date.value || "").split("-");
    if (!month || !day) return "일일보고";
    return `${Number(month)}월 ${Number(day)}일`;
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

/** 서버 시각은 SQLite CURRENT_TIMESTAMP(UTC) "2026-09-29 05:40:12". 내 시간 "14:40"으로 바꾼다. */
const draftTimeLabel = (value) => {
    const text = String(value || "").trim();
    const at = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(text) ? text : `${text.replace(" ", "T")}Z`);
    if (Number.isNaN(at.getTime())) return "저장됨";
    return `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
};

const loadDraft = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null || !date.value) return;
    // 제출된 글은 작성 칸에 다시 넣지 않는다. 남으면 지우고 새로 써야 한다.
    if (alreadySaved.value) {
        input.value = "";
        draftSavedAt.value = "";
        return;
    }
    try {
        const draft = await getReportDraft(memberId, date.value);
        if (alreadySaved.value || input.value.trim()) return;
        const raw = String(draft.raw_text || "");
        if (raw.trim()) draftSavedAt.value = draftTimeLabel(draft.updated_at);
        const structured = onlyStructuredLineReport(raw);
        // 한 줄씩 칸에 못 옮기는 글(메신저 대화 등)은 숨기지 않고 붙여넣기로 연다.
        if (useLines.value && raw.trim() && !structured.trim()) {
            pasteOnNarrow.value = true;
            input.value = raw;
            return;
        }
        input.value = useLines.value ? structured : raw;
    } catch (error) {
        if (error.response?.status !== 404) {
            console.error("원문 초안 불러오기 실패:", error);
        }
    }
};

const statusLabel = computed(() => {
    if (alreadySaved.value) return "제출됨";
    if (draftSavedAt.value) return `원문 초안 · ${draftSavedAt.value}`;
    return "미제출";
});

const statusDetail = computed(() => {
    if (alreadySaved.value) return "다시 저장하면 덮어씀";
    if (draftSavedAt.value) return "추출·검토 전";
    return "";
});

const loadProjects = async () => {
    try {
        const names = await getProjectNames();
        knownProjects.value = Array.isArray(names)
            ? names.map((name) => String(name || "").trim()).filter(Boolean)
            : [];
    } catch {
        knownProjects.value = [];
    }
};

const registerProject = async (name) => {
    const value = String(name || "").trim();
    if (!value) return;
    if (!knownProjects.value.includes(value)) {
        knownProjects.value = [...knownProjects.value, value];
    }
    try {
        await postProjectName(value, "");
    } catch (error) {
        if (error.response?.status !== 409) {
            formError.value = error.response?.data?.detail || "프로젝트를 추가하지 못했습니다.";
        }
    }
};

const reportBody = () => input.value;

const refreshMeta = async () => {
    await loadUserName();
    await loadSavedState();
    await loadProjects();
};

const syncNarrow = () => {
    isNarrow.value = Boolean(narrowQuery?.matches);
    if (isNarrow.value && buttonType.value === "file") {
        buttonType.value = "text";
        pasteOnNarrow.value = false;
        file.value = null;
    }
};

onMounted(async () => {
    narrowQuery = window.matchMedia("(max-width: 860px)");
    syncNarrow();
    narrowQuery.addEventListener("change", syncNarrow);
    await refreshMeta();
    await loadDraft();
});
onUnmounted(() => {
    stopElapsedTimer();
    narrowQuery?.removeEventListener("change", syncNarrow);
    if (aiLoading.value) {
        document.documentElement.classList.remove("is-overlay-open");
    }
});
watch(date, async () => {
    input.value = "";
    activeTemplateId.value = "";
    draftSavedAt.value = "";
    await loadSavedState();
    await loadDraft();
});
watch(selectedUserId, async () => {
    input.value = "";
    draftSavedAt.value = "";
    await refreshMeta();
    await loadDraft();
});

const selectType = (nextType) => {
    if (nextType === "file") {
        if (isNarrow.value) return;
        buttonType.value = "file";
        return;
    }
    buttonType.value = "text";
    pasteOnNarrow.value = nextType === "paste";
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
        await postReportDraft(reportBody(), date.value, memberId);
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
    if (useLines.value) {
        const blocked = lineWriter.value?.commitPending() || "";
        if (blocked) {
            formError.value = blocked;
            return;
        }
    }

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
    document.documentElement.classList.add("is-overlay-open");
    startElapsedTimer();

    try {
        let parsed;
        let rawText;

        if (buttonType.value === "text") {
            rawText = reportBody();
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
        document.documentElement.classList.remove("is-overlay-open");
    }
};
</script>

<template>
    <div class="daily-write">
        <div v-if="!hasUser" class="card">
            <p class="form-hint">로그인이 필요합니다.</p>
            <div class="form-actions">
                <router-link class="btn btn-primary" to="/login">로그인</router-link>
            </div>
        </div>

        <div v-else class="write-layout">
        <div
            class="card write-card"
            :class="{ 'is-lines': useLines }"
        >
            <div class="write-head">
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
                    :class="alreadySaved ? 'is-saved' : draftSavedAt ? 'is-draft' : 'is-danger'"
                    :title="statusDetail"
                >
                    {{ statusLabel }}
                    <span v-if="statusDetail" class="status-chip-more"> · {{ statusDetail }}</span>
                </span>
                <div class="seg write-modes" role="tablist" aria-label="입력 방식">
                    <button
                        v-for="mode in inputModes"
                        :key="mode.id"
                        type="button"
                        role="tab"
                        :aria-selected="inputMode === mode.id"
                        :class="{ 'is-on': inputMode === mode.id }"
                        @click="selectType(mode.id)"
                    >
                        {{ mode.label }}
                    </button>
                </div>
            </div>

            <template v-if="useLines">
                <LineWriter
                    ref="lineWriter"
                    v-model="input"
                    :projects="knownProjects"
                    @add-project="registerProject"
                >
                    <template #dock>
                        <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
                        <button
                            v-if="input.trim()"
                            type="button"
                            class="btn btn-primary line-send"
                            @click="sendReport"
                            :disabled="aiLoading"
                        >
                            {{ aiLoading ? "추출 중" : "AI로 추출" }}
                        </button>
                    </template>
                </LineWriter>
            </template>

            <div v-else-if="buttonType === 'text'" class="field write-field">
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
                </div>
                <textarea
                    id="report-input"
                    v-model="input"
                    :placeholder="activeTemplate?.hint || '오늘 한 일, 이슈, 요청, 다음 계획을 쓰거나 붙여넣으세요.'"
                    rows="10"
                    class="textarea"
                ></textarea>
            </div>

            <div
                v-else-if="!isNarrow"
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

            <p v-if="formError && !useLines" class="form-error" role="alert">
                {{ formError }}
            </p>
            <div v-if="!useLines" class="form-actions">
                <span v-if="draftSavedAt" class="draft-note" role="status">
                    {{ draftSavedAt }} 초안 저장됨
                </span>
                <button
                    v-if="buttonType === 'text'"
                    class="btn"
                    @click="saveDraft"
                    :disabled="aiLoading || draftSaving || !input.trim()"
                >
                    {{ draftSaving ? "저장 중..." : "원문만 초안 저장" }}
                </button>
                <button
                    class="btn btn-primary"
                    @click="sendReport"
                    :disabled="aiLoading"
                >
                    {{ aiLoading ? "추출 중" : "AI로 추출" }}
                </button>
            </div>
            <p v-if="!useLines" class="write-footnote">
                AI가 초안을 만들면 원문과 나란히 검토하고 저장해요.
            </p>
        </div>
        <aside v-if="!isNarrow" class="write-aside">
            
            <section class="card aside-card" aria-labelledby="steps-title">
                <h2 id="steps-title">저장까지 세 단계</h2>
                <ol class="step-list">
                    <li class="is-on"><b>1</b><span>원문을 쓰거나 붙여 넣기</span></li>
                    <li><b>2</b><span>AI가 프로젝트별 초안 만들기</span></li>
                    <li><b>3</b><span>원문과 나란히 검토하고 저장</span></li>
                </ol>
                <p class="aside-note">
                    {{ waitDateLabel }}에
                    {{ alreadySaved ? "저장된 보고가 있어요. 다시 저장하면 바꿀지 먼저 물어봐요." : "저장된 보고가 없어요." }}
                </p>
            </section>
            <section class="card aside-card" aria-labelledby="kinds-title">
                <h2 id="kinds-title">AI가 나누는 항목</h2>
                <ul class="kind-list">
                    <li v-for="kind in EXTRACT_KINDS" :key="kind.label">
                        <span class="kind-swatch" :class="`is-${kind.tone}`" aria-hidden="true"></span>
                        <span class="kind-label">{{ kind.label }}</span>
                        <span class="kind-hint">{{ kind.hint }}</span>
                    </li>
                </ul>
            </section>
        </aside>
        </div>
    </div>
    <Teleport to="body">
        <div v-if="aiLoading" class="submit-wait" role="status" aria-live="polite">
            <div class="submit-wait-card">
                <p class="submit-wait-date">{{ waitDateLabel }}</p>
                <h2>{{ waitStages[waitStage].label }}</h2>
                <div class="submit-meter" aria-hidden="true">
                    <span :style="{ width: ['18%', '52%', '78%'][waitStage] }"></span>
                </div>
                <ol class="submit-steps">
                    <li
                        v-for="(stage, index) in waitStages"
                        :key="stage.label"
                        :class="{ 'is-done': index < waitStage, 'is-on': index === waitStage }"
                    >
                        {{ stage.label }}
                    </li>
                </ol>
                <p class="submit-wait-time">{{ elapsedLabel }} · 보통 10초에서 1분</p>
            </div>
        </div>
    </Teleport>
</template>

<style scoped>
.write-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2) var(--space-3);
    margin-bottom: var(--space-4);
}


.write-date {
    width: auto;
    height: var(--control-h-sm);
    font-size: var(--fs-13);
}

.write-modes {
    margin-left: auto;
}

.write-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 300px;
    gap: var(--space-5);
    align-items: start;
}

.write-footnote {
    margin: var(--space-2) 0 0;
    text-align: right;
    font-size: var(--fs-12);
    color: var(--text-muted);
}

.write-aside {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
}

.aside-card {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.aside-card h2 {
    margin: 0;
    font-size: var(--fs-14);
    font-weight: var(--fw-bold);
    color: var(--text-strong);
}



.step-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin: var(--space-1) 0 0;
    padding: 0;
    list-style: none;
}

.step-list li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--fs-13);
    color: var(--text);
}

.step-list b {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    flex-shrink: 0;
    border-radius: var(--radius-pill);
    background: var(--surface-soft);
    color: var(--text-muted);
    font-size: var(--fs-11);
}

.step-list li.is-on {
    color: var(--text-strong);
    font-weight: var(--fw-semibold);
}

.step-list li.is-on b {
    background: var(--accent);
    color: var(--text-on-accent);
}

.aside-note {
    margin: var(--space-1) 0 0;
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
    font-size: var(--fs-12);
    line-height: var(--lh-base);
    color: var(--text-muted);
    word-break: keep-all;
}

.aside-row {
    display: flex;
    justify-content: space-between;
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text-muted);
}

.aside-row b {
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.kind-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin: var(--space-1) 0 0;
    padding: 0;
    list-style: none;
}

.kind-list li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--fs-13);
}

.kind-swatch {
    width: 8px;
    height: 8px;
    flex-shrink: 0;
    border-radius: 2px;
}

.kind-swatch.is-neutral { background: var(--text-strong); }
.kind-swatch.is-success { background: var(--success-fg); }
.kind-swatch.is-info { background: var(--info-fg); }
.kind-swatch.is-warning { background: var(--warning-fg); }
.kind-swatch.is-request { background: var(--project-4-fg); }
.kind-swatch.is-muted { background: var(--text-muted); }

.kind-label {
    width: 64px;
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.kind-hint {
    color: var(--text-muted);
}

@media (max-width: 1100px) {
    .write-layout {
        grid-template-columns: minmax(0, 1fr);
    }

    .write-aside {
        display: none;
    }
}

.write-field .textarea {
    min-height: 320px;
}

.write-helpers {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2) var(--space-3);
    margin-bottom: var(--space-2);
}

.write-helpers-label {
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
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
    padding: var(--space-7) var(--space-5);
    border: 1px dashed var(--border-strong);
    border-radius: var(--radius);
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
    height: var(--control-h-sm);
    padding: 0 var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    color: var(--text-strong);
    cursor: pointer;
    transition:
        border-color var(--dur-fast) var(--ease),
        background var(--dur-fast) var(--ease);
}

.file-drop-pick:hover {
    border-color: var(--accent);
    background: var(--accent-soft);
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
    color: var(--danger-fg);
    cursor: pointer;
}

.submit-wait {
    position: fixed;
    inset: 0;
    z-index: 90;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-4);
    background: var(--overlay);
}

.submit-wait-card {
    width: min(420px, 100%);
    padding: var(--space-6) var(--space-5) var(--space-5);
    border-radius: var(--radius-lg);
    background: var(--surface);
    box-shadow: var(--shadow-2);
}

.submit-wait-date {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text);
}

.submit-wait-card h2 {
    margin: var(--space-2) 0 0;
    font-size: var(--fs-20);
    font-weight: var(--fw-semibold);
    letter-spacing: -0.02em;
    color: var(--text-strong);
}

.submit-meter {
    height: var(--space-1);
    margin: var(--space-4) 0;
    background: var(--border);
}

.submit-meter span {
    display: block;
    height: 100%;
    background: var(--accent);
    transition: width 0.4s ease;
}

.submit-steps {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.submit-steps li {
    min-height: var(--control-h-sm);
    font-size: var(--fs-14);
    color: var(--text-muted);
}

.submit-steps li.is-on {
    color: var(--text-strong);
    font-weight: var(--fw-semibold);
}

.submit-steps li.is-done {
    color: var(--text);
}

.submit-wait-time {
    margin: var(--space-4) 0 0;
    font-size: var(--fs-13);
    color: var(--text);
}

@media (max-width: 860px) {
    .write-card {
        padding-bottom: calc(var(--control-h-lg) + var(--space-8));
    }

    .write-head {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: var(--space-2) var(--space-3);
    }

    .write-date {
        width: 100%;
        min-width: 0;
        max-width: 100%;
        min-height: var(--control-h-lg);
        height: var(--control-h-lg);
        font-size: var(--fs-16);
        overflow: hidden;
    }

    .status-chip {
        justify-self: start;
        max-width: 100%;
    }

    .status-chip-more {
        display: none;
    }

    .write-modes {
        grid-column: 1 / -1;
        margin-left: 0;
    }

    .write-footnote {
        text-align: center;
    }

    .write-field .textarea {
        min-height: 42dvh;
        font-size: var(--fs-16);
        line-height: 1.5;
    }

    .file-drop-copy {
        font-size: var(--fs-14);
    }

    .file-drop-pick {
        min-height: var(--control-h-lg);
        height: var(--control-h-lg);
        padding: 0 var(--space-5);
    }

    .form-actions {
        position: sticky;
        bottom: calc(var(--bottom-nav-offset) + var(--space-2));
        z-index: 8;
        flex-wrap: wrap;
        justify-content: stretch;
        margin: var(--space-4) calc(var(--space-4) * -1) calc(var(--space-4) * -1);
        padding: var(--space-3) var(--space-4);
        background: var(--surface);
        border-top: 1px solid var(--border);
    }

    .form-actions .btn {
        flex: 1 1 calc(50% - var(--space-2));
    }

    .form-actions .btn-primary {
        flex: 1 1 100%;
    }


    .daily-write:has(.write-card.is-lines) {
        height: 100%;
        display: flex;
        flex-direction: column;
        box-sizing: border-box;
        min-height: calc(
            100dvh - var(--topbar-height) - env(safe-area-inset-top, 0px) - var(--bottom-nav-offset)
        );
        padding-bottom: 0;
        background: var(--surface);
    }

    .write-card.is-lines {
        display: flex;
        flex-direction: column;
        flex: 1;
        margin-left: calc(-1 * max(var(--space-4), env(safe-area-inset-left, 0px)));
        margin-right: calc(-1 * max(var(--space-4), env(safe-area-inset-right, 0px)));
        margin-bottom: 0;
        border-left: 0;
        border-right: 0;
        border-bottom: 0;
        border-radius: 0;
        padding-bottom: var(--space-4);
        background: var(--surface);
    }

    .draft-note {
        width: 100%;
        margin-right: 0;
    }
}

.line-dock-actions {
    display: flex;
    gap: var(--space-2);
}

.line-dock-actions .btn {
    flex: 1;
    min-height: var(--control-h-lg);
}
</style>
