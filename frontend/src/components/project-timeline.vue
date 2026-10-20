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

const projectNames = ref([]);
const timeline = ref([]);
const selectedProject = ref("");
const selectedMember = ref("");
const isLoading = ref(false);
const isLoadingTimeline = ref(false);

const fetchInitialData = async () => {
  isLoading.value = true;
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
  try {
    timeline.value = await getProjectTimeline(selectedProject.value);
  } catch (error) {
    console.error("Error fetching timeline:", error);
    timeline.value = [];
  } finally {
    isLoadingTimeline.value = false;
  }
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
  const monthDay = `${Number(month)}.${Number(day)}`;
  if (year === String(new Date().getFullYear())) return monthDay;
  return `${year}.${monthDay}`;
};

const summaryLine = computed(() => {
  const shown = flowEntries.value.length;
  const people = new Set(
    flowEntries.value.map((entry) => String(entry.member_id || "")).filter(Boolean),
  );
  const parts = [`보고 ${shown}건`];
  if (totalDays.value) parts.push(`${totalDays.value}일`);
  if (!selectedMember.value && people.size) parts.push(`작성 ${people.size}명`);
  return parts.join(" · ");
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

const hasIssueBoard =
  computed(() =>
    issueBoard.value.open.length +
      issueBoard.value.unmentioned.length +
      issueBoard.value.resolved.length >
    0,
  );

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

        <div class="seg view-chips" role="group" aria-label="보기">
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

    <div v-if="selectedProject && !isLoading" class="flow-meta">
      <p v-if="!isLoadingTimeline && filteredTimeline.length">{{ summaryLine }}</p>
      <button
        v-if="futureCount"
        type="button"
        class="text-toggle"
        @click="includeFuture = !includeFuture"
      >
        {{ includeFuture ? "오늘까지만" : `예정 ${futureCount}건 보기` }}
      </button>
    </div>

    <div v-if="isLoading" class="empty-state">데이터를 불러오는 중...</div>

    <div v-else-if="!selectedProject" class="empty-state">
      <p>프로젝트를 선택해주세요</p>
    </div>

    <div v-else-if="isLoadingTimeline" class="empty-state">
      타임라인을 불러오는 중...
    </div>

    <div v-else-if="filteredTimeline.length === 0" class="empty-state">
      <p v-if="selectedMember">
        {{ selectedMemberName || "선택한 보고자" }}의 보고가 없습니다
      </p>
      <p v-else-if="futureCount && !includeFuture">
        오늘까지 올라온 보고가 없습니다. 예정된 보고 {{ futureCount }}건이 있습니다.
      </p>
      <p v-else>해당 프로젝트의 보고 이력이 없습니다</p>
      <button
        v-if="selectedMember"
        type="button"
        class="btn"
        @click="clearMemberFilter"
      >
        전체 보고자 보기
      </button>
      <button
        v-else-if="futureCount && !includeFuture"
        type="button"
        class="btn"
        @click="includeFuture = true"
      >
        예정도 보기
      </button>
    </div>

    <div v-else class="timeline-container">

      <section v-if="hasIssueBoard" class="card open-issues">
        <h2>이슈</h2>

        <div v-if="issueBoard.open.length" class="issue-group">
          <h3><span class="state-chip is-warning">열린 이슈 {{ issueBoard.open.length }}</span></h3>
          <button
            v-for="(item, index) in issueBoard.open"
            :key="`open-${item.member_id}-${item.firstDate}-${index}`"
            type="button"
            class="issue-row is-open"
            @click="openIssueEntry(item)"
          >
            <span class="issue-copy">
              <span class="issue-text">{{ item.text }}</span>
              <span class="issue-meta">{{ issueMeta(item) }}</span>
            </span>
          </button>
        </div>

        <div v-if="issueBoard.unmentioned.length" class="issue-group">
          <h3><span class="state-chip">이후 언급 없음 {{ issueBoard.unmentioned.length }}</span></h3>
          <button
            v-for="(item, index) in issueBoard.unmentioned"
            :key="`omit-${item.member_id}-${item.firstDate}-${index}`"
            type="button"
            class="issue-row is-quiet"
            @click="openIssueEntry(item)"
          >
            <span class="issue-copy">
              <span class="issue-text">{{ item.text }}</span>
              <span class="issue-meta">{{ issueMeta(item) }}</span>
            </span>
          </button>
        </div>

        <div v-if="issueBoard.resolved.length" class="issue-group">
          <h3><span class="state-chip is-success">해결 {{ issueBoard.resolved.length }}</span></h3>
          <button
            v-for="(item, index) in issueBoard.resolved"
            :key="`done-${item.member_id}-${item.firstDate}-${index}`"
            type="button"
            class="issue-row is-done"
            @click="openIssueEntry(item)"
          >
            <span class="issue-copy">
              <span class="issue-text">{{ item.text }}</span>
              <span class="issue-meta">{{ issueMeta(item) }}</span>
            </span>
          </button>
        </div>
      </section>

      <div class="flow">
        <template v-for="group in flowGroups" :key="group.date">
          <div v-if="group.gap" class="gap">{{ group.gap }}일 공백</div>

          <article class="day">
            <h2 class="date-head day-head">
              {{ displayDate(group.date) }}
              <span class="date-head-week">{{ weekday(group.date) }}</span>
              <span v-if="group.entries.length > 1" class="date-head-meta">
                {{ group.entries.length }}건
              </span>
            </h2>

            <button
              v-for="entry in group.entries"
              :key="entry.report_id || `${entry.member_id}-${group.date}`"
              type="button"
              class="day-entry"
              @click="openEntry(entry)"
            >
              <ChevronRight class="entry-go" :size="16" aria-hidden="true" />
              <header v-if="!selectedMember" class="entry-header">
                <span class="avatar">{{
                  String(entry.member_name || "?").slice(0, 1)
                }}</span>
                <h3 class="entry-name">{{ entry.member_name }}</h3>
              </header>

              <div
                v-for="(row, rowIndex) in compactRows(entry)"
                :key="rowIndex"
                class="flow-line"
              >
                <span class="k cat-tag" :class="KIND_TAGS[row.label]">{{ row.label }}</span>
                <p class="v">{{ row.text }}</p>
              </div>
            </button>
          </article>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped src="../styles/components/project-timeline.css"></style>
