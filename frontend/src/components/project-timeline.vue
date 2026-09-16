<script setup>
import { onMounted, ref, computed } from "vue";
import { useRouter } from "vue-router";
import useApi from "../composables/useApi";

const router = useRouter();
const { getProjectNames, getProjectTimeline } = useApi();

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
const CLOSE_KEYS = [
  "속도",
  "검색",
  "깨지",
  "느려",
  "중복",
  "동일명함",
  "긴명함",
  "명함이름",
  "흐린",
];

const projectNames = ref([]);
const timeline = ref([]);
const selectedProject = ref("");
const selectedMember = ref("");
const isLoading = ref(false);
const isLoadingTimeline = ref(false);

const itemText = (value) =>
  value && typeof value === "object"
    ? String(value.content ?? "").trim()
    : String(value ?? "").trim();

const normalize = (value) => itemText(value).replace(/\s+/g, "").toLowerCase();

const similar = (a, b) => {
  const na = normalize(a);
  const nb = normalize(b);
  if (!na || !nb) return false;
  if (na === nb) return true;
  const shorter = na.length <= nb.length ? na : nb;
  const longer = na.length <= nb.length ? nb : na;
  if (shorter.length >= 10 && longer.includes(shorter)) return true;
  return CLOSE_KEYS.some((key) => na.includes(key) && nb.includes(key));
};

const looksLikeIssue = (value) =>
  /검색|안\s*나|나오지|오류|버그|깨지|느려|실패|장애/.test(itemText(value));

const textsOf = (list) =>
  (Array.isArray(list) ? list : []).map(itemText).filter(Boolean);

const fetchInitialData = async () => {
  isLoading.value = true;
  try {
    projectNames.value = await getProjectNames();
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

const filteredTimeline = computed(() => {
  if (!selectedMember.value) return timeline.value;
  return timeline.value.filter(
    (entry) => String(entry.member_id) === String(selectedMember.value),
  );
});

const groupedByDate = computed(() => {
  const groups = {};
  for (const entry of filteredTimeline.value) {
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
const totalEntries = computed(() => filteredTimeline.value.length);

const selectedMemberName = computed(() => {
  const found = projectMembers.value.find(
    (user) => String(user.id) === String(selectedMember.value),
  );
  return found?.name || "";
});

const formatDate = (value) => {
  const [year, month, day] = String(value).split("-");
  if (!year || !month || !day) return value;
  return `${year}.${month}.${day}`;
};

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
    (text) => !issues.some((issue) => similar(issue, text)),
  );
  const rows = [];
  for (const text of completed) rows.push({ kind: "done", label: "완료", text });
  for (const text of progress) rows.push({ kind: "", label: "진행", text });
  for (const text of issues) rows.push({ kind: "issue", label: "이슈", text });
  for (const text of requests) rows.push({ kind: "", label: "요청", text });
  for (const text of plans) rows.push({ kind: "", label: "다음", text });
  return rows;
};

const issueTexts = (entry) => [
  ...textsOf(entry.issues),
  ...textsOf(entry.inProgressTasks).filter(looksLikeIssue),
];

const issueBoard = computed(() => {
  const byMember = new Map();
  const latestByMember = new Map();
  const chronological = [...filteredTimeline.value].sort((a, b) => {
    const dateCmp = String(a.date).localeCompare(String(b.date));
    if (dateCmp) return dateCmp;
    return String(a.member_id).localeCompare(String(b.member_id));
  });

  for (const entry of chronological) {
    const memberKey = String(entry.member_id);
    latestByMember.set(memberKey, entry);
    if (!byMember.has(memberKey)) byMember.set(memberKey, []);
    const threads = byMember.get(memberKey);

    for (const done of textsOf(entry.completedTasks)) {
      for (const item of threads) {
        if (similar(item.text, done)) {
          item.resolvedDate = entry.date;
          item.resolvedReportId = entry.report_id;
        }
      }
    }

    const issueOnly = textsOf(entry.issues);
    const progressOnly = textsOf(entry.inProgressTasks).filter(looksLikeIssue);

    for (const text of issueOnly) {
      const existing = threads.find((item) => similar(item.text, text));
      if (existing) {
        existing.text = text;
        existing.fromIssue = true;
        existing.lastDate = entry.date;
        existing.report_id = entry.report_id;
        continue;
      }
      threads.push({
        text,
        fromIssue: true,
        firstDate: entry.date,
        lastDate: entry.date,
        report_id: entry.report_id,
        member_id: entry.member_id,
        member_name: entry.member_name,
      });
    }

    for (const text of progressOnly) {
      const existing = threads.find((item) => similar(item.text, text));
      if (existing) {
        existing.lastDate = entry.date;
        existing.report_id = entry.report_id;
        continue;
      }
      threads.push({
        text,
        fromIssue: false,
        firstDate: entry.date,
        lastDate: entry.date,
        report_id: entry.report_id,
        member_id: entry.member_id,
        member_name: entry.member_name,
      });
    }
  }

  const open = [];
  const unmentioned = [];
  const resolved = [];

  for (const [memberKey, threads] of byMember) {
    const latest = latestByMember.get(memberKey);
    const latestOpen = latest ? issueTexts(latest) : [];

    for (const item of threads) {
      const stillOpen = latestOpen.some((text) => similar(item.text, text));
      let status = "unmentioned";
      if (stillOpen) status = "open";
      else if (
        item.resolvedDate &&
        String(item.resolvedDate) >= String(item.lastDate)
      ) {
        status = "resolved";
      }
      const row = { ...item, status };
      if (status === "open") open.push(row);
      else if (status === "resolved") resolved.push(row);
      else unmentioned.push(row);
    }
  }

  const byFirst = (a, b) => String(a.firstDate).localeCompare(String(b.firstDate));
  open.sort(byFirst);
  unmentioned.sort(byFirst);
  resolved.sort(byFirst);
  return { open, unmentioned, resolved };
});

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
  router.push(`/report-result/${entry.report_id}`);
};

const clearMemberFilter = () => {
  selectedMember.value = "";
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
      </div>
    </div>

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
          :disabled="!selectedProject || isLoadingTimeline"
        >
          <option value="">전체 멤버</option>
          <option
            v-for="user in projectMembers"
            :key="user.id"
            :value="user.id"
          >
            {{ user.name }}
          </option>
        </select>
      </div>
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

    <div v-else class="timeline-container">
      <div class="timeline-summary">
        <span class="summary-badge">{{ totalDays }}일</span>
        <span class="summary-badge">{{ totalEntries }}건 보고</span>
        <span v-if="issueBoard.open.length" class="summary-badge danger">
          열린 이슈 {{ issueBoard.open.length }}
        </span>
        <span v-if="issueBoard.unmentioned.length" class="summary-badge muted">
          언급 없음 {{ issueBoard.unmentioned.length }}
        </span>
        <span v-if="issueBoard.resolved.length" class="summary-badge">
          해결 {{ issueBoard.resolved.length }}
        </span>
      </div>

      <section v-if="hasIssueBoard" class="card open-issues">
        <h2>이슈</h2>

        <div v-if="issueBoard.open.length" class="issue-group">
          <h3>미해결</h3>
          <button
            v-for="(item, index) in issueBoard.open"
            :key="`open-${item.member_id}-${item.firstDate}-${index}`"
            type="button"
            class="issue-row"
            @click="openIssueEntry(item)"
          >
            <span class="issue-chip">미해결</span>
            <span class="issue-copy">
              <span class="issue-text">{{ item.text }}</span>
              <span class="issue-meta">{{ issueMeta(item) }}</span>
            </span>
          </button>
        </div>

        <div v-if="issueBoard.unmentioned.length" class="issue-group">
          <h3>이후 언급 없음</h3>
          <button
            v-for="(item, index) in issueBoard.unmentioned"
            :key="`omit-${item.member_id}-${item.firstDate}-${index}`"
            type="button"
            class="issue-row"
            @click="openIssueEntry(item)"
          >
            <span class="issue-chip muted">언급 없음</span>
            <span class="issue-copy">
              <span class="issue-text">{{ item.text }}</span>
              <span class="issue-meta">{{ issueMeta(item) }}</span>
            </span>
          </button>
        </div>

        <div v-if="issueBoard.resolved.length" class="issue-group">
          <h3>해결</h3>
          <button
            v-for="(item, index) in issueBoard.resolved"
            :key="`done-${item.member_id}-${item.firstDate}-${index}`"
            type="button"
            class="issue-row"
            @click="openIssueEntry(item)"
          >
            <span class="issue-chip done">해결</span>
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
            <div class="day-head">
              <span class="day-date">{{ formatDate(group.date) }}</span>
              <span class="day-week">{{ weekday(group.date) }}</span>
              <span v-if="group.entries.length > 1" class="date-count">
                {{ group.entries.length }}건
              </span>
            </div>

            <div
              v-for="entry in group.entries"
              :key="entry.report_id || `${entry.member_id}-${group.date}`"
              class="day-entry"
              tabindex="0"
              @click="openEntry(entry)"
              @keydown.enter.prevent="openEntry(entry)"
              @keydown.space.prevent="openEntry(entry)"
            >
              <header v-if="!selectedMember" class="entry-header">
                <span class="avatar">{{
                  String(entry.member_name || "?").slice(0, 1)
                }}</span>
                <h3 class="entry-name">{{ entry.member_name }}</h3>
              </header>

              <div
                v-for="(row, rowIndex) in compactRows(entry)"
                :key="rowIndex"
                class="row"
              >
                <span class="k" :class="row.kind">{{ row.label }}</span>
                <p class="v">{{ row.text }}</p>
              </div>
            </div>
          </article>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filter-select {
  width: auto;
  min-width: 200px;
}

.filter-hint {
  margin: -8px 0 20px;
  font-size: 12px;
  color: var(--text);
  word-break: keep-all;
}

.timeline-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.summary-badge {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
  font-size: 13px;
  font-weight: 500;
  border-radius: 999px;
  background: var(--accent-bg);
  color: var(--accent);
}

.summary-badge.danger {
  background: var(--danger-bg);
  color: var(--danger);
}

.summary-badge.muted {
  background: var(--bg-soft);
  color: var(--text);
}

.open-issues {
  margin-bottom: 24px;
  padding: 16px 18px;
}

.open-issues h2 {
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.issue-group + .issue-group {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.issue-group h3 {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 650;
  color: var(--text);
}

.issue-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  margin: 0;
  padding: 8px 0;
  border: 0;
  border-top: 1px solid var(--border);
  background: transparent;
  text-align: left;
  cursor: pointer;
}


.issue-row:hover {
  background: var(--bg-soft);
  border-radius: var(--radius-sm);
  transition: background 0.2s ease-in-out;
}


.issue-group .issue-row:first-of-type {
  border-top: 0;
  padding-top: 0;
}

.issue-row:hover .issue-text {
  color: var(--text-h);
}

.issue-chip {
  flex: 0 0 auto;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--danger-bg);
  color: var(--danger);
  font-size: 11px;
  font-weight: 650;
  line-height: 1.4;
}

.issue-chip.muted {
  background: var(--bg-soft);
  color: var(--text);
}

.issue-chip.done {
  background: var(--accent-bg);
  color: var(--accent);
}

.issue-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.issue-text {
  font-size: 14px;
  color: var(--text-h);
  word-break: keep-all;
}

.issue-meta {
  font-size: 12px;
  color: var(--text);
}

.flow {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.day {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
  background: var(--bg);
}

.day-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 10px;
}

.day-date {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-h);
}

.day-week {
  font-size: 12px;
  color: var(--text);
}

.date-count {
  font-size: 12px;
  color: var(--text);
  background: var(--bg-soft);
  padding: 2px 8px;
  border-radius: 999px;
}

.day-entry {
  cursor: pointer;
  border-radius: var(--radius-sm);
}

.day-entry + .day-entry {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.day-entry:hover .v {
  color: var(--text-h);
}

.day-entry:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.entry-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 10px;
  background: var(--bg-soft);
  color: var(--text-h);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 12px;
  flex-shrink: 0;
}

.entry-name {
  margin: 0;
  font-size: 14px;
}

.row {
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 10px;
  align-items: start;
  padding: 4px 0;
}

.k {
  font-size: 12px;
  font-weight: 650;
  color: var(--text);
  padding-top: 2px;
}

.k.done {
  color: var(--accent);
}

.k.issue {
  color: var(--danger);
}

.v {
  margin: 0;
  font-size: 14px;
  color: var(--text-h);
  line-height: 1.5;
  word-break: keep-all;
}

.gap {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0;
  color: var(--text);
  font-size: 12px;
}

.gap::before,
.gap::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--border);
}
</style>
