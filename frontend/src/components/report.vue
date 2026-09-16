<script setup>
import { computed, ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { useToast } from "../composables/useToast";

const { postReport, postReportPptx, getReportDraft, getUserActivities, getUsers } =
    useApi();
const router = useRouter();
const { error: toastError } = useToast();

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

const getSelectedMemberId = () => {
    const value = selectedUserId.value;
    if (value === null || value === undefined || value === "선택") return null;
    const memberId = Number(value);
    return Number.isInteger(memberId) && memberId > 0 ? memberId : null;
};

const hasUser = computed(() => getSelectedMemberId() !== null);

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

const refreshMeta = async () => {
    await loadUserName();
    await loadSavedState();
};

onMounted(async () => {
    await refreshMeta();
    await loadDraft();
});
watch(date, async () => {
    await loadSavedState();
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
        toastError(message);
    } finally {
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

        <div v-if="!hasUser" class="card">
     
            <div class="form-actions">
                <router-link class="btn btn-primary" to="/users"
                    >사용자 선택</router-link
                >
            </div>
        </div>

        <div v-else class="card">
            <div class="field">
                <label for="date">날짜</label>
                <input type="date" id="date" v-model="date" required />
            </div>

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

            <div v-if="buttonType === 'text'" class="field">
                <label for="report-input">업무 내용</label>
                <textarea
                    id="report-input"
                    v-model="input"
                    placeholder="보고서 내용을 입력하세요"
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

            <div class="form-actions">
                <button
                    class="btn btn-primary"
                    @click="sendReport"
                    :disabled="aiLoading"
                >
                    {{ aiLoading ? "정리 중..." : "AI로 정리하기" }}
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
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
</style>
