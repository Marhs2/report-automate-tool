<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from "vue";
import { useRouter } from "vue-router";
import { ChevronDown, UploadCloud } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { useDialog } from "../composables/useDialog";
import {
    PASTE_TEMPLATES,
    applyTemplate,
    hasTypedContent,
    templateById,
} from "../lib/reportTemplates";
import { todayString, weekdayLabelOf } from "../lib/dateScope";
import { useMyWeek } from "../composables/useMyWeek";
import { myRecentReports } from "../lib/reportSummary";
import {
    linesToReportJson,
    onlyStructuredLineReport,
    orderProjectsByRecent,
    parseLineReport,
} from "../lib/lineReport.js";
import LineWriter from "./ui/line-writer.vue";

const {
    postReport,
    postReportPptx,
    getReportDraft,
    getReportDrafts,
    deleteReportDraft,
    postReportDraft,
    getUserActivities,
    getUsers,
    getProjectNames,
    postProjectName,
    getReports,
    postSaveReport,
} = useApi();
const router = useRouter();
const { alert: showAlert, confirm: askConfirm } = useDialog();

const input = ref("");
const file = ref(null);
const buttonType = ref("text");
/** 좁은 화면 기본은 한 줄씩 쓰기. 메신저 대화를 통째로 붙이려면 붙여넣기로 바꾼다. */
const pasteOnNarrow = ref(false);
const date = ref(todayString());

const aiLoading = ref(false);
const lineSaving = ref(false);
const draftSaving = ref(false);
const draftSavedAt = ref("");
const formError = ref("");
const userName = ref("");
const alreadySaved = ref(false);
const elapsed = ref(0);
const isDragging = ref(false);
const knownProjects = ref([]);
/** 오른쪽 칸: 회의록 · 영업보고 탭처럼 "내가 쓴 일일보고". */
const myReports = ref([]);
const { weekDays } = useMyWeek();
const todayIso = todayString();
const moreOpen = ref(false);
const TODAY_PLACEHOLDER = "예) MES 운영 문의 2건 처리했고, 엑셀 업로드 검증은 아직 하는 중. 도면이 안 와서 실측이 밀림";
const WEEK_STATE_LABELS = { saved: "제출함", today: "아직", missing: "빠짐", upcoming: "예정" };
const dateLabel = computed(() => {
    const [, month, day] = String(date.value || "").split("-").map(Number);
    if (!month || !day) return "";
    return `${month}월 ${day}일 ${weekdayLabelOf(date.value)}요일`;
});

/** 아직 제출 안 한 임시 저장. 제출하면 서버가 지운다. */
const myDrafts = ref([]);
const lineWriter = ref(null);
const isNarrow = ref(
    typeof window !== "undefined" &&
        window.matchMedia("(max-width: 860px)").matches,
);
let narrowQuery = null;
let elapsedTimer = null;
const useLines = computed(
    () => isNarrow.value && buttonType.value === "text" && !pasteOnNarrow.value,
);
const inputMode = computed(() => {
    if (buttonType.value === "file") return "file";
    return useLines.value ? "lines" : "paste";
});
const inputModes = computed(() =>
    isNarrow.value
        ? [
              { id: "lines", label: "한 줄씩" },
              { id: "paste", label: "붙여넣기" },
          ]
        : [
              { id: "paste", label: "텍스트" },
              { id: "file", label: "파워포인트 파일" },
          ],
);

const elapsedLabel = computed(() => {
    const minutes = Math.floor(elapsed.value / 60);
    const seconds = elapsed.value % 60;
    return minutes > 0 ? `${minutes}분 ${seconds}초` : `${seconds}초`;
});

const waitStages = [
    { label: "글을 읽고 있어요" },
    { label: "항목을 나누고 있어요" },
    { label: "문장을 다듬고 있어요" },
];

const waitStage = computed(() => {
    if (elapsed.value >= 20) return 2;
    if (elapsed.value >= 8) return 1;
    return 0;
});

const waitDateLabel = computed(() => {
    const [, month, day] = String(date.value || "").split("-");
    if (!month || !day) return "일일보고";
    return `${Number(month)}월 ${Number(day)}일`;
});

const startElapsedTimer = () => {
    stopElapsedTimer();
    elapsed.value = 0;
    elapsedTimer = setInterval(() => {
        elapsed.value += 1;
    }, 1000);
};

const stopElapsedTimer = () => {
    if (elapsedTimer !== null) {
        clearInterval(elapsedTimer);
        elapsedTimer = null;
    }
};

const getSelectedMemberId = () => {
    const value = selectedUserId.value;
    if (value === null || value === undefined || value === "선택") return null;
    const memberId = Number(value);
    return Number.isInteger(memberId) && memberId > 0 ? memberId : null;
};

const hasUser = computed(() => getSelectedMemberId() !== null);

const activeTemplateId = ref("");
const activeTemplate = computed(() => templateById(activeTemplateId.value));

/** 이미 쓴 글이 있으면 말없이 덧붙이지 않는다.
 *  저장된 하루 위에 템플릿이 붙어 버리면 사고다. 바꿀지 덧붙일지 먼저 묻는다. */
const insertTemplate = async (template) => {
    if (!hasTypedContent(input.value)) {
        activeTemplateId.value = template?.id || "";
        input.value = applyTemplate(input.value, template, "replace");
        return;
    }
    const replace = await askConfirm(
        `쓰던 내용을 '${template.label}' 형식으로 바꿀까요?`,
        {
            title: "형식 넣기",
            help: "아니요를 누르면 쓰던 내용 아래에 형식을 덧붙입니다.",
            confirmLabel: "바꾸기",
            cancelLabel: "아래에 덧붙이기",
        },
    );
    activeTemplateId.value = template?.id || "";
    input.value = applyTemplate(
        input.value,
        template,
        replace ? "replace" : "append",
    );
};

const loadUserName = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null) {
        userName.value = "";
        return;
    }
    try {
        const users = await getUsers();
        const found = users.find((u) => String(u.id) === String(memberId));
        userName.value = found ? found.name : `사용자 ${memberId}`;
    } catch {
        userName.value = `사용자 ${memberId}`;
    }
};

const loadSavedState = async () => {
    const memberId = getSelectedMemberId();
    alreadySaved.value = false;
    if (memberId === null || !date.value) return;
    try {
        const rows = await getUserActivities(
            Number(date.value.slice(0, 4)),
            Number(date.value.slice(5, 7)),
            date.value,
            date.value,
        );
        const mine = (rows || []).find(
            (row) => String(row.member_id) === String(memberId),
        );
        alreadySaved.value = Boolean(mine && (mine.activities || []).some((a) => a.count > 0));
    } catch {
        alreadySaved.value = false;
    }
};

/** 서버 시각은 SQLite CURRENT_TIMESTAMP(UTC) "2026-09-29 05:40:12". 내 시간 "14:40"으로 바꾼다. */
const draftTimeLabel = (value) => {
    const text = String(value || "").trim();
    const at = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(text) ? text : `${text.replace(" ", "T")}Z`);
    if (Number.isNaN(at.getTime())) return "저장됨";
    return `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
};

const loadDraft = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null || !date.value) return;
    // 제출된 글은 작성 칸에 다시 넣지 않는다. 남으면 지우고 새로 써야 한다.
    if (alreadySaved.value) {
        input.value = "";
        draftSavedAt.value = "";
        return;
    }
    try {
        const draft = await getReportDraft(memberId, date.value);
        if (alreadySaved.value || input.value.trim()) return;
        const raw = String(draft.raw_text || "");
        if (raw.trim()) draftSavedAt.value = draftTimeLabel(draft.updated_at);
        const structured = onlyStructuredLineReport(raw);
        // 한 줄씩 칸에 못 옮기는 글(메신저 대화 등)은 숨기지 않고 붙여넣기로 연다.
        if (useLines.value && raw.trim() && !structured.trim()) {
            pasteOnNarrow.value = true;
            input.value = raw;
            return;
        }
        input.value = useLines.value ? structured : raw;
    } catch (error) {
        if (error.response?.status !== 404) {
            console.error("원문 초안 불러오기 실패:", error);
        }
    }
};

const statusLabel = computed(() => {
    if (alreadySaved.value) return "제출됨";
    if (draftSavedAt.value) return `임시 저장 · ${draftSavedAt.value}`;
    return "미제출";
});

const statusDetail = computed(() => {
    if (alreadySaved.value) return "고쳐서 저장하면 내용이 바뀜";
    if (draftSavedAt.value) return "아직 제출 안 됨";
    return "";
});

const loadDrafts = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null) return;
    try {
        const rows = await getReportDrafts(memberId);
        myDrafts.value = Array.isArray(rows) ? rows : [];
    } catch {
        myDrafts.value = [];
    }
};

const draftDateLabel = (iso) => {
    const [, month, day] = String(iso || "").split("-");
    return month && day ? `${Number(month)}월 ${Number(day)}일` : String(iso || "");
};

/** 임시 저장한 글을 버린다. 제출한 보고는 건드리지 않는다. */
const discardDraft = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null || !draftSavedAt.value) return;
    const ok = await askConfirm("임시 저장한 글이 없어지고 되돌릴 수 없어요.", {
        title: `${draftDateLabel(date.value)} 임시 저장을 버릴까요?`,
        confirmLabel: "버리기",
        danger: true,
    });
    if (!ok) return;
    try {
        await deleteReportDraft(memberId, date.value);
        input.value = "";
        draftSavedAt.value = "";
        await loadDrafts();
    } catch (error) {
        formError.value = error.response?.data?.detail || "임시 저장을 버리지 못했습니다.";
    }
};

const loadProjects = async () => {
    let names = [];
    try {
        const rows = await getProjectNames();
        names = Array.isArray(rows) ? rows : [];
    } catch {
        names = [];
    }
    // 최근 순서와 오른쪽 목록은 있으면 좋은 것이다. 목록을 못 불러와도 등록된 이름으로 쓸 수 있어야 한다.
    let reports = [];
    try {
        reports = await getReports();
    } catch {
        reports = [];
    }
    knownProjects.value = orderProjectsByRecent(names, reports, getSelectedMemberId());
    myReports.value = myRecentReports(reports, getSelectedMemberId());
};

const registerProject = async (name) => {
    const value = String(name || "").trim();
    if (!value) return;
    if (!knownProjects.value.includes(value)) {
        knownProjects.value = [...knownProjects.value, value];
    }
    try {
        await postProjectName(value, "");
    } catch (error) {
        if (error.response?.status !== 409) {
            formError.value = error.response?.data?.detail || "프로젝트를 추가하지 못했습니다.";
        }
    }
};

const reportBody = () => input.value;

const refreshMeta = async () => {
    await loadUserName();
    await loadSavedState();
    await Promise.all([loadProjects(), loadDrafts()]);
};

const syncNarrow = () => {
    isNarrow.value = Boolean(narrowQuery?.matches);
    if (isNarrow.value && buttonType.value === "file") {
        buttonType.value = "text";
        pasteOnNarrow.value = false;
        file.value = null;
    }
};

onMounted(async () => {
    narrowQuery = window.matchMedia("(max-width: 860px)");
    syncNarrow();
    narrowQuery.addEventListener("change", syncNarrow);
    await refreshMeta();
    await loadDraft();
});
onUnmounted(() => {
    stopElapsedTimer();
    narrowQuery?.removeEventListener("change", syncNarrow);
    if (aiLoading.value) {
        document.documentElement.classList.remove("is-overlay-open");
    }
});
watch(date, async () => {
    input.value = "";
    activeTemplateId.value = "";
    draftSavedAt.value = "";
    await loadSavedState();
    await loadDraft();
});
watch(selectedUserId, async () => {
    input.value = "";
    draftSavedAt.value = "";
    await refreshMeta();
    await loadDraft();
});

const selectType = (nextType) => {
    if (nextType === "file") {
        if (isNarrow.value) return;
        buttonType.value = "file";
        return;
    }
    buttonType.value = "text";
    pasteOnNarrow.value = nextType === "paste";
};

const acceptFile = (selected) => {
    if (!selected) return false;
    if (!selected.name.toLowerCase().endsWith(".pptx")) {
        formError.value = "PPTX 파일만 올릴 수 있습니다.";
        file.value = null;
        return false;
    }
    formError.value = "";
    file.value = selected;
    return true;
};

const uploadFile = (event) => {
    const selected = event.target.files?.[0] || null;
    if (!acceptFile(selected)) event.target.value = "";
};

/* 드래그해서 놓기. 점선 박스 안의 '파일 고르기'만 되면 손이 한 번 더 간다. */
const onDragOver = (event) => {
    event.preventDefault();
    isDragging.value = true;
};

const onDragLeave = () => {
    isDragging.value = false;
};

const onDrop = (event) => {
    event.preventDefault();
    isDragging.value = false;
    acceptFile(event.dataTransfer?.files?.[0] || null);
};

const clearFile = () => {
    file.value = null;
};

/** AI를 돌리지 않고 원문만 저장한다. 고치려고 매번 추출할 필요가 없어야 한다. */
const saveDraft = async () => {
    const memberId = getSelectedMemberId();
    if (memberId === null) {
        formError.value = "로그인이 필요합니다.";
        router.push("/login");
        return;
    }
    if (!input.value.trim()) {
        formError.value = "저장할 내용을 입력해주세요.";
        return;
    }
    formError.value = "";
    draftSaving.value = true;
    try {
        await postReportDraft(reportBody(), date.value, memberId);
        const now = new Date();
        draftSavedAt.value = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
        await loadDrafts();
    } catch (error) {
        const detail = error.response?.data?.detail;
        formError.value = detail || "초안 저장에 실패했습니다.";
    } finally {
        draftSaving.value = false;
    }
};

const lineCount = computed(() => parseLineReport(input.value).lines.length);

/** 한 줄씩 쓴 보고는 사람이 이미 나눴다. AI 없이 그대로 저장하고, 문장 정리는 주간보고 AI가 맡는다. */
const saveLines = async () => {
    const blocked = lineWriter.value?.commitPending() || "";
    if (blocked) {
        formError.value = blocked;
        return;
    }
    const memberId = getSelectedMemberId();
    if (memberId === null) {
        formError.value = "로그인이 필요합니다.";
        router.push("/login");
        return;
    }
    const parsed = linesToReportJson(parseLineReport(input.value).lines);
    if (!parsed.projects.length) {
        formError.value = "한 줄 이상 넣은 뒤 저장하세요.";
        return;
    }
    if (alreadySaved.value) {
        const ok = await askConfirm(`${waitDateLabel.value}에 제출한 보고를 지금 쓴 내용으로 바꿀까요?`, {
            title: "이미 제출한 보고가 있어요",
            help: "바꾸면 전에 제출한 내용은 되돌릴 수 없어요.",
            confirmLabel: "바꾸기",
            cancelLabel: "취소",
            danger: true,
        });
        if (!ok) return;
    }
    formError.value = "";
    lineSaving.value = true;
    try {
        await postSaveReport(JSON.stringify(parsed, null, 2), input.value, memberId, date.value);
        input.value = "";
        showAlert("보고서를 저장했습니다.");
        await router.push("/team");
    } catch (error) {
        console.error("일일보고 저장 실패:", error);
        formError.value =
            error.response?.data?.detail || "저장하지 못했습니다. 입력한 내용은 그대로 있어요.";
    } finally {
        lineSaving.value = false;
    }
};

const sendReport = async () => {
    if (useLines.value) {
        const blocked = lineWriter.value?.commitPending() || "";
        if (blocked) {
            formError.value = blocked;
            return;
        }
    }

    const memberId = getSelectedMemberId();
    if (memberId === null) {
        formError.value = "로그인이 필요합니다.";
        router.push("/login");
        return;
    }

    if (buttonType.value === "text") {
        if (!input.value.trim()) {
            formError.value = "보고서 내용을 입력해주세요.";
            return;
        }
    } else if (!file.value) {
        formError.value = "PPTX 파일을 선택해주세요.";
        return;
    }

    formError.value = "";
    aiLoading.value = true;
    document.documentElement.classList.add("is-overlay-open");
    startElapsedTimer();

    try {
        let parsed;
        let rawText;

        if (buttonType.value === "text") {
            rawText = reportBody();
            parsed = await postReport(
                { content: rawText },
                date.value,
                memberId,
            );
        } else {
            const res = await postReportPptx(file.value, date.value, memberId);
            parsed = res.parsed;
            rawText = res.raw_text;
        }

        sessionStorage.setItem("reportData", JSON.stringify(parsed));
        sessionStorage.setItem("reportRaw", rawText);
        sessionStorage.setItem("reportDate", date.value);
        await router.push({ name: "report-result" });
    } catch (error) {
        console.error("보고서 전송 실패:", error);
        const detail = error.response?.data?.detail;
        const message =
            detail ||
            "보고서 전송에 실패했습니다. 입력한 내용은 유지되니 다시 시도해주세요.";
        formError.value = message;
        showAlert(message);
    } finally {
        stopElapsedTimer();
        aiLoading.value = false;
        document.documentElement.classList.remove("is-overlay-open");
    }
};
</script>

<template>
    <div class="daily-write">
        <div v-if="!hasUser" class="card">
            <p class="form-hint">로그인이 필요합니다.</p>
            <div class="form-actions">
                <router-link class="btn btn-primary" to="/login">로그인</router-link>
            </div>
        </div>

        <div v-else class="today">
            <div class="today-top">
                <p class="today-date">
                    {{ dateLabel }}
                    <span
                        class="today-status"
                        :class="alreadySaved ? 'is-saved' : draftSavedAt ? 'is-draft' : ''"
                        :title="statusDetail"
                    >· {{ statusLabel }}</span>
                </p>
                <ol v-if="weekDays.length" class="today-week" aria-label="이번 주 제출">
                    <li
                        v-for="day in weekDays"
                        :key="day.date"
                        class="today-day"
                        :class="[`is-${day.state}`, { 'is-current': day.date === date }]"
                        :aria-label="`${day.weekday}요일 ${WEEK_STATE_LABELS[day.state]}`"
                    >
                        <i aria-hidden="true"></i>{{ day.date === todayIso ? "오늘" : day.weekday }}
                    </li>
                </ol>
            </div>

            <div class="today-box" :class="{ 'is-lines': useLines }">
                <template v-if="useLines">
                    <LineWriter
                        ref="lineWriter"
                        v-model="input"
                        :projects="knownProjects"
                        @add-project="registerProject"
                    >
                        <template #dock>
                            <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
                            <button
                                v-if="lineCount"
                                type="button"
                                class="btn btn-primary line-send"
                                @click="saveLines"
                                :disabled="lineSaving"
                            >
                                {{ lineSaving ? "저장 중" : `저장 · ${lineCount}줄` }}
                            </button>
                        </template>
                    </LineWriter>
                </template>

                <textarea
                    v-else-if="buttonType === 'text'"
                    id="report-input"
                    v-model="input"
                    :placeholder="activeTemplate?.hint || TODAY_PLACEHOLDER"
                    aria-label="오늘 한 일"
                    rows="10"
                    class="today-input"
                ></textarea>

                <div
                    v-else
                    class="field file-drop-area today-drop"
                    :class="{ 'is-dragging': isDragging }"
                    @dragover="onDragOver"
                    @dragenter="onDragOver"
                    @dragleave="onDragLeave"
                    @drop="onDrop"
                >
                    <UploadCloud :size="22" aria-hidden="true" />
                    <p class="file-drop-copy">
                        PPTX 파일을 고르거나 여기로 놓으세요
                    </p>
                    <label class="file-drop-pick" for="pptx-input">파일 고르기</label>
                    <input
                        id="pptx-input"
                        class="file-drop-input"
                        type="file"
                        accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                        @change="uploadFile"
                    />
                    <p v-if="file" class="file-name">
                        {{ file.name }}
                        <button type="button" class="file-clear" @click="clearFile">지우기</button>
                    </p>
                </div>

                <div class="today-foot">
                    <span class="today-foot-note" role="status">
                        {{ draftSavedAt ? `${draftSavedAt}에 임시 저장됨` : alreadySaved ? "제출한 보고가 있어요" : "" }}
                    </span>
                    <button
                        type="button"
                        class="btn btn-ghost btn-small today-more-toggle"
                        :aria-expanded="moreOpen"
                        aria-controls="today-more"
                        @click="moreOpen = !moreOpen"
                    >
                        {{ moreOpen ? "접기" : "더 보기" }}
                        <ChevronDown :size="16" class="today-more-icon" aria-hidden="true" />
                    </button>
                </div>

                <div v-if="moreOpen" id="today-more" class="today-more">
                    <div class="today-more-row">
                        <label class="today-more-label" for="date">날짜</label>
                        <input type="date" id="date" class="input today-more-date" v-model="date" required />
                    </div>
                    <div class="today-more-row">
                        <span class="today-more-label">쓰는 방식</span>
                        <div class="seg" role="tablist" aria-label="입력 방식">
                            <button
                                v-for="mode in inputModes"
                                :key="mode.id"
                                type="button"
                                role="tab"
                                :aria-selected="inputMode === mode.id"
                                :class="{ 'is-on': inputMode === mode.id }"
                                @click="selectType(mode.id)"
                            >
                                {{ mode.label }}
                            </button>
                        </div>
                    </div>
                    <div v-if="buttonType === 'text' && !useLines" class="today-more-row">
                        <span class="today-more-label">틀 넣기</span>
                        <div class="template-chips" role="group" aria-label="붙여넣기 형식">
                            <button
                                v-for="template in PASTE_TEMPLATES"
                                :key="template.id"
                                type="button"
                                class="btn btn-small"
                                :class="{ on: activeTemplateId === template.id }"
                                :aria-pressed="activeTemplateId === template.id"
                                :title="template.hint"
                                @click="insertTemplate(template)"
                            >
                                {{ template.label }}
                            </button>
                        </div>
                    </div>
                    <div class="today-more-block">
                        <div class="today-more-head">
                            <span class="today-more-label">내가 쓴 일일보고</span>
                            <router-link v-if="myReports.length" class="today-more-link" to="/reports">전체 보기</router-link>
                        </div>
                        <!-- 임시 저장은 제출이 아니라 목록에 없다. 없어진 줄 알지 않게 따로 보여 준다. -->
                        <button
                            v-for="draft in myDrafts"
                            :key="draft.report_date"
                            type="button"
                            class="row"
                            :class="{ 'is-current': draft.report_date === date }"
                            @click="date = draft.report_date"
                        >
                            <span class="row-main">
                                <span class="row-title">{{ draft.preview || "내용 없음" }}</span>
                                <span class="row-sub">{{ draftDateLabel(draft.report_date) }} · 임시 저장 · 아직 제출 안 됨</span>
                            </span>
                        </button>
                        <p v-if="!myReports.length && !myDrafts.length" class="today-more-empty">아직 없어요. 제출하면 여기에 쌓여요.</p>
                        <router-link
                            v-for="row in myReports.slice(0, 5)"
                            :key="row.id"
                            class="row"
                            :to="`/report-result/${row.id}`"
                        >
                            <span class="row-main">
                                <span class="row-title">{{ row.title }}</span>
                                <span class="row-sub">{{ row.date }}</span>
                            </span>
                        </router-link>
                    </div>
                    <div v-if="draftSavedAt" class="today-more-row">
                        <button type="button" class="btn btn-danger btn-small" @click="discardDraft">이 초안 버리기</button>
                    </div>
                </div>
            </div>

            <p v-if="formError && !useLines" class="form-error" role="alert">
                {{ formError }}
            </p>

            <template v-if="!useLines">
                <p class="today-hint">줄글로 편하게 써도 돼요. 프로젝트와 완료 · 진행 · 이슈는 AI가 나누고, 결과를 확인한 뒤 저장하면 제출돼요.</p>
                <div class="today-actions">
                    <button
                        v-if="buttonType === 'text'"
                        type="button"
                        class="btn today-save"
                        @click="saveDraft"
                        :disabled="aiLoading || draftSaving || !input.trim()"
                    >
                        {{ draftSaving ? "저장 중..." : "임시 저장" }}
                    </button>
                    <button
                        type="button"
                        class="btn btn-primary today-send"
                        @click="sendReport"
                        :disabled="aiLoading"
                    >
                        {{ aiLoading ? "정리하는 중" : "AI로 정리하기" }}
                    </button>
                </div>
            </template>

            <router-link class="today-other" :to="{ path: '/compose', query: { kind: 'meeting' } }">
                회의록이나 영업보고 쓰기
            </router-link>
        </div>
    </div>
    <Teleport to="body">
        <div v-if="aiLoading" class="submit-wait" role="status" aria-live="polite">
            <div class="submit-wait-card">
                <p class="submit-wait-date">{{ waitDateLabel }}</p>
                <h2>{{ waitStages[waitStage].label }}</h2>
                <div class="submit-meter" aria-hidden="true">
                    <span :style="{ width: ['18%', '52%', '78%'][waitStage] }"></span>
                </div>
                <ol class="submit-steps">
                    <li
                        v-for="(stage, index) in waitStages"
                        :key="stage.label"
                        :class="{ 'is-done': index < waitStage, 'is-on': index === waitStage }"
                    >
                        {{ stage.label }}
                    </li>
                </ol>
                <p class="submit-wait-time">{{ elapsedLabel }} · 보통 10초에서 1분</p>
            </div>
        </div>
    </Teleport>
</template>

<style scoped src="../styles/components/report.css"></style>
