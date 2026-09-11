<script setup>
import { onMounted, ref, computed } from "vue";
import { useRouter } from "vue-router";
import useAPI from "../composables/useApi";

const router = useRouter();
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

const selectedMemberName = computed(() => {
  const found = users.value.find(
    (user) => String(user.id) === String(selectedMember.value),
  );
  return found?.name || "";
});

const formatDate = (value) => {
  const [year, month, day] = String(value).split("-");
  if (!year || !month || !day) return value;
  return `${year}.${month}.${day}`;
};

const itemText = (value) =>
  value && typeof value === "object"
    ? (value.content ?? "")
    : String(value ?? "");

const statusOf = (value) =>
  value && typeof value === "object" ? value.status || "" : "";

const visibleSections = (entry) =>
  [
    {
      key: "completed",
      label: "완료된 업무",
      items: entry.completedTasks || [],
    },
    {
      key: "progress",
      label: "진행 중인 업무",
      items: entry.inProgressTasks || [],
    },
    {
      key: "issues",
      label: "이슈",
      items: entry.issues || [],
    },
    {
      key: "requests",
      label: "요청사항",
      items: entry.requests || [],
    },
    {
      key: "plans",
      label: "다음 계획",
      items: entry.nextPlans || [],
    },
  ].filter((section) => Array.isArray(section.items) && section.items.length);

const onProjectChange = () => {
  selectedMember.value = "";
  fetchTimeline();
};

const openEntry = (entry) => {
  if (!entry?.report_id) return;
  router.push(`/report/${entry.report_id}`);
};

const clearMemberFilter = () => {
  selectedMember.value = "";
  fetchTimeline();
};

onMounted(() => {
  fetchInitialData();
});
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>프로젝트 흐름</h1>
        <p class="page-subtitle">
          프로젝트를 선택하면 시간순으로 보고 이력을 조회합니다
        </p>
      </div>
    </div>

    <!-- 필터 영역 -->
    <div class="toolbar">
      <div class="field">
        <label for="timeline-project">프로젝트</label>
        <select
          id="timeline-project"
          v-model="selectedProject"
          class="input filter-select"
          @change="onProjectChange"
        >
          <option value="">프로젝트 선택</option>
          <option v-for="name in projectNames" :key="name" :value="name">
            {{ name }}
          </option>
        </select>
      </div>

      <div class="field">
        <label for="timeline-member">멤버</label>
        <select
          id="timeline-member"
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
    </div>

    <!-- 로딩 -->
    <div v-if="isLoading" class="empty-state">데이터를 불러오는 중...</div>

    <!-- 프로젝트 미선택 -->
    <div v-else-if="!selectedProject" class="empty-state">
      <p>프로젝트를 선택해주세요</p>
    </div>

    <!-- 타임라인 로딩 -->
    <div v-else-if="isLoadingTimeline" class="empty-state">
      타임라인을 불러오는 중...
    </div>

    <!-- 결과 없음 -->
    <div v-else-if="timeline.length === 0" class="empty-state">
      <p v-if="selectedMember">
        {{ selectedMemberName || "선택한 멤버" }}의 보고가 없습니다
      </p>
      <p v-else>해당 프로젝트의 보고 이력이 없습니다</p>
      <button
        v-if="selectedMember"
        type="button"
        class="btn"
        @click="clearMemberFilter"
      >
        전체 멤버 보기
      </button>
    </div>

    <!-- 타임라인 표시 -->
    <div v-else class="timeline-container">
      <div class="timeline-summary">
        <span class="summary-badge">{{ totalDays }}일</span>
        <span class="summary-badge">{{ totalEntries }}건 보고</span>
      </div>

      <div class="timeline">
        <div
          v-for="([date, entries], idx) in groupedByDate"
          :key="date"
          class="timeline-day"
        >

          <div class="timeline-content">
            <div class="date-header">
              <span class="date-text">{{ formatDate(date) }}</span>
              <span class="date-count">{{ entries.length }}건</span>
            </div>

            <div
              v-for="(entry, eIdx) in entries"
              :key="eIdx"
              class="card timeline-card"
              tabindex="0"
              @click="openEntry(entry)"
              @keydown.enter.prevent="openEntry(entry)"
              @keydown.space.prevent="openEntry(entry)"
            >
              <header class="entry-header">
                <span class="avatar">{{
                  String(entry.member_name || "?").slice(0, 1)
                }}</span>
                <h3 class="entry-name">{{ entry.member_name }}</h3>
              </header>

              <div
                v-for="section in visibleSections(entry)"
                :key="section.key"
                class="field-group"
              >
                <h3>{{ section.label }}</h3>
                <ul class="item-list">
                  <li
                    v-for="(item, itemIndex) in section.items"
                    :key="itemIndex"
                  >
                    <span>{{ itemText(item) }}</span>
                    <span
                      v-if="section.key === 'issues' && statusOf(item)"
                      class="status-badge"
                      :class="
                        statusOf(item) === '해결' ? 'is-resolved' : 'is-open'
                      "
                    >
                      {{ statusOf(item) }}
                    </span>
                  </li>
                </ul>
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
  cursor: pointer;
}

.timeline-card:hover {
  border-color: var(--accent-border);
  box-shadow: var(--shadow-raised);
}

.timeline-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.timeline-card:last-child {
  margin-bottom: 0;
}

.entry-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--bg-soft);
  color: var(--text-h);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
}

.entry-name {
  margin: 0;
  font-size: 15px;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
  border: 1px solid var(--border);
  background: var(--bg);
  padding: 12px 14px;
  border-radius: var(--radius-sm);
}

.field-group:last-of-type {
  margin-bottom: 0;
}

.field-group h3 {
  margin: 0;
  font-size: 13px;
  color: var(--text);
}

.item-list {
  margin: 0;
  padding-left: 18px;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text-h);
}

.item-list li + li {
  margin-top: 4px;
}

.status-badge {
  display: inline-flex;
  margin-left: 8px;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 650;
  vertical-align: middle;
}

.status-badge.is-open {
  background: var(--danger-bg);
  color: var(--danger);
}

.status-badge.is-resolved {
  background: color-mix(in srgb, var(--success) 16%, transparent);
  color: var(--success);
}
</style>
