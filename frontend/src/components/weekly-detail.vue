<template>
    <div class="page report-doc is-wide">
        <!-- 고칠 수 있으면 수정 화면으로 연다. 저장 전에는 목록에 남지 않는다. -->
        <header class="detail-head">
            <div class="detail-title">
                <h1>{{ userName || "주간 보고서" }}</h1>
                <span class="detail-period">{{ periodLabel }}</span>
                <span class="state-chip" :class="isUnsaved ? 'is-warning' : 'is-success'">
                    {{ isUnsaved ? "AI 초안 · 저장 전" : "저장됨" }}
                </span>
            </div>
            <div class="detail-actions">
                <div class="detail-copy-col">
                    <button type="button" class="btn btn-small" @click="copyReport"
                        :disabled="isSaving || isReextracting">복사</button>
                </div>
                <div v-if="canEdit" class="mode-switch" role="group" aria-label="보기 방식">
                    <button type="button" :class="{ 'is-on': !isEditing }" :aria-pressed="!isEditing"
                        :disabled="isReextracting" @click="isEditing && toggleEditing()">읽기</button>
                    <button type="button" :class="{ 'is-on': isEditing }" :aria-pressed="isEditing"
                        :disabled="isReextracting" @click="!isEditing && toggleEditing()">수정</button>
                </div>
            </div>
        </header>

        <div v-if="reportData && !isEditing" class="content-container single">
            <div class="json-container">
                <div v-if="!projectBlocks.length" class="empty-state">
                    아직 채워진 프로젝트가 없습니다
                </div>

                <section v-for="block in projectBlocks" :key="`read-${block.key}`" class="card project-block">
                    <h2 class="read-project-name">{{ blockTitle(block) || "제목 없음" }}</h2>
                    <div class="split">
                        <div class="split-col">
                            <h3 class="read-col-head">
                                진행 현황
                                <span v-if="reportData.week_label_done">{{ reportData.week_label_done }}</span>
                            </h3>
                            <!-- 슬라이드에서는 한 칸이지만 읽을 때는 완료 / 진행 / 이슈로 나눠 본다. -->
                            <div v-for="group in doneGroups(block)" :key="`${block.key}-${group.kind}`"
                                class="read-kind">
                                <h4>
                                    <span class="cat-tag" :class="KIND_TONES[group.kind]">{{ group.label }}</span>
                                    <span class="read-count">{{ group.items.length }}</span>
                                </h4>
                                <ul class="read-list">
                                    <li v-for="(item, index) in group.items" :key="index">{{ item }}</li>
                                </ul>
                            </div>
                            <p v-if="!doneGroups(block).length" class="read-empty">없음</p>
                        </div>
                        <div class="split-col">
                            <h3 class="read-col-head">
                                향후일정
                                <span v-if="nextWeek">{{ nextWeek }}</span>
                            </h3>
                            <ul v-if="nextItems(block).length" class="read-list">
                                <li v-for="(item, index) in nextItems(block)" :key="index">{{ item }}</li>
                            </ul>
                            <p v-else class="read-empty">없음</p>
                        </div>
                    </div>
                </section>

                <!-- PPT 전용 칸. 비어 있으면 "0건"을 늘어놓지 않고 한 줄로 접는다. -->
                <section v-if="extras.total" class="card extras-card">
                    <h2 class="read-project-name">PPT 전용 칸</h2>
                    <div v-if="extras.notices" class="read-kind">
                        <h4>공지사항 {{ extras.notices }}</h4>
                        <ul class="read-list">
                            <li v-for="(notice, index) in notices" :key="`rn-${index}`">
                                {{ notice.title }}
                                <template v-if="notice.body.filter(Boolean).length">
                                    : {{ notice.body.filter(Boolean).join(" / ") }}
                                </template>
                            </li>
                        </ul>
                    </div>
                    <div v-if="extras.events" class="read-kind">
                        <h4>주요 이벤트 {{ extras.events }}</h4>
                        <ul class="read-list">
                            <li v-for="(event, index) in [...eventsOf('month_events'), ...eventsOf('next_month_events')]"
                                :key="`re-${index}`">
                                {{ [event.when, event.title].filter(Boolean).join(" ") }}
                            </li>
                        </ul>
                    </div>
                    <div v-if="extras.collab" class="read-kind">
                        <h4>센터 협업</h4>
                        <template v-for="row in collabRows" :key="row.code">
                            <p class="read-support">{{ row.code }}</p>
                            <ul class="read-list">
                                <li v-for="(item, index) in row.done" :key="`rcd-${index}`">{{ item }}</li>
                                <li v-for="(item, index) in row.next" :key="`rcn-${index}`">향후 · {{ item }}</li>
                            </ul>
                        </template>
                    </div>
                </section>
            </div>
        </div>

        <div v-else-if="reportData" class="content-container single">
            <div class="json-container">
                <details class="card meta-card">
                    <summary>
                        <span class="meta-summary">{{ metaSummary }}</span>
                        <button type="button" class="btn btn-small layout-chip" @click.prevent.stop="changeLayout">
                            PPT · {{ layoutName }}
                        </button>
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

                <div
                    class="card project-block"
                    v-for="block in projectBlocks"
                    :key="block.key"
                    :data-project-key="block.key"
                    @focusin="rememberBlock(block)"
                >
                    <div class="project-head">
                        <input class="input project-name-input" :value="blockTitle(block)" placeholder="프로젝트 이름"
                            @input="setBlockTitle(block, $event.target.value)" />
                        <button type="button" class="btn btn-danger" @click="removeProject(block)">
                            삭제
                        </button>
                    </div>
                    <div class="split">
                        <section v-for="col in columns" :key="col.kind" class="field-group split-col">
                            <h2>{{ col.label }}</h2>
                            <div v-for="(_item, itemIndex) in (block[col.kind]?.items || [])"
                                :key="`${col.kind}-${block.key}-${itemIndex}`" class="task-row">
                                <textarea class="input task-editor"
                                    :data-weekly-editor="`${block.key}-${col.kind}-${itemIndex}`"
                                    v-model="block[col.kind].items[itemIndex]" rows="1" placeholder="내용을 입력하세요"
                                    @input="growEditor" @keydown.enter.exact.prevent="$event.target.blur()" />
                                <button type="button" class="btn remove-btn" aria-label="이 항목 삭제"
                                    @click="removeAt(block[col.kind].items, itemIndex)">
                                    <X :size="14" aria-hidden="true" />
                                </button>
                            </div>
                            <p v-if="!(block[col.kind]?.items || []).length" class="empty-msg">
                                항목이 없습니다
                            </p>
                            <button type="button" class="btn add-btn" @click="addItem(block, col.kind)">
                                + 추가
                            </button>
                        </section>
                    </div>
                </div>

                <button type="button" class="btn add-project-btn" @click="addProject">
                    프로젝트 추가
                </button>

                <!-- 아래는 PPT에만 들어가는 칸. 업무 내용을 먼저 쓰고 필요할 때만 채운다. -->
                <h2 class="extras-label">PPT 전용 칸</h2>

                <!-- 공지사항 슬라이드 -->
                <details class="card fold-card" :open="foldOpen.notices"
                    @toggle="foldOpen.notices = $event.target.open">
                    <summary>
                        <span class="fold-title">공지사항</span>
                        <span class="fold-count">{{ notices.length }}건</span>
                        <span v-if="!notices.length" class="fold-hint">비우면 슬라이드가 빠집니다</span>
                    </summary>
                    <div v-for="(notice, noticeIndex) in notices" :key="`notice-${noticeIndex}`"
                        class="fold-block notice-block">
                        <div class="fold-block-head">
                            <input class="input project-name-input notice-title-input" v-model="notice.title"
                                placeholder="공지 제목" />
                            <button type="button" class="btn btn-danger" @click="removeNotice(noticeIndex)">
                                삭제
                            </button>
                        </div>
                        <div v-for="(_line, lineIndex) in notice.body" :key="`line-${lineIndex}`" class="task-row">
                            <input class="input" v-model="notice.body[lineIndex]" placeholder="세부 내용 한 줄" />
                            <button type="button" class="btn remove-btn" aria-label="이 항목 삭제"
                                @click="removeNoticeLine(notice, lineIndex)">
                                <X :size="14" aria-hidden="true" />
                            </button>
                        </div>
                        <button type="button" class="btn add-btn" @click="addNoticeLine(notice)">
                            + 줄 추가
                        </button>
                    </div>
                    <button type="button" class="btn add-project-btn add-notice-btn" @click="addNotice">
                        공지 추가
                    </button>
                </details>

                <!-- 주요 업무 현황 슬라이드의 이벤트 표 -->
                <details class="card fold-card" :open="foldOpen.events"
                    @toggle="foldOpen.events = $event.target.open">
                    <summary>
                        <span class="fold-title">주요 이벤트</span>
                        <span class="fold-count">{{ eventCount }}건</span>
                        <span v-if="!eventCount" class="fold-hint">비우면 이벤트 표가 빠집니다</span>
                    </summary>
                    <div class="split">
                        <section v-for="list in eventLists" :key="list.key" class="field-group split-col">
                            <h2>{{ list.label }}</h2>
                            <div v-for="(event, eventIndex) in eventsOf(list.key)" :key="`${list.key}-${eventIndex}`"
                                class="task-row">
                                <input class="input event-when" v-model="event.when" placeholder="6/15" />
                                <input class="input" v-model="event.title" placeholder="내용" />
                                <button type="button" class="btn remove-btn" aria-label="이 항목 삭제"
                                    @click="removeEvent(list.key, eventIndex)">
                                    <X :size="14" aria-hidden="true" />
                                </button>
                            </div>
                            <p v-if="!eventsOf(list.key).length" class="empty-msg">항목이 없습니다</p>
                            <button type="button" class="btn add-btn" @click="addEvent(list.key)">
                                + 추가
                            </button>
                        </section>
                    </div>
                </details>

                <!-- 센터 협업 현황 슬라이드 -->
                <details v-if="collab" class="card fold-card" :open="foldOpen.collab"
                    @toggle="foldOpen.collab = $event.target.open">
                    <summary>
                        <span class="fold-title">센터 협업 현황</span>
                        <span class="fold-count">{{ collabVisible.length && !collabFilled ? `${collabVisible.length}개 센터` : `${collabFilled}건` }}</span>
                        <span v-if="!collabFilled" class="fold-hint">비우면 슬라이드가 빠집니다</span>
                    </summary>
                    <!-- PPT 표와 같은 모양: 센터 행 × 진행 현황 · 향후일정 열. -->
                    <!-- 내용이 있거나 방금 더한 센터만 줄로 보인다. PPT에는 다섯 줄이 모두 들어간다. -->
                    <div v-if="collabVisible.length" class="collab-grid">
                        <div class="collab-head" aria-hidden="true">
                            <span>지원</span>
                            <span v-for="col in collabColumns" :key="col.kind">{{ col.label }}</span>
                        </div>
                        <div v-for="code in collabVisible" :key="code" class="collab-row" :data-collab="code">
                            <span class="collab-code">
                                {{ code }}
                                <button type="button" class="btn btn-danger btn-small collab-drop"
                                    :aria-label="`${code} 센터 삭제`" @click="hideCenter(code)">삭제</button>
                            </span>
                            <div v-for="col in collabColumns" :key="col.kind" class="collab-cell"
                                role="group" :aria-label="`${code} ${col.label}`">
                                <span class="collab-cell-label">{{ col.label }}</span>
                                <div v-for="(_item, itemIndex) in collab.centers[code][col.kind]"
                                    :key="`collab-${code}-${col.kind}-${itemIndex}`" class="task-row">
                                    <input class="input" v-model="collab.centers[code][col.kind][itemIndex]"
                                        placeholder="내용을 입력하세요" />
                                    <button type="button" class="btn remove-btn" aria-label="이 항목 삭제"
                                        @click="removeCollabItem(code, col.kind, itemIndex)">
                                        <X :size="14" aria-hidden="true" />
                                    </button>
                                </div>
                                <button type="button" class="btn add-btn" @click="addCollabItem(code, col.kind)">
                                    + 추가
                                </button>
                            </div>
                        </div>
                    </div>
                    <div v-if="collabHidden.length" class="collab-add" role="group" aria-label="센터 추가">
                        <span class="collab-add-label">센터 추가</span>
                        <button v-for="code in collabHidden" :key="code" type="button" class="btn btn-small"
                            @click="showCenter(code)">
                            + {{ code }}
                        </button>
                    </div>
                </details>

                <div class="card save-bar">
                    <div class="save-actions">
                        <button v-if="canEdit" type="button" class="btn btn-small" @click="reextractReport"
                            :disabled="isSaving || isReextracting">
                            {{ isReextracting ? "재추출 중..." : "재추출" }}
                        </button>
                        <button v-if="canEdit" class="btn btn-primary" @click="saveReport"
                            :disabled="isSaving || isReextracting">
                            {{ isSaving ? "저장 중..." : saveLabel }}
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div v-else class="empty-state">보고서 데이터가 없습니다.</div>

        <Teleport to="body">
            <div v-if="layoutPicker" class="app-dialog-overlay" @click.self="closeLayoutPicker(null)"
                @keydown.esc="closeLayoutPicker(null)">
                <div class="card app-dialog layout-dialog" role="dialog" aria-modal="true"
                    aria-labelledby="layout-dialog-title">
                    <h2 id="layout-dialog-title" class="app-dialog-message">PPT를 어떤 형식으로 만들까요?</h2>
                    <div class="layout-options" role="radiogroup" aria-labelledby="layout-dialog-title">
                        <button v-for="option in WEEKLY_LAYOUTS" :key="option.value" type="button" role="radio"
                            class="layout-option" :class="{ 'is-on': layoutPicker.choice === option.value }"
                            :aria-checked="layoutPicker.choice === option.value"
                            @click="layoutPicker.choice = option.value">
                            <span class="layout-option-name">{{ option.label }}</span>
                            <!-- 내 보고 앞부분을 주요 업무 현황 슬라이드 모양으로 줄여 그린다 -->
                            <span class="slide" aria-hidden="true">
                                <span class="slide-title">주요 업무 현황</span>
                                <span class="slide-table" :class="`is-${layoutPreviews[option.value].kind}`">
                                    <span v-if="layoutPreviews[option.value].kind === 'rows'" class="slide-head">구분</span>
                                    <span class="slide-head">진행 현황</span>
                                    <span class="slide-head is-next">향후일정</span>
                                    <template v-if="layoutPreviews[option.value].kind === 'rows'">
                                        <template v-for="(row, rowIndex) in layoutPreviews[option.value].rows"
                                            :key="`r-${rowIndex}`">
                                            <span class="slide-cell is-lead">{{ row.title }}</span>
                                            <span v-for="key in ['done', 'next']" :key="key" class="slide-cell">
                                                <span v-for="(line, lineIndex) in row[key]" :key="lineIndex"
                                                    class="slide-line">{{ line }}</span>
                                            </span>
                                        </template>
                                    </template>
                                    <template v-else>
                                        <span v-for="key in ['done', 'next']" :key="key" class="slide-cell">
                                            <span v-for="(line, lineIndex) in layoutPreviews[option.value][key]"
                                                :key="lineIndex" class="slide-line" :class="{ 'is-head': line.head }">
                                                {{ line.text }}
                                            </span>
                                        </span>
                                    </template>
                                </span>
                            </span>
                        </button>
                    </div>
                    <div class="app-dialog-actions">
                        <button type="button" class="btn" @click="closeLayoutPicker(null)">취소</button>
                        <button type="button" class="btn btn-primary" @click="closeLayoutPicker(layoutPicker.choice)">
                            {{ layoutPicker.forSave ? "이 형식으로 저장" : "이 형식으로" }}
                        </button>
                    </div>
                </div>
            </div>
        </Teleport>
    </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import useApi from "../composables/useApi";
import { useRoute, useRouter } from "vue-router";
import { useDialog } from "../composables/useDialog";
import { selectedUserId } from "../composables/useSelectedUser";
import { isAdmin } from "../composables/useSession";
import {
    COLLAB_CENTERS,
    WEEKLY_LAYOUTS,
    asCollab,
    layoutPreview,
    collabItemCount,
    deckExtrasCount,
    deckForSave,
    emptyEvent,
    emptyNotice,
    emptySection,
    formatDeck,
    groupDoneItems,
    nextWeekLabel,
    placeProjectSection,
    projectSectionOrder,
    toWeeklyDeck,
    visibleConfirmQuestions,
} from "../lib/weeklyDeck";
import { copyText } from "../lib/copyText";
import AppField from "./ui/AppField.vue";
import { X } from "lucide-vue-next";

const route = useRoute();
const router = useRouter();

const reportData = ref(null);
const userName = ref("");
const ownerMemberId = ref(null);
const isSaving = ref(false);
const isReextracting = ref(false);
const isEditing = ref(false);
const selectedDates = ref([]);
const isUnsaved = computed(() => String(route.params.id || "") === "new");
/** 읽기 화면의 진행 현황 분류 색. 일일보고와 같은 태그를 쓴다. */
const KIND_TONES = { done: "is-done", progress: "is-progress", issue: "is-issue", other: "is-next" };
const saveLabel = computed(() => (isUnsaved.value ? "저장" : "수정 저장"));
const isMine = computed(() => {
    if (ownerMemberId.value == null || selectedUserId.value == null) return false;
    return String(ownerMemberId.value) === String(selectedUserId.value);
});
const canEdit = computed(() => isMine.value || isAdmin.value);
const { getUsers, getWeeklyReportById, postCreateWeekly, postWeeklyReport, updateWeeklyReport } = useApi();
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
    ]
        .map((value) => String(value || "").trim())
        .filter(Boolean)
        .join(" · ");
});

const confirmQuestions = computed(() =>
    visibleConfirmQuestions(reportData.value?.confirmQuestions, reportData.value),
);

const removeAt = (list, index) => {
    list.splice(index, 1);
};

/** 가드 DOM 키. 제목을 키로 쓰면 글자마다 카드가 다시 만들어져 입력 포커스가 풀린다. */
const sectionKeys = new WeakMap();
let sectionKeySeq = 0;
const stableSectionKey = (section) => {
    let key = sectionKeys.get(section);
    if (!key) {
        sectionKeySeq += 1;
        key = `sec-${sectionKeySeq}`;
        sectionKeys.set(section, key);
    }
    return key;
};

const projectBlocks = computed(() =>
    projectSectionOrder(reportData.value).map((block) => ({
        key: stableSectionKey(block.done || block.next),
        done: block.done,
        next: block.next,
    })),
);

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

const activeBlock = ref(null);

const rememberBlock = (block) => {
    activeBlock.value = block;
};

const addProject = async () => {
    if (!reportData.value) return;
    const section = emptySection();
    const block = activeBlock.value || projectBlocks.value[0] || null;
    placeProjectSection(reportData.value, block, section);
    const key = stableSectionKey(section);
    await nextTick();
    const card = document.querySelector(`[data-project-key="${key}"]`);
    if (!(card instanceof HTMLElement)) return;
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    const input = card.querySelector("input");
    if (input instanceof HTMLElement) input.focus();
};

/* 공지, 금월·익월 이벤트, 센터 협업. 비면 PPTX에서 그 슬라이드가 빠진다. */

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

/** 편집은 센터별 모양으로만 한다. 예전 모양이나 빈 값은 처음 열 때 바꾼다. */
const collab = computed(() => {
    if (!reportData.value) return null;
    if (!reportData.value.collab?.centers) reportData.value.collab = asCollab(reportData.value.collab);
    return reportData.value.collab;
});

const collabRows = computed(() =>
    COLLAB_CENTERS.map((code) => {
        const row = collab.value?.centers?.[code] || {};
        return {
            code,
            done: (row.done || []).filter((item) => String(item || "").trim()),
            next: (row.next || []).filter((item) => String(item || "").trim()),
        };
    }).filter((row) => row.done.length || row.next.length),
);

const collabColumns = [
    { kind: "done", label: "진행 현황" },
    { kind: "next", label: "향후일정" },
];

const collabFilled = computed(() => collabItemCount(collab.value));

/* 접기 카드는 보고를 불러올 때만 "내용이 있으면 펼침"으로 정한다.
   개수에 실시간으로 묶으면 마지막 항목을 지우는 순간 카드가 닫힌다. */
const foldOpen = ref({ notices: false, events: false, collab: false });
/* 협업 편집에 보이는 센터. 불러올 때는 내용 있는 센터만, 이후에는 항목을 다 지워도 줄을 남긴다. */
const collabShown = ref([]);
watch(reportData, () => {
    foldOpen.value = {
        notices: notices.value.length > 0,
        events: eventCount.value > 0,
        collab: collabFilled.value > 0,
    };
    collabShown.value = collabRows.value.map((row) => row.code);
});
const collabVisible = computed(() => COLLAB_CENTERS.filter((code) => collabShown.value.includes(code)));
const collabHidden = computed(() => COLLAB_CENTERS.filter((code) => !collabShown.value.includes(code)));
/* 센터 줄을 빼면 그 센터 항목도 비운다. 내용이 있으면 한 번 묻는다. */
const hideCenter = async (code) => {
    const row = collab.value?.centers[code];
    if (!row) return;
    const filled = [...row.done, ...row.next].some((item) => String(item || "").trim());
    if (filled && !(await askConfirm("저장하기 전에는 보고서에 반영되지 않습니다.", {
        title: `${code} 협업 내용을 지울까요?`,
        confirmLabel: "삭제",
        danger: true,
    }))) return;
    collab.value.centers[code] = { done: [], next: [] };
    collabShown.value = collabShown.value.filter((shown) => shown !== code);
};

const showCenter = async (code) => {
    collabShown.value = [...collabShown.value, code];
    addCollabItem(code, "done");
    await nextTick();
    document.querySelector(`[data-collab="${code}"] input`)?.focus();
};

const addCollabItem = (code, kind) => {
    collab.value?.centers[code][kind].push("");
};

const removeCollabItem = (code, kind, index) => {
    collab.value?.centers[code][kind].splice(index, 1);
};

/* 센터·센터장은 매주 같은 값이다. 한 번 입력하면 다음 보고서에 자동으로 채운다. */
const CENTER_KEY = "dxel.weekly.center";
const DIRECTOR_KEY = "dxel.weekly.director";
const LAYOUT_KEY = "dxel.weekly.layout";

const layoutName = computed(
    () => WEEKLY_LAYOUTS.find((option) => option.value === reportData.value?.layout)?.label || "형식 고르기",
);

/* 형식 고르기 창. 저장 전에(새 초안이거나 아직 안 고른 보고) 또는 '미리보기'로 연다. */
const layoutPicker = ref(null);
const layoutPreviews = computed(() =>
    Object.fromEntries(WEEKLY_LAYOUTS.map((option) => [option.value, layoutPreview(reportData.value, option.value)])),
);
const pickLayout = (forSave) =>
    new Promise((resolve) => {
        const remembered = localStorage.getItem(LAYOUT_KEY);
        const choice = [reportData.value?.layout, remembered].find((value) =>
            WEEKLY_LAYOUTS.some((option) => option.value === value),
        );
        layoutPicker.value = { choice: choice || WEEKLY_LAYOUTS[0].value, forSave, resolve };
        nextTick(() => document.querySelector(".layout-option.is-on")?.focus());
    });
const closeLayoutPicker = (value) => {
    layoutPicker.value?.resolve(value);
    layoutPicker.value = null;
};
const changeLayout = async () => {
    const layout = await pickLayout(false);
    if (layout) reportData.value.layout = layout;
};

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
    if (data.layout) localStorage.setItem(LAYOUT_KEY, data.layout);
};



const WEEKLY_DRAFT_KEY = "weeklyDraft";

/* 저장된 보고는 읽기로 연다(읽으러 온 사람이 실수로 고치지 않게). 새 초안만 바로 수정으로 연다. */
const openForEdit = () => {
    isEditing.value = canEdit.value && isUnsaved.value;
    if (isEditing.value) growAllEditors();
};

const loadDraft = () => {
    const raw = sessionStorage.getItem(WEEKLY_DRAFT_KEY);
    if (!raw) {
        showAlert("저장 전 초안이 없습니다. 목록에서 다시 만들어 주세요.");
        return;
    }
    let draft;
    try {
        draft = JSON.parse(raw);
    } catch {
        showAlert("저장 전 초안을 읽지 못했습니다. 목록에서 다시 만들어 주세요.");
        return;
    }
    reportData.value = toWeeklyDeck(draft.report);
    selectedDates.value = Array.isArray(draft.selects) ? draft.selects : [];
    ownerMemberId.value = draft.memberId ?? selectedUserId.value ?? null;
    userName.value = reportData.value.author || "";
    applyRememberedHeader();
    openForEdit();
    if (!userName.value && ownerMemberId.value != null) {
        getUsers()
            .then((users) => {
                const found = users.find((user) => String(user.id) === String(ownerMemberId.value));
                userName.value = found ? found.name : `사용자 ${ownerMemberId.value}`;
            })
            .catch(() => {
                userName.value = `사용자 ${ownerMemberId.value}`;
            });
    }
};

watch(
    reportData,
    (newVal) => {
        if (newVal) sessionStorage.setItem("reportData", JSON.stringify(newVal));
        if (newVal && isUnsaved.value) {
            const raw = sessionStorage.getItem(WEEKLY_DRAFT_KEY);
            let draft = {};
            try {
                draft = raw ? JSON.parse(raw) : {};
            } catch {
                draft = {};
            }
            draft.report = newVal;
            sessionStorage.setItem(WEEKLY_DRAFT_KEY, JSON.stringify(draft));
        }
        growAllEditors();
    },
    { deep: true },
);

onMounted(async () => {
    const reportId = route.params.id;
    if (String(reportId) === "new") {
        loadDraft();
        return;
    }
    if (reportId) {
        try {
            const data = await getWeeklyReportById(reportId);
            reportData.value = toWeeklyDeck(data.report);
            selectedDates.value = Array.isArray(data.selectedDate) ? data.selectedDate : [];
            if (!reportData.value.author) {
                reportData.value.author = data.memberName || "";
            }
            userName.value = data.memberName || `사용자 ${data.memberId}`;
            ownerMemberId.value = data.memberId ?? null;
            applyRememberedHeader();
            sessionStorage.setItem("reportData", JSON.stringify(reportData.value));
            sessionStorage.setItem("selectedUser", String(data.memberId));
            openForEdit();
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

const reextractReport = async () => {
    if (!canEdit.value) {
        showAlert("자신의 보고만 다시 만들 수 있습니다.");
        return;
    }
    const dates = selectedDates.value;
    if (!dates.length) {
        showAlert("다시 뽑을 날짜가 없습니다. 목록에서 기간을 골라 주세요.");
        return;
    }
    const ok = await askConfirm("지금 고친 내용은 바뀝니다. 저장하기 전까지는 반영되지 않습니다.", {
        title: "일일보고로 다시 뽑을까요?",
        confirmLabel: "재추출",
    });
    if (!ok) return;
    const memberId = ownerMemberId.value ?? selectedUserId.value;
    if (memberId == null) {
        showAlert("사용자 정보가 없습니다.");
        return;
    }
    isReextracting.value = true;
    try {
        const response = await postWeeklyReport(memberId, dates);
        const nextDraft = response.data || {};
        if (!nextDraft.report) {
            showAlert("주간 보고서를 다시 만들지 못했습니다.");
            return;
        }
        const next = toWeeklyDeck(nextDraft.report);
        if (!next.author) next.author = userName.value;
        if (Array.isArray(nextDraft.selects) && nextDraft.selects.length) {
            selectedDates.value = nextDraft.selects;
        }
        if (isUnsaved.value) {
            const raw = sessionStorage.getItem(WEEKLY_DRAFT_KEY);
            let stored = {};
            try {
                stored = raw ? JSON.parse(raw) : {};
            } catch {
                stored = {};
            }
            stored.selects = selectedDates.value;
            stored.report = next;
            sessionStorage.setItem(WEEKLY_DRAFT_KEY, JSON.stringify(stored));
        }
        reportData.value = next;
        applyRememberedHeader();
        showAlert("일일보고로 다시 뽑았습니다. 저장해야 반영됩니다.");
    } catch (error) {
        const detail = error.response?.data?.detail;
        console.error("재추출 실패:", error);
        showAlert(detail || "재추출에 실패했습니다. 다시 시도해주세요.");
    } finally {
        isReextracting.value = false;
    }
};

const copyReport = async () => {
    if (!reportData.value) return;
    try {
        const copied = await copyText(formatDeck(reportData.value));
        if (!copied) throw new Error("copy failed");
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
            title:
                questions.length > 1
                    ? `저장 전 확인 ${index + 1}/${questions.length}`
                    : "저장 전 확인",
            help: question.ifNo || "아니면 고친 뒤 다시 저장하세요.",
            confirmLabel: "네, 맞아요",
            cancelLabel: "아니요, 고칠게요",
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
        await updateWeeklyReport(reportId, JSON.stringify(deckForSave(reportData.value)));
        showAlert("주간 보고서가 저장되었습니다.");
    } catch (error) {
        console.error("저장 실패:", error);
        showAlert("주간 보고서 저장에 실패했습니다.");
    } finally {
        isSaving.value = false;
    }
};

const createSavedReport = async () => {
    const raw = sessionStorage.getItem(WEEKLY_DRAFT_KEY);
    let draft = {};
    try {
        draft = raw ? JSON.parse(raw) : {};
    } catch {
        draft = {};
    }
    const selects = Array.isArray(draft.selects) ? draft.selects : [];
    if (!selects.length) {
        showAlert("저장할 날짜가 없습니다. 목록에서 다시 만들어 주세요.");
        return;
    }
    isSaving.value = true;
    try {
        rememberHeader();
        const created = await postCreateWeekly(
            draft.memberId ?? ownerMemberId.value,
            selects,
            JSON.stringify(deckForSave(reportData.value)),
        );
        sessionStorage.removeItem(WEEKLY_DRAFT_KEY);
        showAlert("주간 보고서가 저장되었습니다.");
        await router.replace(`/weekly-detail/${created.id}`);
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
    if (!route.params.id) {
        showAlert("저장할 주간 보고서 ID가 없습니다.");
        return;
    }
    if (isUnsaved.value && !(await askConfirmQuestions())) return;
    if (isUnsaved.value || !reportData.value.layout) {
        const layout = await pickLayout(true);
        if (!layout) return;
        reportData.value.layout = layout;
    }
    if (isUnsaved.value) {
        await createSavedReport();
        return;
    }
    await persistReport();
};
</script>

<style scoped src="../styles/components/weekly-detail.css"></style>
