<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import useAPI from "../composables/useAPI";

const { PostReport, PostReportPptx, GetReportDraft } = useAPI();
const router = useRouter();

const input = ref("");
const file = ref(null);
const buttonType = ref("text");
const today = new Date();
const date = ref(
    `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`,
);

const aiLoading = ref(false);

const getSelectedMemberId = () => {
    const value = localStorage.getItem("report-selectedUser");
    if (!value || value === "선택" || !/^\d+$/.test(value)) return null;
    const memberId = Number(value);
    return memberId > 0 ? memberId : null;
};

const loadDraft = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null || input.value.trim()) return;
    try {
        const draft = await GetReportDraft(memberId, date.value);
        input.value = draft.raw_text;
    } catch (error) {
        if (error.response?.status !== 404) {
            console.error("원문 초안 불러오기 실패:", error);
        }
    }
};

onMounted(loadDraft);
watch(date, loadDraft);

const selectType = (nextType) => {
    buttonType.value = nextType;
};

const uploadFile = (event) => {
    const selected = event.target.files?.[0] || null;
    if (selected && !selected.name.toLowerCase().endsWith(".pptx")) {
        alert("PPTX 파일만 업로드할 수 있습니다.");
        event.target.value = "";
        file.value = null;
        return;
    }
    file.value = selected;
};

const sendReport = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null) {
        alert("사용자 선택 화면에서 사용자를 먼저 선택해주세요.");
        return;
    }

    if (buttonType.value === "text") {
        if (!input.value.trim()) {
            alert("보고서 내용을 입력해주세요.");
            return;
        }
    } else if (!file.value) {
        alert("PPTX 파일을 선택해주세요.");
        return;
    }

    aiLoading.value = true;

    try {
        let parsed;
        let rawText;

        if (buttonType.value === "text") {
            rawText = input.value;
            parsed = await PostReport(
                { content: rawText },
                date.value,
                memberId,
            );
        } else {
            const res = await PostReportPptx(file.value, date.value, memberId);
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
        alert(
            detail ||
                "보고서 전송에 실패했습니다. 입력한 내용은 유지되니 다시 시도해주세요.",
        );
    } finally {
        aiLoading.value = false;
    }
};
</script>

<template>
    <div class="page">
        <div class="page-header">
            <div>
                <h1>보고서 작성</h1>
                <p class="page-subtitle">
                    오늘의 업무 내용을 자유롭게 작성하거나 PPTX를 올리면 AI가
                    항목별로 정리해줍니다
                </p>
            </div>
        </div>

        <div class="card">
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
                    {{ aiLoading ? "전송 중..." : "보내기" }}
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.form-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
}

.select-type-buttons {
    display: flex;
    gap: 8px;
}

.file-drop-area {
    border: 1px dashed var(--border);
    padding: 16px;
    border-radius: var(--radius-sm);
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.file-name {
    margin: 0;
    font-size: 13px;
    color: var(--text-h);
}

.select-type-btn.active {
    background: var(--accent-bg, #e8f0fe);
    border-color: var(--accent-border, #007bff);
    color: var(--text-h, #111);
}
</style>
