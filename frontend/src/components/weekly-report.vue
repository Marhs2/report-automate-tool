<script setup>
import { onMounted, ref } from "vue";
import useAPI from "../composables/useApi";
import PizZip from "pizzip";
import Docxtemplater from "docxtemplater";
import { saveAs } from "file-saver";

const { postWeekly, GetWeeklyReport } = useAPI();

const selects = ref([]);
const userId = ref();
const weeklyReport = ref(null);
const isLoading = ref(false);

const date = new Date();
const day = date.getDay();
const getThisWeek = () => {
  const diffToMonday = date.getDate() - (day === 0 ? 7 : day) + 1;
  const monday = new Date(date.setDate(diffToMonday));

  const formatDate = (d) => d.toISOString().split("T")[0];
  return {
    monday: formatDate(monday),
  };
};

const sendDates = async () => {
  isLoading.value = true;
  const response = await postWeekly(userId.value, selects.value);
  console.log(response);
  await fetchWeeklyReport();
  isLoading.value = false;
};

const { monday } = getThisWeek();

const fetchWeeklyReport = async () => {
  isLoading.value = true;
  const response = await GetWeeklyReport();
  weeklyReport.value = response;
  isLoading.value = false;
};

const downloadReport = async (report) => {
  try {
    isLoading.value = true;

    // 1. Fetch the docx template as an array buffer.
    const response = await fetch("/asset/주간_요약보고서_템플릿.docx");
    if (!response.ok) {
      throw new Error("템플릿 파일을 찾을 수 없습니다.");
    }
    const arrayBuffer = await response.arrayBuffer();

    // 2. Load the binary content into PizZip
    const zip = new PizZip(arrayBuffer);

    // 3. Initialize Docxtemplater
    const doc = new Docxtemplater(zip, {
      paragraphLoop: true,
      linebreaks: true,
    });

    // 4. Formulate the data object for Docxtemplater
    const sortedDates = [...(report.selectedDate || [])].sort();
    const period_start = sortedDates[0] || "";
    const period_end = sortedDates[sortedDates.length - 1] || "";
    
    const createdDateRaw = report.createdAt || report.created_at || new Date().toISOString();
    const created_date = new Date(createdDateRaw).toISOString().split("T")[0];

    const projectsList = (report.report?.projects || []).map((p) => ({
      project_name: p.projectName || "",
      completed: p.completedTasks || [],
      inProgress: p.inProgressTasks || [],
      issues: (p.issues || []).map((issue) => {
        if (typeof issue === "string") {
          return {
            content: issue,
            resolved: false,
          };
        }
        return {
          content: issue.content || "",
          resolved: issue.status === "해결",
        };
      }),
      nextPlans: p.nextWeekPlans || p.nextPlans || [],
    }));

    const project_count = projectsList.length;

    // Default missing members list to empty
    const missing = [];
    const missing_count = missing.length;

    const data = {
      period_start,
      period_end,
      created_date,
      project_count,
      missing_count,
      projects: projectsList,
      missing,
    };

    // Render the document with the data
    doc.render(data);

    // Get the generated zip content as blob
    const out = doc.getZip().generate({
      type: "blob",
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });

    // Generate filename based on member name and date range
    const memberName = report.memberName || `사용자_${report.memberId}`;
    const filename = `주간요약보고서_${memberName}_${period_start}~${period_end}.docx`;

    // Save the file using file-saver
    saveAs(out, filename);
  } catch (error) {
    console.error("보고서 다운로드 실패:", error);
    alert("보고서 다운로드 중 오류가 발생했습니다: " + error.message);
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchWeeklyReport);
</script>

<template>
  <div>
    <ul v-for="day in 7">
      <li>
        {{
          new Date(
            new Date(monday).setDate(new Date(monday).getDate() + (day - 1)),
          )
            .toISOString()
            .split("T")[0]
        }}
      </li>
      <li>
        <input
          type="checkbox"
          v-model="selects"
          :value="
            new Date(
              new Date(monday).setDate(new Date(monday).getDate() + (day - 1)),
            )
              .toISOString()
              .split('T')[0]
          "
        />
      </li>
    </ul>

    <ul>
      <input type="number" placeholder="user Id" v-model="userId" />
      <button v-on:click="() => sendDates()" :disabled="isLoading">
        {{ isLoading ? "로딩 중..." : "주간 보고서 생성" }}
      </button>
    </ul>
  </div>

  <div>
    <h2>주간 보고서 다운로드</h2>
    <ul>
      <li v-for="(report, index) in weeklyReport" :key="index" style="margin-bottom: 20px; border-bottom: 1px solid #ccc; padding-bottom: 10px; width: 100%;">
        <div>사용자: {{ report.memberName || report.memberId }}</div>
        <div>선택요일: {{ report.selectedDate?.join(', ') }}</div>
        <ul v-for="data in report.report?.projects" :key="data.projectName">
          <li>- {{ data.projectName }}</li>
        </ul>
        <button v-on:click="() => downloadReport(report)" :disabled="isLoading">다운로드</button>
      </li>
    </ul>
  </div>
</template>

<style>
li,
ul {
  list-style: none;
}
ul {
  display: flex;
  align-items: center;
}
</style>
