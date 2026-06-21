<template>
  <h1>분석 결과</h1>

  <div>

    <div v-if="reportData">

      <div class="report-section">
        <div v-for="project in reportData.projects" :key="project.projectName">
          <h2>{{ project.projectName }}</h2>

          <div>
            <h3>완료된 업무</h3>
            <ul>
              <li v-for="task in project.completedTasks" :key="task">{{ task }}</li>
            </ul>
          </div>

          <div>
            <h3>진행 중인 업무</h3>
            <ul>
              <li v-for="task in project.inProgressTasks" :key="task">{{ task }}</li>
            </ul>
          </div>

          <div>
            <h3>이슈</h3>
            <ul>
              <li v-for="issue in project.issues" :key="issue">{{ issue }}</li>
            </ul>
          </div>

          <div>
            <h3>요청사항</h3>
            <ul>
              <li v-for="request in project.requests" :key="request">{{ request }}</li>
            </ul>
          </div>

          <div>
            <h3>향후 계획</h3>
            <ul>
              <li v-for="plan in project.nextPlans" :key="plan">{{ plan }}</li>
            </ul>
          </div>

          <hr />
        </div>

        <div v-if="reportData.importantSummary">
          <h2>중요 요약</h2>
          <p>{{ reportData.importantSummary }}</p>
        </div>
      </div>

      <div class="raw-section">
        <h2>원본 보고서</h2>
        <div v-html="rawData"></div>
      </div>

    </div>


    <div v-else>
      <p>보고서 데이터가 없습니다. 보고서를 먼저 제출해주세요.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";


const reportData = ref(null);
const rawData = ref(null);

onMounted(() => {
  const stored = sessionStorage.getItem("reportData");

  if (stored) {
    reportData.value = JSON.parse(stored);
  }
  const storedRaw = sessionStorage.getItem("reportRaw");
  if (storedRaw) {
    rawData.value = storedRaw.replace(/\\n/g, "\n").replace(/^"(.*)"$/, "$1");
  }
  console.log("Loaded report data:", reportData.value);
});
</script>

<style scoped>
h1 {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 24px;
  color: #1f2937;
}

.report-section {
  max-width: 850px;
  margin: 0 auto;
}

.report-section h2 {
  font-size: 20px;
  font-weight: 600;
  color: #111827;
  margin: 28px 0 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e5e7eb;
}

.report-section > div > div {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 18px 22px;
  margin-bottom: 16px;
}

.report-section h3 {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  margin: 0 0 10px;
  color: #6b7280;
}

ul {
  margin: 0;
  padding-left: 18px;
}

li {
  line-height: 1.7;
  color: #374151;
  font-size: 14px;
}

hr {
  border: none;
  border-top: 1px solid #e5e7eb;
  margin: 28px 0;
}

.raw-section {
  max-width: 850px;
  margin: 0 auto;
}

.raw-section h2 {
  font-size: 20px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 14px;
}

.raw-section > div {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 22px;
  white-space: pre-wrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  line-height: 1.7;
  color: #374151;
}

p {
  line-height: 1.75;
  color: #374151;
  font-size: 14px;
}
</style>
