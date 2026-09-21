<template>
    <div class="page report-doc is-wide">
        <!-- 주간 상세는 먼저 읽는 화면이다. 고칠 때만 입력칸을 연다. -->
        <header class="detail-head">
            <div class="detail-title">
                <h1>{{ userName || "주간 보고서" }}</h1>
                <span class="detail-period">{{ periodLabel }}</span>
                <span v-if="!isEditing" class="status-chip">읽기</span>
                <span v-else class="status-chip is-draft">고치는 중</span>
            </div>
            <div class="detail-actions">
                <button type="button" class="btn btn-small" @click="goBack">목록</button>
                <button type="button" class="btn btn-small" @click="copyReport" :disabled="isSaving">복사</button>
                <button
                    v-if="canEdit"
                    type="button"
                    class="btn btn-small"
                    :class="{ 'btn-primary': !isEditing }"
                    @click="toggleEditing"
                >
                    {{ isEditing ? "읽기" : "수정" }}
                </button>
                <button
                    v-if="canEdit && isEditing"
                    type="button"
                    class="btn btn-primary btn-small hide-on-narrow"
                    @click="saveReport"
                    :disabled="isSaving"
                >
                    {{ isSaving ? "저장 중..." : "수정 저장" }}
                </button>
            </div>
        </header>

        <div v-if="reportData && !isEditing" class="content-container single">
            <div class="json-container">
                <p v-if="reportData.carriedFromLastWeek" class="carry-hint" role="status">
                    지난주 향후 {{ reportData.carriedCount }}건을 이번 주 향후일정에 남겨 두었습니다.
                </p>

                <div v-if="!projectBlocks.length" class="empty-state">
                    아직 채워진 프로젝트가 없습니다
                </div>

                <section
                    v-for="block in projectBlocks"
                    :key="`read-${block.key}`"
                    class="card project-block"
                >
                    <h2 class="read-project-name">{{ blockTitle(block) || "제목 없음" }}</h2>
                    <div class="split">
                        <div class="split-col">
                            <h3 class="read-col-head">
                                진행 현황
                                <span v-if="reportData.week_label_done">{{ reportData.week_label_done }}</span>
                            </h3>
                            <!-- 슬라이드에서는 한 칸이지만 읽을 때는 완료 / 진행 / 이슈로 나눠 본다. -->
                            <div
                                v-for="group in doneGroups(block)"
                                :key="`${block.key}-${group.kind}`"
                                class="read-kind"
                            >
                                <h4 :class="group.kind">{{ group.label }} {{ group.items.length }}</h4>
                                <ul class="read-list">
                                    <li v-for="(item, index) in group.items" :key="index">{{ item }}</li>
                                </ul>
                            </div>
                            <p v-if="!doneGroups(block).length" class="empty-msg">항목이 없습니다</p>
                        </div>
                        <div class="split-col">
                            <h3 class="read-col-head">
                                향후일정
                                <span v-if="nextWeek">{{ nextWeek }}</span>
                            </h3>
                            <ul v-if="nextItems(block).length" class="read-list">
                                <li v-for="(item, index) in nextItems(block)" :key="index">{{ item }}</li>
                            </ul>
                            <p v-else class="empty-msg">항목이 없습니다</p>
                        </div>
                    </div>
                </section>

                <!-- PPT 전용 칸. 비어 있으면 "0건"을 늘어놓지 않고 한 줄로 접는다. -->
                <p v-if="extras.total === 0" class="extras-note">
                    PPT 전용 칸(공지사항 · 주요 이벤트 · 센터 협업)은 비어 있습니다.
                    비워 두면 해당 슬라이드가 빠집니다.
                </p>
                <section v-else class="card extras-card">
                    <h2 class="read-project-name">PPT 전용 칸</h2>
                    <div v-if="extras.notices" class="read-kind">
                        <h4>공지사항 {{ extras.notices }}</h4>
                        <ul class="read-list">
                            <li v-for="(notice, index) in notices" :key="`rn-${index}`">
                                {{ notice.title }}
                                <template v-if="notice.body.filter(Boolean).length">
                                    — {{ notice.body.filter(Boolean).join(" / ") }}
                                </template>
                            </li>
                        </ul>
                    </div>
                    <div v-if="extras.events" class="read-kind">
                        <h4>주요 이벤트 {{ extras.events }}</h4>
                        <ul class="read-list">
                            <li
                                v-for="(event, index) in [...eventsOf('month_events'), ...eventsOf('next_month_events')]"
                                :key="`re-${index}`"
                            >
                                {{ [event.when, event.title].filter(Boolean).join(" ") }}
                            </li>
                        </ul>
                    </div>
                    <div v-if="extras.collab" class="read-kind">
                        <h4>센터 협업</h4>
                        <p v-if="collab?.supports.length" class="read-support">
                            지원 {{ collab.supports.join(", ") }}
                        </p>
                        <ul class="read-list">
                            <li
                                v-for="(item, index) in [...(collab?.done || []), ...(collab?.next || [])].filter(Boolean)"
                                :key="`rc-${index}`"
                            >
                                {{ item }}
                            </li>
                        </ul>
                    </div>
                </section>
            </div>
        </div>

        <div v-else-if="reportData" class="content-container single">
            <div class="json-container">
                <p v-if="reportData.carriedFromLastWeek" class="carry-hint" role="status">
                    지난주 향후 {{ reportData.carriedCount }}건을 이번 주 향후일정에 남겨 두었습니다.
                </p>

                <details class="card meta-card">
                    <summary>
                        <span class="meta-summary">{{ metaSummary }}</span>
                        <span class="meta-edit">수정</span>
                    </summary>
                    <div class="meta-grid">
                        <AppField label="보고일자">
                            <input class="input" v-model="reportData.report_date" />
                        </AppField>
                        <AppField label="작성자">
                            <input class="input" v-model="reportData.author" />
                        </AppField>
                        <AppField label="센터">
                            <input class="input" v-model="reportData.center" placeholder="예: 경영지원센터" />
                        </AppField>
                        <AppField label="센터장">
                            <input class="input" v-model="reportData.director" placeholder="예: 홍길동" />
                        </AppField>
                        <AppField label="진행 주차">
                            <input class="input" v-model="reportData.week_label_done" />
                        </AppField>
                        <AppField label="향후 주차">
                            <input class="input" :value="nextWeek" readonly tabindex="-1" />
                        </AppField>
                    </div>
                </details>

                <!-- 공지사항 슬라이드 -->
                <details class="card fold-card" :open="notices.length > 0">
                    <summary>
                        <span class="fold-title">공지사항</span>
                        <span class="fold-count">{{ notices.length }}건</span>
                        <span v-if="!notices.length" class="fold-hint">비우면 슬라이드가 빠집니다</span>
                    </summary>
                    <div v-for="(notice, noticeIndex) in notices" :key="`notice-${noticeIndex}`" class="fold-block">
                        <div class="fold-block-head">
                            <input
                                class="input"
                                v-model="notice.title"
                                placeholder="공지 제목 (예: 보안업무관리 규정 제정)"
                            />
                            <button
                                type="button"
                                class="btn btn-danger"
                                @click="removeNotice(noticeIndex)"
                            >
                                삭제
                            </button>
                        </div>
                        <div v-for="(_line, lineIndex) in notice.body" :key="`line-${lineIndex}`" class="task-row">
                            <input
                                class="input"
                                v-model="notice.body[lineIndex]"
                                placeholder="세부 내용 한 줄"
                            />
                            <button
                                type="button"
                                class="btn remove-btn"
                                aria-label="이 항목 삭제"
                                @click="removeNoticeLine(notice, lineIndex)"
                            >
                                삭제
                            </button>
                        </div>
                        <button type="button" class="btn add-btn" @click="addNoticeLine(notice)">
                            항목 추가
                        </button>
                    </div>
                    <button type="button" class="btn add-btn" @click="addNotice">
                        항목 추가
                    </button>
                </details>

                <!-- 주요 업무 현황 슬라이드의 이벤트 표 -->
                <details class="card fold-card" :open="eventCount > 0">
                    <summary>
                        <span class="fold-title">주요 이벤트</span>
                        <span class="fold-count">{{ eventCount }}건</span>
                        <span v-if="!eventCount" class="fold-hint">비우면 이벤트 표가 빠집니다</span>
                    </summary>
                    <div class="split">
                        <section v-for="list in eventLists" :key="list.key" class="field-group split-col">
                            <h2>{{ list.label }}</h2>
                            <div
                                v-for="(event, eventIndex) in eventsOf(list.key)"
                                :key="`${list.key}-${eventIndex}`"
                                class="task-row"
                            >
                                <input
                                    class="input event-when"
                                    v-model="event.when"
                                    placeholder="6/15"
                                />
                                <input
                                    class="input"
                                    v-model="event.title"
                                    placeholder="내용"
                                />
                                <button
                                    type="button"
                                    class="btn remove-btn"
                                    aria-label="이 항목 삭제"
                                    @click="removeEvent(list.key, eventIndex)"
                                >
                                    삭제
                                </button>
                            </div>
                            <p v-if="!eventsOf(list.key).length" class="empty-msg">항목이 없습니다</p>
                            <button type="button" class="btn add-btn" @click="addEvent(list.key)">
                                항목 추가
                            </button>
                        </section>
                    </div>
                </details>

                <div
                    class="card project-block"
                    v-for="block in projectBlocks"
                    :key="block.key"
                >
                    <div class="project-head">
                        <input
                            class="input project-name-input"
                            :value="blockTitle(block)"
                            placeholder="프로젝트 이름"
                            @input="setBlockTitle(block, $event.target.value)"
                        />
                        <button
                            type="button"
                            class="btn btn-danger"
                            @click="removeProject(block)"
                        >
                            삭제
                        </button>
                    </div>
                    <div class="split">
                        <section
                            v-for="col in columns"
                            :key="col.kind"
                            class="field-group split-col"
                        >
                            <h2>{{ col.label }}</h2>
                            <div
                                v-for="(_item, itemIndex) in (block[col.kind]?.items || [])"
                                :key="`${col.kind}-${block.key}-${itemIndex}`"
                                class="task-row"
                            >
                                <textarea
                                    class="input task-editor"
                                    :data-weekly-editor="`${block.key}-${col.kind}-${itemIndex}`"
                                    v-model="block[col.kind].items[itemIndex]"
                                    rows="1"
                                    placeholder="내용을 입력하세요"
                                    @input="growEditor"
                                    @keydown.enter.exact.prevent="$event.target.blur()"
                                />
                                <button
                                    type="button"
                                    class="btn remove-btn"
                                    aria-label="이 항목 삭제"
                                    @click="removeAt(block[col.kind].items, itemIndex)"
                                >
                                    삭제
                                </button>
                            </div>
                            <p v-if="!(block[col.kind]?.items || []).length" class="empty-msg">
                                항목이 없습니다
                            </p>
                            <button
                                type="button"
                                class="btn add-btn"
                                @click="addItem(block, col.kind)"
                            >
                                항목 추가
                            </button>
                        </section>
                    </div>
                </div>

                <button type="button" class="btn add-project-btn" @click="addProject">
                    프로젝트 추가
                </button>

                <!-- 센터 협업 현황 슬라이드 -->
                <details v-if="collab" class="card fold-card" :open="collabFilled > 0">
                    <summary>
                        <span class="fold-title">센터 협업 현황</span>
                        <span class="fold-count">{{ collab.supports.length }}개 센터</span>
                        <span v-if="!collabFilled" class="fold-hint">비우면 슬라이드가 빠집니다</span>
                    </summary>
                    <div class="support-picker" role="group" aria-label="지원 센터">
                        <span class="support-label">지원</span>
                        <button
                            v-for="code in COLLAB_CENTERS"
                            :key="code"
                            type="button"
                            class="support-chip"
                            :class="{ 'is-on': collab.supports.includes(code) }"
                            :aria-pressed="collab.supports.includes(code)"
                            @click="toggleSupport(code)"
                        >
                            {{ code }}
                        </button>
                    </div>
                    <div class="split">
                        <section v-for="col in collabColumns" :key="col.kind" class="field-group split-col">
                            <h2>{{ col.label }}</h2>
                            <div
                                v-for="(_item, itemIndex) in collab[col.kind]"
                                :key="`collab-${col.kind}-${itemIndex}`"
                                class="task-row"
                            >
                                <input
                                    class="input"
                                    v-model="collab[col.kind][itemIndex]"
                                    placeholder="내용을 입력하세요"
                                />
                                <button
                                    type="button"
                                    class="btn remove-btn"
                                    aria-label="이 항목 삭제"
                                    @click="removeCollabItem(col.kind, itemIndex)"
                                >
                                    삭제
                                </button>
                            </div>
                            <button type="button" class="btn add-btn" @click="addCollabItem(col.kind)">
                                항목 추가
                            </button>
                        </section>
                    </div>
                </details>

                <div class="card save-bar">
                    <span class="save-note">{{ userName }}</span>
                    <div class="save-actions">
                        <button class="btn" @click="copyReport" :disabled="isSaving">복사</button>
                        <button
                            v-if="canEdit"
                            class="btn btn-primary"
                            @click="saveReport"
                            :disabled="isSaving"
                        >
                            {{ isSaving ? "저장 중..." : "수정 저장" }}
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div v-else class="empty-state">보고서 데이터가 없습니다.</div>
    </div>
</template>

<script setup>
import { computed, nextTick, ref, onMounted, watch } from "vue";
import useApi from "../composables/useApi";
import { useRoute, useRouter } from "vue-router";
import { useDialog } from "../composables/useDialog";
import { selectedUserId } from "../composables/useSelectedUser";
import { isAdmin } from "../composables/useSession";
import {
    COLLAB_CENTERS,
    deckExtrasCount,
    emptyCollab,
    emptyEvent,
    emptyNotice,
    emptySection,
    formatDeck,
    groupDoneItems,
    nextWeekLabel,
    toWeeklyDeck,
} from "../lib/weeklyDeck";
import AppField from "./ui/AppField.vue";

const route = useRoute();
const router = useRouter();
const goBack = () => router.push("/weekly");

const reportData = ref(null);
const userName = ref("");
const ownerMemberId = ref(null);
const isSaving = ref(false);
/** 먼저 읽는 화면으로 연다. 고칠 때만 입력칸을 켠다. */
const isEditing = ref(false);
const isMine = computed(() => {
    if (ownerMemberId.value == null || selectedUserId.value == null) return false;
    return String(ownerMemberId.value) === String(selectedUserId.value);
});
const canEdit = computed(() => isMine.value || isAdmin.value);
const { getUsers, getWeeklyReportById, updateWeeklyReport } = useApi();
const { alert: showAlert, confirm: askConfirm } = useDialog();

const toggleEditing = () => {
    if (!canEdit.value) return;
    isEditing.value = !isEditing.value;
    if (isEditing.value) growAllEditors();
};

watch(canEdit, (ok) => {
    if (!ok) isEditing.value = false;
});

const columns = [
    { kind: "done", label: "진행 현황" },
    { kind: "next", label: "향후일정" },
];
const growEditor = (event) => {
    const el = event.target;
    if (!(el instanceof HTMLTextAreaElement)) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
};

const growAllEditors = async () => {
    await nextTick();
    document.querySelectorAll("[data-weekly-editor]").forEach((node) => {
        growEditor({ target: node });
    });
};

const startEdit = async (block, kind, index) => {
    await nextTick();
    const id = `${block.key}-${kind}-${index}`;
    const el = [...document.querySelectorAll("[data-weekly-editor]")].find(
        (node) => node.getAttribute("data-weekly-editor") === id,
    );
    if (!(el instanceof HTMLTextAreaElement)) return;
    el.focus();
    growEditor({ target: el });
    const len = el.value.length;
    el.setSelectionRange(len, len);
};

const nextWeek = computed(() => {
    if (!reportData.value) return "";
    return (
        nextWeekLabel(
            reportData.value.week_label_done,
            reportData.value.report_date,
        ) ||
        reportData.value.week_label_next ||
        ""
    );
});

watch(nextWeek, (label) => {
    if (reportData.value && label) {
        reportData.value.week_label_next = label;
    }
});

/** 헤더 부제: 진행 주차 → 향후 주차. 주차 라벨이 없으면 보고일자. */
const periodLabel = computed(() => {
    const data = reportData.value;
    if (!data) return "주간 상세";
    const done = String(data.week_label_done || "").trim();
    if (done) return nextWeek.value ? `${done} → ${nextWeek.value}` : done;
    return data.report_date || "주간 상세";
});

/** 접힌 문서 정보 카드에 한 줄로 보여줄 요약. */
const metaSummary = computed(() => {
    const data = reportData.value;
    if (!data) return "";
    return [
        data.report_date,
        data.author,
        data.center,
        periodLabel.value,
    ]
        .map((value) => String(value || "").trim())
        .filter(Boolean)
        .join(" · ");
});

const confirmQuestions = computed(() => {
    const items = reportData.value?.confirmQuestions;
    if (!Array.isArray(items)) return [];
    return items
        .map((item, index) => ({
            id: item?.id || `q-${index}`,
            text: String(item?.text || "").trim(),
            ifNo: String(item?.ifNo || "").trim(),
        }))
        .filter((item) => item.text)
        .slice(0, 3);
});

const removeAt = (list, index) => {
    list.splice(index, 1);
};

const projectBlocks = computed(() => {
    const data = reportData.value;
    if (!data) return [];
    const order = [];
    const seen = new Map();
    const add = (section, kind, index) => {
        const key = section.title || `__blank_${kind}_${index}`;
        if (!seen.has(key)) {
            const block = { key, done: null, next: null };
            seen.set(key, block);
            order.push(block);
        }
        seen.get(key)[kind] = section;
    };
    (data.done || []).forEach((section, index) => add(section, "done", index));
    (data.next || []).forEach((section, index) => add(section, "next", index));
    return order;
});

const blockTitle = (block) => block.done?.title || block.next?.title || "";

/** 읽기 모드: 합쳐진 진행 현황을 완료 / 진행 / 이슈로 다시 나눈다. */
const doneGroups = (block) =>
    block.done ? groupDoneItems(reportData.value, block.done) : [];

const nextItems = (block) =>
    (block.next?.items || []).filter((item) => String(item || "").trim());

/** PPT 전용 칸이 실제로 채워진 건수. 0이면 읽는 화면에서 한 줄로 접는다. */
const extras = computed(() => deckExtrasCount(reportData.value));

const setBlockTitle = (block, title) => {
    if (block.done) block.done.title = title;
    if (block.next) block.next.title = title;
};

const addItem = (block, kind) => {
    if (!reportData.value) return;
    const list = kind === "done" ? reportData.value.done : reportData.value.next;
    if (!block[kind]) {
        const section = emptySection();
        section.title = blockTitle(block);
        list.push(section);
        startEdit(block, kind, 0);
        return;
    }
    block[kind].items.push("");
    startEdit(block, kind, block[kind].items.length - 1);
};

const removeProject = (block) => {
    if (!reportData.value) return;
    if (block.done) {
        const index = reportData.value.done.indexOf(block.done);
        if (index >= 0) reportData.value.done.splice(index, 1);
    }
    if (block.next) {
        const index = reportData.value.next.indexOf(block.next);
        if (index >= 0) reportData.value.next.splice(index, 1);
    }
};

const addProject = () => {
    if (!reportData.value) return;
    reportData.value.done.push(emptySection());
};

/* ---- 실제 주간보고 슬라이드에 필요한 나머지 칸 ----
   공지사항 / 금월·익월 주요 이벤트 / 센터 협업 현황.
   비어 있으면 PPTX에서 해당 슬라이드가 빠지므로 여기서 채운다. */

const notices = computed(() => reportData.value?.notices || []);

const addNotice = () => {
    if (!reportData.value) return;
    if (!Array.isArray(reportData.value.notices)) reportData.value.notices = [];
    reportData.value.notices.push(emptyNotice());
};

const removeNotice = (index) => {
    reportData.value?.notices?.splice(index, 1);
};

const addNoticeLine = (notice) => {
    notice.body.push("");
};

const removeNoticeLine = (notice, index) => {
    notice.body.splice(index, 1);
    if (!notice.body.length) notice.body.push("");
};

const eventLists = computed(() => [
    { key: "month_events", label: "금월 주요 이벤트" },
    { key: "next_month_events", label: "익월 주요 이벤트" },
]);

const eventsOf = (key) => reportData.value?.[key] || [];

const eventCount = computed(
    () =>
        eventsOf("month_events").length + eventsOf("next_month_events").length,
);

const addEvent = (key) => {
    if (!reportData.value) return;
    if (!Array.isArray(reportData.value[key])) reportData.value[key] = [];
    reportData.value[key].push(emptyEvent());
};

const removeEvent = (key, index) => {
    reportData.value?.[key]?.splice(index, 1);
};

const collab = computed(() => {
    if (!reportData.value) return null;
    if (!reportData.value.collab) reportData.value.collab = emptyCollab();
    return reportData.value.collab;
});

const collabColumns = [
    { kind: "done", label: "진행 현황" },
    { kind: "next", label: "향후일정" },
];

const collabFilled = computed(() => {
    const data = collab.value;
    if (!data) return 0;
    return (
        data.supports.length +
        [...(data.done || []), ...(data.next || [])].filter((item) =>
            String(item || "").trim(),
        ).length
    );
});

const toggleSupport = (code) => {
    const data = collab.value;
    if (!data) return;
    const index = data.supports.indexOf(code);
    if (index >= 0) data.supports.splice(index, 1);
    else data.supports.push(code);
};

const addCollabItem = (kind) => {
    collab.value?.[kind].push("");
};

const removeCollabItem = (kind, index) => {
    const list = collab.value?.[kind];
    if (!list) return;
    list.splice(index, 1);
    if (!list.length) list.push("");
};

/* 센터·센터장은 매주 같은 값이다. 한 번 입력하면 다음 보고서에 자동으로 채운다. */
const CENTER_KEY = "dxel.weekly.center";
const DIRECTOR_KEY = "dxel.weekly.director";

const applyRememberedHeader = () => {
    const data = reportData.value;
    if (!data) return;
    const center = localStorage.getItem(CENTER_KEY) || "";
    const director = localStorage.getItem(DIRECTOR_KEY) || "";
    if (center && (!data.center || data.center === "미지정")) {
        data.center = center;
    }
    if (director && !data.director) data.director = director;
};

const rememberHeader = () => {
    const data = reportData.value;
    if (!data) return;
    const center = String(data.center || "").trim();
    const director = String(data.director || "").trim();
    if (center && center !== "미지정") localStorage.setItem(CENTER_KEY, center);
    if (director) localStorage.setItem(DIRECTOR_KEY, director);
};



watch(
    reportData,
    (newVal) => {
        if (newVal) sessionStorage.setItem("reportData", JSON.stringify(newVal));
        growAllEditors();
    },
    { deep: true },
);

onMounted(async () => {
    const reportId = route.params.id;
    if (reportId) {
        try {
            const data = await getWeeklyReportById(reportId);
            reportData.value = toWeeklyDeck(data.report);
            if (!reportData.value.author) {
                reportData.value.author = data.memberName || "";
            }
            userName.value = data.memberName || `사용자 ${data.memberId}`;
            ownerMemberId.value = data.memberId ?? null;
            applyRememberedHeader();
            sessionStorage.setItem("reportData", JSON.stringify(reportData.value));
            sessionStorage.setItem("selectedUser", String(data.memberId));
        } catch (error) {
            console.error("보고서 불러오기 실패:", error);
            showAlert("보고서를 불러오는데 실패했습니다.");
        }
        return;
    }
    const stored = sessionStorage.getItem("reportData");
    if (stored) reportData.value = toWeeklyDeck(JSON.parse(stored));
    const userId = localStorage.getItem("report-selectedUser") || "";
    if (userId) {
        getUsers()
            .then((users) => {
                const found = users.find((u) => String(u.id) === String(userId));
                userName.value = found ? found.name : `사용자 ${userId}`;
            })
            .catch(() => {
                userName.value = `사용자 ${userId}`;
            });
    }
});

const copyReport = async () => {
    if (!reportData.value) return;
    try {
        await navigator.clipboard.writeText(formatDeck(reportData.value));
        showAlert("보고서가 클립보드에 복사되었습니다.");
    } catch (error) {
        console.error("복사 실패:", error);
        showAlert("복사에 실패했습니다.");
    }
};

const askConfirmQuestions = async () => {
    const questions = confirmQuestions.value;
    for (const [index, question] of questions.entries()) {
        const ok = await askConfirm(question.text, {
            title: `저장 전 확인 ${index + 1}/${questions.length}`,
            help: question.ifNo
                ? `아니요면 ${question.ifNo}`
                : "아니요면 해당 항목을 고친 뒤 다시 저장하세요.",
            confirmLabel: "네",
            cancelLabel: "아니요",
        });
        if (!ok) return false;
    }
    return true;
};

const persistReport = async () => {
    const reportId = route.params.id;
    isSaving.value = true;
    try {
        rememberHeader();
        await updateWeeklyReport(reportId, JSON.stringify(reportData.value));
        showAlert("주간 보고서가 저장되었습니다.");
    } catch (error) {
        console.error("저장 실패:", error);
        showAlert("주간 보고서 저장에 실패했습니다.");
    } finally {
        isSaving.value = false;
    }
};

const saveReport = async () => {
    if (!reportData.value) return;
    if (!canEdit.value) {
        showAlert("자신의 보고만 수정할 수 있습니다.");
        return;
    }
    const reportId = route.params.id;
    if (!reportId) {
        showAlert("저장할 주간 보고서 ID가 없습니다.");
        return;
    }
    if (!(await askConfirmQuestions())) return;
    await persistReport();
};
</script>

<style scoped>
/* 제목 줄: 사람 · 주차 · 상태 · 동작. */
.detail-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
}

.detail-title {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2) var(--space-3);
    min-width: 0;
}

.detail-title h1 {
    margin: 0;
    font-family: var(--heading);
    font-size: 22px;
    letter-spacing: -0.3px;
    color: var(--text-strong);
}

.detail-period {
    font-size: var(--fs-13);
    color: var(--text);
}

.detail-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
}

/* 읽기 모드 */
.read-project-name {
    margin: 0 0 var(--space-3);
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    word-break: keep-all;
}

.read-col-head {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    margin: 0 0 var(--space-2);
    font-family: var(--sans);
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.read-col-head span {
    font-size: var(--fs-11);
    font-weight: var(--fw-medium);
    color: var(--text);
}

.read-kind + .read-kind {
    margin-top: var(--space-3);
}

.read-kind h4 {
    margin: 0 0 var(--space-1);
    font-family: var(--sans);
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.read-kind h4.done {
    color: var(--success-fg);
}

.read-kind h4.issue {
    color: var(--danger-fg);
}

.read-list {
    margin: 0;
    padding-left: var(--space-5);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
}

.read-list li {
    font-size: var(--fs-14);
    color: var(--text-strong);
    line-height: var(--lh-base);
    word-break: keep-all;
}

.read-support {
    margin: 0 0 var(--space-1);
    font-size: var(--fs-12);
    color: var(--text);
}

.extras-card .read-kind:first-of-type {
    margin-top: 0;
}

/* 비어 있는 PPT 칸은 "0건" 카드로 늘어놓지 않고 한 줄로 알린다. */
.extras-note {
    margin: 0;
    padding: var(--space-3) var(--space-4);
    border: 1px dashed var(--border);
    border-radius: var(--radius);
    font-size: var(--fs-12);
    color: var(--text);
    word-break: keep-all;
}

/* 접히는 보조 카드: 공지사항 · 주요 이벤트 · 센터 협업 현황.
   비어 있을 때는 한 줄로 접어 두고, 내용이 있으면 펼친 상태로 연다. */
.fold-card {
    padding: var(--space-3) var(--space-4);
}

.fold-card > summary {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    cursor: pointer;
    font-size: var(--fs-13);
    color: var(--text);
}

.fold-card[open] > summary {
    margin-bottom: var(--space-4);
}

.fold-title {
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.fold-count {
    padding: 0 6px;
    border-radius: var(--radius-pill);
    background: var(--surface-soft);
    font-size: var(--fs-11);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.fold-hint {
    margin-left: auto;
    font-size: var(--fs-12);
    color: var(--text-muted);
}

.fold-block + .fold-block {
    margin-top: var(--space-4);
    padding-top: var(--space-4);
    border-top: 1px solid var(--border);
}

.fold-block-head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
}

.fold-card .add-project {
    margin-top: var(--space-3);
}

.event-when {
    flex: 0 0 72px;
    text-align: center;
}

.support-picker {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
}

.support-label {
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.support-chip {
    height: 28px;
    padding: 0 var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-pill);
    background: var(--surface);
    font: inherit;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text);
    cursor: pointer;
}

.support-chip:hover {
    border-color: var(--border-strong);
}

.support-chip.is-on {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--accent-hover);
}

.meta-card {
    padding: var(--space-3) var(--space-4);
}

.meta-card > summary {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    cursor: pointer;
    font-size: var(--fs-13);
    color: var(--text);
}

.meta-summary {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-strong);
    font-weight: var(--fw-medium);
}

.meta-edit {
    margin-left: auto;
    flex-shrink: 0;
    color: var(--text-muted);
}

.meta-card[open] > summary {
    margin-bottom: var(--space-4);
}

.carry-hint {
    margin: 0;
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--warning-border);
    border-radius: var(--radius);
    background: var(--warning-bg);
    color: var(--warning-fg);
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    word-break: keep-all;
}

.json-container,
.project-block,
.split,
.split-col,
.meta-grid {
    min-width: 0;
    max-width: 100%;
}

.meta-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-3);
}

.meta-grid :deep(.input) {
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
}

.project-head {
    min-width: 0;
}

/* 줄 끝에 붙는 작은 아이콘 버튼. 텍스트 '삭제' 버튼이 항목마다 반복되던 것을 대체한다. */
.row-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 28px;
    height: 28px;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition:
        background var(--dur-fast) var(--ease),
        color var(--dur-fast) var(--ease);
}

.row-btn:hover,
.row-btn:focus-visible {
    background: var(--danger-bg);
    color: var(--danger-fg);
}

.add-item {
    display: inline-flex;
    align-items: center;
    align-self: flex-start;
    gap: var(--space-1);
    padding: var(--space-1) var(--space-2);
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    font: inherit;
    font-size: var(--fs-13);
    color: var(--text);
    cursor: pointer;
}

.add-item:hover {
    background: var(--surface-soft);
    color: var(--text-strong);
}

.add-project {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-3);
    border: 1px dashed var(--border-strong);
    border-radius: var(--radius);
    background: transparent;
    font: inherit;
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    color: var(--text);
    cursor: pointer;
}

.add-project:hover {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--text-strong);
}

.split {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: var(--space-3);
    align-items: stretch;
}

.split-col {
    margin-bottom: 0;
}

.task-row {
    align-items: flex-start;
}

.task-editor {
    min-height: 36px;
    resize: none;
    overflow: hidden;
    line-height: var(--lh-relaxed);
}

.project-block {
    overflow: hidden;
}

/* 항목이 길어도 스크롤 끝까지 내려가지 않고 저장할 수 있게 고정한다. */
.save-bar {
    position: sticky;
    bottom: var(--space-3);
    z-index: 5;
    padding: var(--space-3) var(--space-4);
    box-shadow: 0 2px 12px rgba(38, 37, 30, 0.08);
}

.save-note {
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.save-actions {
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
}

@media (max-width: 1100px) {
    .meta-grid,
    .split {
        grid-template-columns: minmax(0, 1fr);
    }
}
</style>
