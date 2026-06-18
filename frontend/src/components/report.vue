<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import useAPI from "../composables/useAPI";

const { PostReport } = useAPI();
const router = useRouter();

const input = ref("");
const aiLoading = ref(false);

const sendReport = async () => {
  aiLoading.value = true;

  try {
    const res = await PostReport({ content: input.value });
    console.log("보고서 전송 성공:", res);

    await router.push({
      name: "report-result",
      state: {
        reportData: res,
      },
    });
  } catch (error) {
    console.error("보고서 전송 실패:", error);
  } finally {
    aiLoading.value = false;
  }
};
</script>

<template>
  <textarea v-model="input" placeholder="보고서 내용을 입력하세요"></textarea>

  <button @click="sendReport" :disabled="aiLoading">
    {{ aiLoading ? "전송 중..." : "보내기" }}
  </button>
</template>
