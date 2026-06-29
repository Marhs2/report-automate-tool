```vue
<template>
  <h1>분석 결과</h1>

  <div>
    <div v-if="reportData" class="content-container">
      <div class="json-container">
        <div v-for="(project, projectIndex) in reportData.projects" :key="project.projectName || projectIndex"
          class="projects-container">
          <input :value="project.projectName" />

          <div class="completedTasks">
            <h2>완료된 업무</h2>
            <input v-if="project.completedTasks.length > 0" v-for="(task, taskIndex) in project.completedTasks"
              :key="`completed-${taskIndex}`" :value="task" v-model="project.completedTasks[taskIndex]" />
            <div v-else>완료된 업무가 없습니다</div>
            <button @click="addCompletedTask(project)">+</button>
          </div>

          <div class="inProgressTasks">
            <h2>진행 중인 업무</h2>
            <input v-if="project.inProgressTasks.length > 0" v-for="(task, taskIndex) in project.inProgressTasks"
              :key="`progress-${taskIndex}`" :value="task" v-model="project.inProgressTasks[taskIndex]" />

            <div v-else>진행 중인 업무가 없습니다</div>

            <button @click="addInProgressTask(project)">+</button>
          </div>

          <div class="issues">
            <h2>이슈</h2>
            <input v-if="project.issues.length > 0" v-for="(issue, issueIndex) in project.issues"
              :key="`issue-${issueIndex}`" :value="issue" v-model="project.issues[issueIndex]" />
            <div v-else>이슈가 없습니다</div>
            <button @click="addIssue(project)">+</button>
          </div>

          <div class="requests">
            <h2>요청사항</h2>
            <input v-if="project.requests.length > 0" v-for="(request, requestIndex) in project.requests"
              :key="`request-${requestIndex}`" :value="request" v-model="project.requests[requestIndex]" />
            <div v-else>요청사항이 없습니다</div>
            <button @click="addRequest(project)">+</button>
          </div>

          <div class="nextPlans">
            <h2>다음 계획</h2>
            <input v-if="project.nextPlans.length > 0" v-for="(plan, planIndex) in project.nextPlans"
              :key="`plan-${planIndex}`" :value="plan" v-model="project.nextPlans[planIndex]" />

            <div v-else>다음 계획이 없습니다</div>
            <button @click="addNextPlan(project)">+</button>
          </div>

          <br />
        </div>

        <div>
          <input type="text" v-model="memberId" placeholder="회원 ID를 입력하세요" />
          <button @click="saveReport">저장하기</button>
        </div>
      </div>

      <div class="raw-container">
        <h2>원본 보고서</h2>
        <pre class="raw-content">{{ rawData }}</pre>
      </div>
    </div>

    <div v-else>
      <p>보고서 데이터가 없습니다. 보고서를 먼저 제출해주세요.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import useAPI from "../composables/useAPI";

const reportData = ref(null);
const rawData = ref(null);
const memberId = ref("");
const { PostSaveReport } = useAPI();

watch(reportData, (newVal) => {
  if (newVal) {
    sessionStorage.setItem("reportData", JSON.stringify(newVal));
  }
}, { deep: true });

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


const addCompletedTask = (project) => {
  project.completedTasks.push("");
};

const addInProgressTask = (project) => {
  project.inProgressTasks.push("");
};

const addIssue = (project) => {
  project.issues.push("");
};

const addRequest = (project) => {
  project.requests.push("");
};

const addNextPlan = (project) => {
  project.nextPlans.push("");
};



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
/* 전체 레이아웃 (편집기와 원본 보고서 좌우 정렬) */
.content-container {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  box-sizing: border-box;
}

/* 왼쪽 편집 폼 영역 */
.json-container {
  flex: 2;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 오른쪽 원본 보고서 영역 (스크롤 고정) */
.raw-container {
  flex: 1;
  position: sticky;
  top: 20px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 20px;
}

.raw-container h2 {
  font-size: 16px;
  margin-top: 0;
  margin-bottom: 12px;
  color: #334155;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 8px;
}

.raw-container pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
  line-height: 1.5;
  max-height: 80vh;
  overflow-y: auto;
  color: #475569;
}

/* 개별 프로젝트 카드 */
.projects-container {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

/* 프로젝트명 입력창 */
.projects-container>input {
  width: 100%;
  font-size: 18px;
  font-weight: bold;
  padding: 10px;
  margin-bottom: 20px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  box-sizing: border-box;
}

/* 각 업무/이슈/요청/계획 박스 레이아웃 */
.projects-container>div {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
  border: 1px solid #f1f5f9;
  background: #f8fafc;
  padding: 16px;
  border-radius: 8px;
}

.projects-container>div h2 {
  font-size: 14px;
  margin: 0 0 8px 0;
  color: #334155;
}

/* 박스 내부의 입력란 */
.projects-container>div>input {
  padding: 8px 12px;
  font-size: 14px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  width: 100%;
  box-sizing: border-box;
}

/* 추가 (+) 버튼 */
.projects-container>div>button {
  align-self: flex-start;
  padding: 6px 16px;
  font-size: 14px;
  cursor: pointer;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  transition: background 0.15s;
}


/* 하단 저장 영역 및 회원 ID 입력란 */
.json-container>div:last-child {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 16px;
  border-top: 1px solid #e2e8f0;
}

.json-container>div:last-child input[type="text"] {
  flex: 1;
  padding: 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
}

.json-container>div:last-child button {
  padding: 10px 20px;
  background: #0f172a;
  color: #ffffff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  white-space: nowrap;
}

.json-container>div:last-child button:hover {
  background: #1e293b;
}
</style>