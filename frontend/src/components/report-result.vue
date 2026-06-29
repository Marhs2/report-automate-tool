```vue
<template>
  <h1>분석 결과</h1>

  <div>
    <div v-if="reportData" class="content-container">
      <div class="json-container">
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
              v-model="project.completedTasks[taskIndex]"
            />
            <div v-else>완료된 업무가 없습니다</div>
            <button @click="addCompletedTask(project)">+</button>
          </div>

          <div class="inProgressTasks">
            <h2>진행 중인 업무</h2>
            <input
              v-if="project.inProgressTasks.length > 0"
              v-for="(task, taskIndex) in project.inProgressTasks"
              :key="`progress-${taskIndex}`"
              :value="task"
              v-model="project.inProgressTasks[taskIndex]"
            />

            <div v-else>진행 중인 업무가 없습니다</div>

            <button @click="addInProgressTask(project)">+</button>
          </div>

          <div class="issues">
            <h2>이슈</h2>
            <input
              v-if="project.issues.length > 0"
              v-for="(issue, issueIndex) in project.issues"
              :key="`issue-${issueIndex}`"
              :value="issue"
              v-model="project.issues[issueIndex]"
            />
            <div v-else>이슈가 없습니다</div>
            <button @click="addIssue(project)">+</button>
          </div>

          <div class="requests">
            <h2>요청사항</h2>
            <input
              v-if="project.requests.length > 0"
              v-for="(request, requestIndex) in project.requests"
              :key="`request-${requestIndex}`"
              :value="request"
              v-model="project.requests[requestIndex]"
            />
            <div v-else>요청사항이 없습니다</div>
            <button @click="addRequest(project)">+</button>
          </div>

          <div class="nextPlans">
            <h2>다음 계획</h2>
            <input
              v-if="project.nextPlans.length > 0"
              v-for="(plan, planIndex) in project.nextPlans"
              :key="`plan-${planIndex}`"
              :value="plan"
              v-model="project.nextPlans[planIndex]"
            />

            <div v-else>다음 계획이 없습니다</div>
            <button @click="addNextPlan(project)">+</button>
          </div>

          <br />
        </div>

        <div>
          <input
            type="text"
            v-model="memberId"
            placeholder="회원 ID를 입력하세요"
          />
          <button @click="saveReport">저장하기</button>
        </div>
      </div>

      <div class="raw-container">
        <h2>원본 보고서</h2>
        <pre>{{ rawData }}</pre>
      </div>
    </div>

    <div v-else>
      <p>보고서 데이터가 없습니다. 보고서를 먼저 제출해주세요.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import useAPI from "../composables/useAPI";

const reportData = ref(null);
const rawData = ref(null);
const memberId = ref("");
const { PostSaveReport } = useAPI();

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

const saveReport = () => {
  if (reportData.value) {
    const jsonData = JSON.stringify(reportData.value, null, 2);

    PostSaveReport(jsonData, rawData.value, parseInt(memberId.value))
      .then((response) => {
        console.log("보고서 저장 성공:", response);
        alert("보고서가 성공적으로 저장되었습니다.");
      })
      .catch((error) => {
        console.error("보고서 저장 실패:", error);
        alert("보고서 저장에 실패했습니다. 다시 시도해주세요.");
      });
  }
};
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

.content-container {
  display: flex;
}
</style>
