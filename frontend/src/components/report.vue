<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import useAPI from "../composables/useAPI";

const { PostReport } = useAPI();
const router = useRouter();

const input = ref("");
const date = ref(new Date().toISOString().substring(0, 10));

const aiLoading = ref(false);

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
        sessionStorage.setItem("reportRaw", JSON.stringify(input.value));
        sessionStorage.setItem("reportDate", date.value);
        await router.push({ name: "report-result" });
    } catch (error) {
        console.error("보고서 전송 실패:", error);
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
