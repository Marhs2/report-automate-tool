<script setup>
import { onMounted, ref, computed } from "vue";
import { ChevronRight } from "lucide-vue-next";
import { useRoute, useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { isFutureDate } from "../lib/dateScope";
import {
  buildIssueBoard,
  looksLikeIssue,
  sameWork,
  textsOf,
} from "../lib/issueBoard";

/** 보고 항목 분류 색. 모든 화면이 같은 태그(components.css .cat-tag)를 쓴다. */
const KIND_TAGS = { 완료: "is-done", 진행: "is-progress", 이슈: "is-issue", 요청: "is-request", 다음: "is-next" };

const route = useRoute();
const router = useRouter();
const { getProjectNames, getProjectTimeline, getUsers } = useApi();

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
/** 불러오는 동안 보드 자리에 그리는 빈 줄 수. */
const SKELETON_LINES = 3;

const projectNames = ref([]);
const timeline = ref([]);
const selectedProject = ref("");
const selectedMember = ref("");
const isLoading = ref(false);
const isLoadingTimeline = ref(false);
const loadError = ref("");
const timelineError = ref("");

const fetchInitialData = async () => {
  isLoading.value = true;
  loadError.value = "";
  try {
    projectNames.value = await getProjectNames();
    // 들어오자마자 "프로젝트를 선택해주세요"만 있는 빈 화면을 보여주지 않는다.
    const asked = String(route.query.project || "");
    if (!selectedProject.value && projectNames.value.length) {
      selectedProject.value = projectNames.value.includes(asked) ? asked : projectNames.value[0];
      await fetchTimeline();
    }
  } catch (error) {
    console.error("Error fetching initial data:", error);
    loadError.value = "프로젝트 목록을 불러오지 못했습니다.";
  } finally {
    isLoading.value = false;
  }
  try {
    allMembers.value = await getUsers();
  } catch (error) {
    console.error("Error fetching users:", error);
    allMembers.value = [];
  }
};

const fetchTimeline = async () => {
  if (!selectedProject.value) {
    timeline.value = [];
    return;
  }
  isLoadingTimeline.value = true;
  timelineError.value = "";
  try {
    timeline.value = await getProjectTimeline(selectedProject.value);
  } catch (error) {
    console.error("Error fetching timeline:", error);
    timeline.value = [];
    timelineError.value = "보고를 불러오지 못했습니다.";
  } finally {
    isLoadingTimeline.value = false;
  }
};

const retry = () => {
  if (loadError.value) fetchInitialData();
  else fetchTimeline();
};

const projectMembers = computed(() => {
  const map = new Map();
  for (const entry of timeline.value) {
    const id = String(entry.member_id ?? "");
    if (!id || map.has(id)) continue;
    map.set(id, {
      id,
      name: entry.member_name || `사용자 ${id}`,
    });
  }
  return [...map.values()].sort((a, b) => a.name.localeCompare(b.name, "ko"));
});

/* 콤보는 전체 인원이다. 이 프로젝트 보고자만 넣으면 빠진 사람을 고를 수 없다. */
const allMembers = ref([]);

const reportCountByMember = computed(() => {
  const counts = new Map();
  for (const entry of scopedTimeline.value) {
    const id = String(entry.member_id ?? "");
    if (!id) continue;
    counts.set(id, (counts.get(id) || 0) + 1);
  }
  return counts;
});

const memberOptions = computed(() => {
  const counts = reportCountByMember.value;
  const rows = allMembers.value.length
    ? allMembers.value.map((user) => ({
        id: String(user.id),
        name: user.name || `사용자 ${user.id}`,
      }))
    : projectMembers.value;
  return rows
    .map((user) => ({ ...user, count: counts.get(user.id) || 0 }))
    .sort((left, right) => {
      if (Boolean(right.count) !== Boolean(left.count)) {
        return right.count - left.count;
      }
      return left.name.localeCompare(right.name, "ko");
    });
});

/* 아직 오지 않은 날의 보고는 "오늘 이슈"가 아니다.
   기본은 오늘까지만 보고, 필요하면 켠다. */
const includeFuture = ref(false);

const futureCount = computed(
  () => timeline.value.filter((entry) => isFutureDate(entry.date)).length,
);

const scopedTimeline = computed(() =>
  includeFuture.value
    ? timeline.value
    : timeline.value.filter((entry) => !isFutureDate(entry.date)),
);

/* 카드가 완료·진행·다음 한 덩어리면 이슈만 따라가기 어렵다. */
const VIEWS = [
  { id: "all", label: "전체" },
  { id: "issues", label: "이슈만" },
];
const view = ref("all");

const filteredTimeline = computed(() => {
  if (!selectedMember.value) return scopedTimeline.value;
  return scopedTimeline.value.filter(
    (entry) => String(entry.member_id) === String(selectedMember.value),
  );
});

/** 이슈만 볼 때는 이슈가 없는 보고를 아예 빼서 스크롤이 줄어든다. */
const flowEntries = computed(() =>
  view.value === "issues"
    ? filteredTimeline.value.filter((entry) => compactRows(entry).length > 0)
    : filteredTimeline.value,
);

const groupedByDate = computed(() => {
  const groups = {};
  for (const entry of flowEntries.value) {
    if (!groups[entry.date]) groups[entry.date] = [];
    groups[entry.date].push(entry);
  }
  return Object.entries(groups).sort(([a], [b]) => b.localeCompare(a));
});

const calendarGap = (older, newer) => {
  const start = new Date(`${older}T00:00:00`);
  const end = new Date(`${newer}T00:00:00`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0;
  return Math.round((end - start) / 86400000) - 1;
};

const flowGroups = computed(() =>
  groupedByDate.value.map(([date, entries], idx) => {
    const newer = idx > 0 ? groupedByDate.value[idx - 1][0] : null;
    const gap = newer ? calendarGap(date, newer) : 0;
    return { date, entries, gap: gap > 0 ? gap : 0 };
  }),
);

const totalDays = computed(() => groupedByDate.value.length);

const selectedMemberName = computed(() => {
  const found = memberOptions.value.find(
    (user) => String(user.id) === String(selectedMember.value),
  );
  return found?.name || "";
});

const displayDate = (value) => {
  const [year, month, day] = String(value).split("-");
  if (!year || !month || !day) return value;
  // 검색 · 필터 목록과 같은 날짜 머리: "10월 16일".
  const monthDay = `${Number(month)}월 ${Number(day)}일`;
  if (year === String(new Date().getFullYear())) return monthDay;
  return `${year}년 ${monthDay}`;
};

const summaryParts = computed(() => {
  const shown = flowEntries.value.length;
  const people = new Set(
    flowEntries.value.map((entry) => String(entry.member_id || "")).filter(Boolean),
  );
  const parts = [`보고 ${shown}건`];
  if (totalDays.value) parts.push(`${totalDays.value}일`);
  if (!selectedMember.value && people.size) parts.push(`작성 ${people.size}명`);
  return parts;
});

const weekday = (value) => {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "";
  return WEEKDAYS[date.getDay()];
};

const shortDate = (value) => {
  const [, month, day] = String(value).split("-");
  if (!month || !day) return value;
  return `${Number(month)}.${Number(day)}`;
};

const compactRows = (entry) => {
  const issues = textsOf(entry.issues);
  const completed = textsOf(entry.completedTasks);
  const requests = textsOf(entry.requests);
  const plans = textsOf(entry.nextPlans);
  const progress = textsOf(entry.inProgressTasks).filter(
    (text) => !issues.some((issue) => sameWork(issue, text)),
  );
  const rows = [];
  if (view.value === "issues") {
    for (const text of issues) rows.push({ kind: "issue", label: "이슈", text });
    for (const text of progress.filter(looksLikeIssue)) {
      rows.push({ kind: "issue", label: "이슈", text });
    }
    return rows;
  }
  for (const text of completed) rows.push({ kind: "done", label: "완료", text });
  for (const text of progress) rows.push({ kind: "", label: "진행", text });
  for (const text of issues) rows.push({ kind: "issue", label: "이슈", text });
  for (const text of requests) rows.push({ kind: "", label: "요청", text });
  for (const text of plans) rows.push({ kind: "", label: "다음", text });
  return rows;
};

const issueBoard = computed(() => buildIssueBoard(filteredTimeline.value));

const issueGroups = computed(() => [
  { id: "open", label: "미해결", tone: "is-danger", items: issueBoard.value.open },
  { id: "omit", label: "이후 언급 없음", tone: "", items: issueBoard.value.unmentioned },
  { id: "done", label: "해결", tone: "is-success", items: issueBoard.value.resolved },
]);

const issueTotal = computed(() =>
  issueGroups.value.reduce((sum, group) => sum + group.items.length, 0),
);

const hasIssueBoard = computed(() => issueTotal.value > 0);

const issueMeta = (item) => {
  const who =
    !selectedMember.value && item.member_name ? ` · ${item.member_name}` : "";
  if (item.status === "open") return `${shortDate(item.firstDate)}부터${who}`;
  if (item.status === "resolved") {
    return `${shortDate(item.resolvedDate)} 완료${who}`;
  }
  return `${shortDate(item.lastDate)} 이후 보고에 없음${who}`;
};

const openIssueEntry = (item) => {
  if (item.status === "resolved") {
    openEntry({ report_id: item.resolvedReportId || item.report_id });
    return;
  }
  openEntry(item);
};

const onProjectChange = () => {
  selectedMember.value = "";
  fetchTimeline();
};

const openEntry = (entry) => {
  if (!entry?.report_id) return;
  // 크럼이 "프로젝트 흐름"으로 남아야 돌아올 자리를 안다.
  router.push({
    name: "report-result",
    params: { id: entry.report_id },
    query: { from: "timeline" },
  });
};

const clearMemberFilter = () => {
  selectedMember.value = "";
};

onMounted(() => {
  fetchInitialData();
});
</script>

<template>
  <div class="page is-wide">
    <!-- 일일보고 목록과 같은 한 줄 필터. 라벨 대신 첫 옵션이 무엇을 고르는지 말한다. -->
    <div class="filters">
      <select
        id="timeline-project"
        v-model="selectedProject"
        class="input filter-select"
        aria-label="프로젝트"
        @change="onProjectChange"
      >
        <option value="">프로젝트 선택</option>
        <option v-for="name in projectNames" :key="name" :value="name">
          {{ name }}
        </option>
      </select>

      <!-- 전체 인원을 다 넣고, 이 프로젝트 보고 건수를 옆에 적는다. -->
      <select
        id="timeline-member"
        v-model="selectedMember"
        class="input filter-select"
        aria-label="보고자"
        :disabled="!selectedProject || isLoadingTimeline"
      >
        <option value="">전체 보고자</option>
        <option
          v-for="user in memberOptions"
          :key="user.id"
          :value="user.id"
        >
          {{ user.name }}{{ user.count ? ` (${user.count})` : " (보고 없음)" }}
        </option>
      </select>

      <div class="seg view-seg" role="group" aria-label="보기">
        <button
          v-for="item in VIEWS"
          :key="item.id"
          type="button"
          :class="{ 'is-on': view === item.id }"
          :aria-pressed="view === item.id"
          @click="view = item.id"
        >
          {{ item.label }}
        </button>
      </div>
    </div>

    <div v-if="selectedProject && !isLoading && !loadError" class="flow-meta">
      <p v-if="!isLoadingTimeline && !timelineError && filteredTimeline.length" class="flow-chips">
        <span v-for="part in summaryParts" :key="part" class="chip">{{ part }}</span>
      </p>
      <button
        v-if="futureCount"
        type="button"
        class="btn btn-small btn-ghost future-toggle"
        :class="{ 'is-active': includeFuture }"
        :aria-pressed="includeFuture"
        @click="includeFuture = !includeFuture"
      >
        {{ includeFuture ? "오늘까지만" : `예정 ${futureCount}건 보기` }}
      </button>
    </div>

    <section
      v-if="isLoading || isLoadingTimeline"
      class="card day-board skeleton"
      role="status"
      :aria-label="isLoading ? '프로젝트 불러오는 중' : '보고 불러오는 중'"
    >
      <div class="board-head" aria-hidden="true">
        <i class="skeleton-bar is-title"></i>
      </div>
      <div v-for="n in SKELETON_LINES" :key="n" class="skeleton-line" aria-hidden="true">
        <i class="skeleton-bar is-tag"></i>
        <i class="skeleton-bar is-text"></i>
      </div>
    </section>

    <section v-else-if="loadError || timelineError" class="card board-state is-error" role="alert">
      <p>{{ loadError || timelineError }}</p>
      <button type="button" class="btn btn-small" @click="retry">다시 시도</button>
    </section>

    <section v-else-if="!selectedProject" class="card board-state">
      <p v-if="projectNames.length">프로젝트를 고르면 보고 흐름이 나옵니다</p>
      <p v-else>아직 일일보고에 적힌 프로젝트가 없습니다</p>
    </section>

    <section v-else-if="filteredTimeline.length === 0" class="card board-state">
      <p v-if="selectedMember">
        {{ selectedMemberName || "선택한 보고자" }}의 보고가 없습니다
      </p>
      <p v-else-if="futureCount && !includeFuture">
        오늘까지 올라온 보고가 없습니다. 예정된 보고 {{ futureCount }}건이 있습니다.
      </p>
      <p v-else>이 프로젝트의 보고 이력이 없습니다</p>
      <button
        v-if="selectedMember"
        type="button"
        class="btn btn-small"
        @click="clearMemberFilter"
      >
        전체 보고자 보기
      </button>
      <button
        v-else-if="futureCount && !includeFuture"
        type="button"
        class="btn btn-small"
        @click="includeFuture = true"
      >
        예정도 보기
      </button>
    </section>

    <div v-else class="timeline" :class="{ 'has-issues': hasIssueBoard }">
      <aside v-if="hasIssueBoard" class="card issue-board" aria-labelledby="issue-board-title">
        <header class="board-head">
          <h2 id="issue-board-title" class="board-title">이슈</h2>
          <span class="board-meta">{{ issueTotal }}건</span>
        </header>

        <template v-for="group in issueGroups" :key="group.id">
          <section v-if="group.items.length" class="issue-group" :aria-label="group.label">
            <h3 class="issue-group-head">
              <span class="state-chip" :class="group.tone">{{ group.label }} {{ group.items.length }}</span>
            </h3>
            <button
              v-for="(item, index) in group.items"
              :key="`${group.id}-${item.member_id}-${item.firstDate}-${index}`"
              type="button"
              class="issue-row"
              @click="openIssueEntry(item)"
            >
              <span class="issue-text">{{ item.text }}</span>
              <span class="issue-meta">{{ issueMeta(item) }}</span>
            </button>
          </section>
        </template>
      </aside>

      <div class="flow">
        <section v-if="!flowGroups.length" class="card board-state">
          <p>이슈가 적힌 보고가 없습니다</p>
          <button type="button" class="btn btn-small" @click="view = 'all'">전체 보기</button>
        </section>

        <template v-for="group in flowGroups" :key="group.date">
          <p v-if="group.gap" class="gap">{{ group.gap }}일 공백</p>

          <article class="card day-board">
            <header class="board-head">
              <h2 class="board-title">
                {{ displayDate(group.date) }}
                <span class="day-week">{{ weekday(group.date) }}</span>
              </h2>
              <span v-if="group.entries.length > 1" class="board-meta">
                {{ group.entries.length }}건
              </span>
            </header>

            <button
              v-for="entry in group.entries"
              :key="entry.report_id || `${entry.member_id}-${group.date}`"
              type="button"
              class="entry"
              @click="openEntry(entry)"
            >
              <span v-if="!selectedMember" class="entry-who">
                <span class="avatar">{{ String(entry.member_name || "?").slice(0, 1) }}</span>
                <span class="entry-name">{{ entry.member_name }}</span>
              </span>
              <span class="entry-lines">
                <span v-for="(row, rowIndex) in compactRows(entry)" :key="rowIndex" class="entry-line">
                  <span class="cat-tag" :class="KIND_TAGS[row.label]">{{ row.label }}</span>
                  <span class="entry-text">{{ row.text }}</span>
                </span>
              </span>
              <ChevronRight class="entry-go" :size="18" aria-hidden="true" />
            </button>
          </article>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped src="../styles/components/project-timeline.css"></style>
