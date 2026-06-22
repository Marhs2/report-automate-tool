```vue
<template>
  <h1>분석 결과</h1>

  <div>
    <div v-if="reportData">
      <div
        v-for="(project, projectIndex) in reportData.projects"
        :key="project.projectName || projectIndex"
        class="projects-container"
      >
        <input :value="project.projectName" />

        <div class="completedTasks">
          <h2>완료된 업무</h2>
          <input
            v-if="project.completedTasks.length > 0"
            v-for="(task, taskIndex) in project.completedTasks"
            :key="`completed-${taskIndex}`"
            :value="task"
          />
          <div v-else>완료된 업무가 없습니다</div>
        </div>

        <div class="inProgressTasks">
          <h2>진행 중인 업무</h2>
          <input
            v-if="project.inProgressTasks.length > 0"
            v-for="(task, taskIndex) in project.inProgressTasks"
            :key="`progress-${taskIndex}`"
            :value="task"
          />
          <div v-else>진행 중인 업무가 없습니다</div>
        </div>

        <div class="issues">
          <h2>이슈</h2>
          <input
            v-if="project.issues.length > 0"
            v-for="(issue, issueIndex) in project.issues"
            :key="`issue-${issueIndex}`"
            :value="issue"
          />
          <div v-else>이슈가 없습니다</div>
        </div>

        <div class="requests">
          <h2>요청사항</h2>
          <input
            v-if="project.requests.length > 0"
            v-for="(request, requestIndex) in project.requests"
            :key="`request-${requestIndex}`"
            :value="request"
          />
          <div v-else>요청사항이 없습니다</div>
        </div>

        <div class="nextPlans">
          <h2>다음 계획</h2>
          <input
            v-if="project.nextPlans.length > 0"
            v-for="(plan, planIndex) in project.nextPlans"
            :key="`plan-${planIndex}`"
            :value="plan"
          />

          <div v-else>다음 계획이 없습니다</div>
        </div>

        <br />
      </div>

      <div>
        <button @click="saveReport">저장하기</button>
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
.projects-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.projects-container > div {
  display: flex;
  flex-direction: column;
  & > input {
    margin-bottom: 10px;
    padding: 5px;
    font-size: 16px;
  }
}
</style>
