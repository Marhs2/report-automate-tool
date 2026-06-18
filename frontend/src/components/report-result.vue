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
