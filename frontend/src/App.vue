<script setup>
import { onMounted, ref } from "vue";
import useAPI from "./composables/useAPI";
const { PostReport } = useAPI();


const input = ref("");
const aiLoading = ref(false);

const sendReport = async () => {
  aiLoading.value = true;
  try {
    const response = await PostReport({ content: input.value }).then((res) => {
      console.log("보고서 전송 성공:", res);
      aiLoading.value = false;
    });

  } catch (error) {
    console.error("보고서 전송 실패:", error);
    aiLoading.value = false;
  }
};



</script>

<template>


  <textarea v-model="input" placeholder="보고서 내용을 입력하세요"></textarea>

  <button @click="sendReport" :disabled="aiLoading">
    {{ aiLoading ? "전송 중..." : "보내기" }}
  </button>


  <div>

  </div>


</template>
