<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

const reportData = computed(() => route.state?.reportData || null);
</script>

<template>
  <h1>분석 결과</h1>

  <div>
    <pre>{{ JSON.stringify(reportData, null, 2) }}</pre>
  </div>
</template>
