<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from "vue";
import { useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { useDialog } from "../composables/useDialog";
import AppField from "./ui/AppField.vue";
import { PASTE_TEMPLATES, applyTemplate, templateById } from "../lib/reportTemplates";

const {
    postReport,
    postReportPptx,
    getReportDraft,
    getUserActivities,
    getUsers,
    getReports,
} = useApi();
const router = useRouter();
const { alert: showAlert } = useDialog();

const input = ref("");
const file = ref(null);
const buttonType = ref("text");
const today = new Date();
const date = ref(
    `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`,
);

const aiLoading = ref(false);
const formError = ref("");
const userName = ref("");
const alreadySaved = ref(false);
const elapsed = ref(0);
const prevPlans = ref([]);
const prevPlansDate = ref("");
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

const insertTemplate = (template) => {
    activeTemplateId.value = template?.id || "";
    input.value = applyTemplate("", template);
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
    await loadSavedState();
    await loadPrevPlans();
    await loadDraft();
});
watch(selectedUserId, refreshMeta);

const selectType = (nextType) => {
    buttonType.value = nextType;
};

const uploadFile = (event) => {
    const selected = event.target.files?.[0] || null;
    if (selected && !selected.name.toLowerCase().endsWith(".pptx")) {
        formError.value = "PPTX 파일만 업로드할 수 있습니다.";
        event.target.value = "";
        file.value = null;
        return;
    }
    formError.value = "";
    file.value = selected;
};

const sendReport = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null) {
        formError.value = "왼쪽 아래에서 사용자를 먼저 선택해주세요.";
        router.push("/users");
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
        <div class="status-banner">
            <span
                >작성자 <strong>{{ userName || "미선택" }}</strong></span
            >
            <span
                >날짜 <strong>{{ date }}</strong></span
            >
            <span
                v-if="alreadySaved"
                class="status-chip is-saved"
                >이 날짜 저장됨</span
            >
            <span v-else class="status-chip is-draft">아직 저장 전</span>
        </div>
        <p v-if="alreadySaved" class="form-hint">
            이 날짜에 저장된 보고가 있어요. 다시 정리해 저장하면 기존 보고를
            덮어씁니다.
        </p>

        <div v-if="!hasUser" class="card">
     
            <div class="form-actions">
                <router-link class="btn btn-primary" to="/users"
                    >사용자 선택</router-link
                >
            </div>
        </div>

        <div v-else class="card">
            <AppField label="날짜" for-id="date">
                <input type="date" id="date" v-model="date" required />
            </AppField>

            <div class="field">
                <label>보고서 유형</label>
                <div
                    class="select-type-buttons"
                    role="group"
                    aria-label="보고서 유형"
                >
                    <button
                        type="button"
                        class="btn select-type-btn"
                        :class="{ active: buttonType === 'text' }"
                        @click="selectType('text')"
                    >
                        텍스트
                    </button>
                    <button
                        type="button"
                        class="btn select-type-btn"
                        :class="{ active: buttonType === 'file' }"
                        @click="selectType('file')"
                    >
                        파일
                    </button>
                </div>
            </div>

            <div v-if="prevPlans.length" class="prev-plans">
                <div class="prev-plans-head">
                    <p class="prev-plans-title">
                        <strong>{{ prevPlansDate }}</strong> 보고의 다음
                        계획이에요. 오늘 끝낸 일과 겹치면 입력란에 넣으세요.
                    </p>
                    <button
                        type="button"
                        class="btn btn-small"
                        @click="insertPrevPlans"
                    >
                        입력란에 추가
                    </button>
                </div>
                <ul class="prev-plans-list">
                    <li v-for="(item, index) in prevPlans" :key="index">
                        <span class="prev-plans-project">{{
                            item.project
                        }}</span>
                        {{ item.text }}
                    </li>
                </ul>
            </div>

            <div v-if="buttonType === 'text'" class="field">
                <label for="report-input">{{ activeTemplate?.label || "어제 / 오늘 / 막힌 것" }}</label>
                <div class="template-chips" role="group" aria-label="붙여넣기 칸">
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
                <textarea
                    id="report-input"
                    v-model="input"
                    :placeholder="activeTemplate?.hint || '어제 한 일, 오늘 할 일, 막힌 것을 붙여넣으세요. 요청은 [지시/건의] 칸을 쓰세요.'"
                    rows="16"
                    class="textarea"
                ></textarea>
            </div>

            <div v-else class="field file-drop-area">
                <label for="pptx-input">PPTX 파일</label>
                <input
                    id="pptx-input"
                    type="file"
                    accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    @change="uploadFile"
                />
                <p v-if="file" class="file-name">{{ file.name }}</p>
            </div>

            <p v-if="formError" class="form-error" role="alert">
                {{ formError }}
            </p>
            <div v-if="aiLoading" class="ai-progress" role="status">
                <p class="ai-progress-title">
                    로컬 AI가 보고서를 구조화하고 있어요 ·
                    {{ elapsedLabel }} 경과
                </p>
                <p class="ai-progress-help">
                    보통 1~3분, 최대 10분까지 걸릴 수 있어요. 완료될
                    때까지 이 화면을 유지해주세요. 입력한 내용은
                    유지됩니다.
                </p>
            </div>
            <div class="form-actions">
                <button
                    class="btn btn-primary"
                    @click="sendReport"
                    :disabled="aiLoading"
                >
                    {{ aiLoading ? `정리 중... (${elapsedLabel})` : "AI로 일일 업무 일지" }}
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.template-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
}

.template-chips .on {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--text-strong);
}

.form-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: var(--space-4);
}

.form-error {
    margin-top: var(--space-3);
    color: var(--danger-fg);
    font-size: var(--fs-13);
}

.form-hint {
    margin-top: var(--space-3);
    font-size: var(--fs-13);
    color: var(--text);
}

.select-type-buttons {
    display: flex;
    gap: var(--space-2);
}

.file-drop-area {
    border: 1px dashed var(--border);
    padding: var(--space-5);
    border-radius: var(--radius-sm);
    background: var(--bg);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    transition:
        border-color var(--dur-fast) var(--ease),
        background var(--dur-fast) var(--ease);
}

.file-drop-area:hover,
.file-drop-area:focus-within {
    border-color: var(--accent-border);
}

.file-drop-area > input[type="file"] {
    padding: 0;
    border: none;
    background: transparent;
}

.file-name {
    margin: 0;
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.select-type-btn.active,
.select-type-btn.active:hover {
    background: var(--accent-soft);
    border-color: var(--accent-border);
    color: var(--accent);
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

.prev-plans {
    margin-bottom: var(--space-4);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-sm);
    background: var(--surface-soft);
}

.prev-plans-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
}

.prev-plans-title {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text);
}

.prev-plans-list {
    margin: var(--space-2) 0 0;
    padding-left: var(--space-4);
    font-size: var(--fs-13);
    color: var(--text-strong);
}

.prev-plans-project {
    font-weight: var(--fw-semibold);
}

.write-hint {
    margin-top: var(--space-3);
    font-size: var(--fs-13);
    color: var(--text);
}

.write-hint summary {
    cursor: pointer;
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.write-hint ul {
    margin: var(--space-2) 0 0;
    padding-left: var(--space-4);
}
</style>
