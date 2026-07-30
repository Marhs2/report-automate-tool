<script setup>
import { onMounted, ref, computed } from "vue";
import useAPI from "../composables/useApi";
import {
  CheckCircle2,
  CircleDot,
  AlertTriangle,
  MessageSquare,
  ArrowRightCircle,
  Calendar,
  User,
  FolderOpen,
} from "lucide-vue-next";

const { getProjectNames, getProjectTimeline, getUsers } = useAPI();

const projectNames = ref([]);
const users = ref([]);
const timeline = ref([]);
const selectedProject = ref("");
const selectedMember = ref("");
const isLoading = ref(false);
const isLoadingTimeline = ref(false);

const fetchInitialData = async () => {
  isLoading.value = true;
  try {
    const [names, userList] = await Promise.all([
      getProjectNames(),
      getUsers(),
    ]);
    projectNames.value = names;
    users.value = userList;
  } catch (error) {
    console.error("Error fetching initial data:", error);
  } finally {
    isLoading.value = false;
  }
};

const fetchTimeline = async () => {
  if (!selectedProject.value) {
    timeline.value = [];
    return;
  }
  isLoadingTimeline.value = true;
  try {
    const memberId = selectedMember.value || undefined;
    const data = await getProjectTimeline(selectedProject.value, memberId);
    timeline.value = data;
  } catch (error) {
    console.error("Error fetching timeline:", error);
    timeline.value = [];
  } finally {
    isLoadingTimeline.value = false;
  }
};

const groupedByDate = computed(() => {
  const groups = {};
  for (const entry of timeline.value) {
    if (!groups[entry.date]) {
      groups[entry.date] = [];
    }
    groups[entry.date].push(entry);
  }
  // 최신 날짜가 위에 오도록 역순 정렬
  const sorted = Object.entries(groups).sort(([a], [b]) => b.localeCompare(a));
  return sorted;
});

const totalDays = computed(() => groupedByDate.value.length);
const totalEntries = computed(() => timeline.value.length);

onMounted(() => {
  fetchInitialData();
});
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>프로젝트별 타임라인</h1>
        <p class="page-subtitle">
          프로젝트를 선택하면 시간순으로 보고 이력을 조회합니다
        </p>
      </div>
    </div>

    <!-- 필터 영역 -->
    <div class="toolbar">
      <select
        v-model="selectedProject"
        class="input filter-select"
        @change="fetchTimeline"
      >
        <option value="">프로젝트 선택</option>
        <option v-for="name in projectNames" :key="name" :value="name">
          {{ name }}
        </option>
      </select>

      <select
        v-model="selectedMember"
        class="input filter-select"
        @change="fetchTimeline"
      >
        <option value="">전체 멤버</option>
        <option v-for="user in users" :key="user.id" :value="user.id">
          {{ user.name }}
        </option>
      </select>
    </div>

    <!-- 로딩 -->
    <div v-if="isLoading" class="empty-state">데이터를 불러오는 중...</div>

    <!-- 프로젝트 미선택 -->
    <div v-else-if="!selectedProject" class="empty-state">
      <FolderOpen :size="32" style="margin-bottom: 8px; opacity: 0.5" />
      <p>프로젝트를 선택해주세요</p>
    </div>

    <!-- 타임라인 로딩 -->
    <div v-else-if="isLoadingTimeline" class="empty-state">
      타임라인을 불러오는 중...
    </div>

    <!-- 결과 없음 -->
    <div v-else-if="timeline.length === 0" class="empty-state">
      해당 프로젝트의 보고 이력이 없습니다
    </div>

    <!-- 타임라인 표시 -->
    <div v-else class="timeline-container">
      <div class="timeline-summary">
        <span class="summary-badge">
          <Calendar :size="14" />
          {{ totalDays }}일
        </span>
        <span class="summary-badge">
          <User :size="14" />
          {{ totalEntries }}건 보고
        </span>
      </div>

      <div class="timeline">
        <div
          v-for="([date, entries], idx) in groupedByDate"
          :key="date"
          class="timeline-day"
        >

          <div class="timeline-content">
            <div class="date-header">
              <span class="date-text">{{ date }}</span>
              <span class="date-count">{{ entries.length }}건</span>
            </div>

            <div
              v-for="(entry, eIdx) in entries"
              :key="eIdx"
              class="card timeline-card"
            >
              <div class="entry-meta">
                <User :size="13" />
                <span>{{ entry.member_name }}</span>
              </div>

              <div class="detail-list">
                <!-- 완료된 업무 -->
                <div
                  v-if="entry.completedTasks && entry.completedTasks.length"
                  class="detail-row"
                >
                  <div class="detail-label tone-completed">
                    <CheckCircle2 :size="14" />
                    <span>완료</span>
                  </div>
                  <div class="detail-content">
                    <ul>
                      <li v-for="(task, i) in entry.completedTasks" :key="i">
                        {{ task }}
                      </li>
                    </ul>
                  </div>
                </div>

                <!-- 진행 중 -->
                <div
                  v-if="entry.inProgressTasks && entry.inProgressTasks.length"
                  class="detail-row"
                >
                  <div class="detail-label tone-in-progress">
                    <CircleDot :size="14" />
                    <span>진행중</span>
                  </div>
                  <div class="detail-content">
                    <ul>
                      <li v-for="(task, i) in entry.inProgressTasks" :key="i">
                        {{ task }}
                      </li>
                    </ul>
                  </div>
                </div>

                <!-- 이슈 -->
                <div
                  v-if="entry.issues && entry.issues.length"
                  class="detail-row"
                >
                  <div class="detail-label tone-issues">
                    <AlertTriangle :size="14" />
                    <span>이슈</span>
                  </div>
                  <div class="detail-content">
                    <ul>
                      <li v-for="(issue, i) in entry.issues" :key="i">
                        <span>{{ issue.content || issue }}</span>
                        <span
                          v-if="issue.status"
                          :class="[
                            'status-badge',
                            issue.status === '해결'
                              ? 'status-resolved'
                              : 'status-unresolved',
                          ]"
                        >
                          {{ issue.status }}
                        </span>
                      </li>
                    </ul>
                  </div>
                </div>

                <!-- 요청사항 -->
                <div
                  v-if="entry.requests && entry.requests.length"
                  class="detail-row"
                >
                  <div class="detail-label tone-request">
                    <MessageSquare :size="14" />
                    <span>요청</span>
                  </div>
                  <div class="detail-content">
                    <ul>
                      <li v-for="(req, i) in entry.requests" :key="i">
                        {{ req }}
                      </li>
                    </ul>
                  </div>
                </div>

                <!-- 다음 계획 -->
                <div
                  v-if="entry.nextPlans && entry.nextPlans.length"
                  class="detail-row"
                >
                  <div class="detail-label tone-next-plans">
                    <ArrowRightCircle :size="14" />
                    <span>계획</span>
                  </div>
                  <div class="detail-content">
                    <ul>
                      <li v-for="(plan, i) in entry.nextPlans" :key="i">
                        {{ plan }}
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filter-select {
  width: auto;
  min-width: 200px;
}

.timeline-summary {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.summary-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  font-size: 13px;
  font-weight: 500;
  border-radius: 999px;
  background: var(--accent-bg);
  color: var(--accent);
}

.timeline {
  position: relative;
}

.timeline-day {
  display: flex;
  gap: 20px;
  padding-bottom: 32px;
}

.timeline-day:last-child {
  padding-bottom: 0;
}

.timeline-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 20px;
  padding-top: 6px;
}

.marker-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--bg);
  box-shadow: 0 0 0 2px var(--accent);
  flex-shrink: 0;
}

.marker-line {
  flex: 1;
  width: 2px;
  background: var(--border);
  margin-top: 6px;
}

.timeline-content {
  flex: 1;
  min-width: 0;
}

.date-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.date-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-h);
}

.date-count {
  font-size: 12px;
  color: var(--text);
  background: var(--bg-soft);
  padding: 2px 8px;
  border-radius: 999px;
}

.timeline-card {
  padding: 14px 18px;
  margin-bottom: 10px;
}

.timeline-card:last-child {
  margin-bottom: 0;
}

.entry-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text);
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.detail-list {
  display: flex;
  flex-direction: column;
}

.detail-row {
  display: flex;
  gap: 12px;
  padding: 6px 0;
}

.detail-row + .detail-row {
  border-top: 1px solid var(--border);
}

.detail-label {
  flex: 0 0 80px;
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-h);
}

.tone-completed {
  color: var(--success);
}
.tone-in-progress {
  color: var(--accent);
}
.tone-issues {
  color: var(--danger);
}
.tone-request {
  color: var(--warning);
}
.tone-next-plans {
  color: #14b8a6;
}

.detail-content {
  flex: 1;
  min-width: 0;
}

.detail-content ul {
  margin: 0;
  padding-left: 16px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text);
}

.detail-content li {
  list-style: disc;
}

.status-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.status-resolved {
  border: 1px solid var(--success);
  color: var(--success);
}

.status-unresolved {
  border: 1px solid var(--danger);
  color: var(--danger);
}
</style>
