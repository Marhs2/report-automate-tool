<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import useAPI from "../composables/useAPI";

const { PostReport, GetReportDraft } = useAPI();
const router = useRouter();

const input = ref("");
const today = new Date();
const date = ref(
    `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`
);

const aiLoading = ref(false);

const loadDraft = async () => {
    const memberId = localStorage.getItem("report-selectedUser");
    if (!memberId || input.value.trim()) return;
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

const sendReport = async () => {
    aiLoading.value = true;

    try {
        const res = await PostReport(
            { content: input.value },
            date.value,
            localStorage.getItem("report-selectedUser"),
        );
        console.log("보고서 전송 성공:", res);

        sessionStorage.setItem("reportData", JSON.stringify(res));
        // 원문은 문자열 그대로 보관한다. JSON.stringify 후 정규식으로 되돌리면
        // 개행이 섞인 텍스트에서 앞뒤 따옴표가 남는다.
        sessionStorage.setItem("reportRaw", input.value);
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
                    오늘의 업무 내용을 자유롭게 작성하면 AI가 항목별로
                    정리해줍니다
                </p>
            </div>
        </div>

        <div class="card">
            <div class="field">
                <label for="date">날짜</label>
                <input type="date" id="date" v-model="date" />
            </div>
            <div class="field">
                <label for="report-input">업무 내용</label>
                <textarea
                    id="report-input"
                    v-model="input"
                    placeholder="보고서 내용을 입력하세요"
                    rows="16"
                    class="textarea"
                ></textarea>
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
</style>
