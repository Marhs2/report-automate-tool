<script setup>
import { onMounted, ref } from "vue";
import useAPI from "../composables/useAPI";

const { GetReports } = useAPI();
const reports = ref([]);
const isLoading = ref(false);
const getReports = async () => {
  isLoading.value = true;
  try {
    const response = await GetReports();
    reports.value = response;
    console.log("Reports:", response);
  } catch (error) {
    console.error("Error fetching reports:", error);
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  getReports();
});
</script>

<template>
  <div>
    <h2>Reports List</h2>
    <div class="reports-container">
      <div v-for="report in reports" :key="report.id" class="report-item">
        <h3>Report ID: {{ report.id }}</h3>
        <div>Member ID: {{ report.member_id }}</div>
        <div>Report Date: {{ report.report_date }}</div>
        <ul>
          <li v-for="(item, index) in report.parsed_json.projects" :key="index">
            {{ item }}
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>
