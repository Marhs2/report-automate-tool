<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import { selectedUserId } from "../composables/useSelectedUser";
import AppField from "./ui/AppField.vue";
import Report from "./report.vue";
import { Mic, Square } from "lucide-vue-next";
import { useMeetingRecorder } from "../composables/useMeetingRecorder";
import { useMeetingChunks } from "../composables/useMeetingChunks";
import { formatClock } from "../lib/meetingAudio";
import { summaryNote, summaryToForm } from "../lib/meetingSummary";

/** 글 상자를 내용 높이에 맞춘다. 비어 있거나 짧으면 작게, 길어지면 늘어난다. */
const fitHeight = (el) => {
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + 2}px`;
};
const vAutosize = {
    mounted(el) {
        fitHeight(el);
        el.addEventListener("input", () => fitHeight(el));
    },
    updated: fitHeight,
};

const narrowQuery = typeof window !== "undefined" ? window.matchMedia("(max-width: 860px)") : null;
const isNarrow = ref(Boolean(narrowQuery?.matches));
const onNarrowChange = (event) => {
    isNarrow.value = event.matches;
};

const KINDS = [
    { id: "meeting", label: "회의록" },
    { id: "sales", label: "영업보고" },
];
const KIND_LABELS = {
    meeting: "회의록",
    general: "일일보고",
    sales: "영업보고",
};

const route = useRoute();
const router = useRouter();
const { alert: showAlert, confirm: askConfirm } = useDialog();
const {
    getWorkRecords,
    getWorkRecord,
    postWorkRecord,
    putWorkRecord,
    deleteWorkRecord,
    getUsers,
    getProjectNames,
    summarizeMeeting,
} = useApi();

/** 프로젝트 칸 제안. 고객사 · 프로젝트 이름을 매번 다시 치지 않게 한다. */
const projectOptions = ref([]);
const loadProjectOptions = async () => {
    try {
        const rows = await getProjectNames();
        projectOptions.value = [
            ...new Set(
                (Array.isArray(rows) ? rows : [])
                    .map((row) => (typeof row === "string" ? row : row?.name || row?.project_name || ""))
                    .map((name) => String(name).trim())
                    .filter(Boolean),
            ),
        ];
    } catch {
        projectOptions.value = [];
    }
};

/* 일일보고 탭과 같은 머리줄(작성자 · 날짜 · 상태)을 쓰려고 이름을 불러온다. */
const userName = ref("");
const loadUserName = async () => {
    const id = selectedUserId.value;
    if (!id) {
        userName.value = "";
        return;
    }
    try {
        const users = await getUsers();
        const found = (users || []).find((u) => String(u.id) === String(id));
        userName.value = found ? found.name : "";
    } catch {
        userName.value = "";
    }
};

const kindFromQuery = (value) => {
    const next = String(value || "daily");
    if (next === "daily" || next === "general" || next === "cards") return "daily";
    return KINDS.some((item) => item.id === next) ? next : "meeting";
};

const kind = ref(kindFromQuery(route.query.kind));
const recordId = ref(null);
const records = ref([]);
// records가 어느 종류의 목록인지. 종류를 바꾸는 동안 앞 종류의 목록이 새 제목 아래 보이지 않게 한다.
const recordsKind = ref("");
const recordLoading = ref(false);
const isSaving = ref(false);
// 기록 하나를 못 받으면 양식 자리에, 목록을 못 받으면 목록 보드 안에 알린다.
const recordError = ref("");
const listError = ref("");
const formError = ref("");
let loadedKey = "";

// /compose/:id를 처음 열어 기록이 아직 붙지 않은 동안. 종류를 몰라서 양식 대신 빈 모양이나 오류를 보인다.
const recordPending = computed(() => Boolean(route.params.id) && kind.value === "daily");
const isDailyTab = computed(() => kind.value === "daily" && !route.params.id);
const activeKind = computed(() => (recordPending.value ? "" : kind.value));
const listReady = computed(() => recordsKind.value === kind.value);

const blankFollow = () => ({ task: "", owner: "", due: "" });

const today = () => {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${now.getFullYear()}-${month}-${day}`;
};

const form = reactive({
    title: "",
    reportDate: today(),
    projectName: "",
    heldAt: "",
    place: "",
    attendees: "",
    agenda: "",
    decisions: "",
    followups: [blankFollow()],
    body: "",
    contactName: "",
    phone: "",
    email: "",
    organization: "",
    jobTitle: "",
    progress: "",
    nextSteps: "",
    transcript: "",
});

const errorText = (error, fallback) => {
    const detail = error?.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    return fallback;
};

const resetForm = () => {
    form.title = "";
    form.reportDate = today();
    form.projectName = "";
    form.heldAt = "";
    form.place = "";
    form.attendees = "";
    form.agenda = "";
    form.decisions = "";
    form.followups = [blankFollow()];
    form.body = "";
    form.contactName = "";
    form.phone = "";
    form.email = "";
    form.organization = "";
    form.jobTitle = "";
    form.progress = "";
    form.nextSteps = "";
    form.transcript = "";
    formError.value = "";
    resetVoice();
    meetingStage.value = "record";
};

const applyRecord = (row) => {
    resetForm();
    recordId.value = row.id;
    kind.value = row.kind;
    form.title = row.title || "";
    form.reportDate = row.reportDate || today();
    form.projectName = row.projectName || "";
    form.heldAt = row.heldAt || "";
    form.place = row.place || "";
    form.attendees = row.attendees || "";
    form.agenda = row.agenda || "";
    form.decisions = row.decisions || "";
    form.followups = (row.followups || []).length
        ? row.followups.map((item) => ({
            task: item.task || "",
            owner: item.owner || "",
            due: item.due || "",
        }))
        : [blankFollow()];
    form.body = row.body || "";
    form.contactName = row.contactName || "";
    form.phone = row.phone || "";
    form.email = row.email || "";
    form.organization = row.organization || "";
    form.jobTitle = row.jobTitle || "";
    form.progress = row.progress || "";
    form.nextSteps = row.nextSteps || "";
    form.transcript = row.transcript || "";
    meetingStage.value = "form";
};

const loadRecords = async () => {
    const forKind = kind.value;
    if (!["meeting", "general", "sales"].includes(forKind)) {
        records.value = [];
        recordsKind.value = forKind;
        return;
    }
    records.value = await getWorkRecords(forKind);
    recordsKind.value = forKind;
};

/** 목록 보드의 다시 시도. 쓰던 양식은 그대로 두고 목록만 다시 받는다. */
const reloadRecords = async () => {
    listError.value = "";
    try {
        await loadRecords();
    } catch (error) {
        console.error("목록 조회 실패:", error);
        listError.value = errorText(error, "기록을 불러오지 못했습니다.");
    }
};

const loadFromRoute = async () => {
    const id = route.params.id;
    const key = id ? `edit:${id}` : `new:${route.query.kind || "daily"}`;
    if (key === loadedKey) return;
    loadedKey = key;
    recordError.value = "";
    listError.value = "";
    formError.value = "";
    let stage = "list";
    try {
        if (id) {
            stage = "record";
            recordLoading.value = true;
            const row = await getWorkRecord(id);
            recordLoading.value = false;
            applyRecord(row);
            stage = "list";
            await loadRecords();
            return;
        }
        recordId.value = null;
        const next = String(route.query.kind || "daily");
        if (next === "daily" || next === "general" || next === "cards") {
            kind.value = "daily";
            records.value = [];
            recordsKind.value = "daily";
            if (next !== "daily") {
                loadedKey = "";
                await router.replace({ path: "/compose", query: { kind: "daily" } });
            }
            return;
        }
        kind.value = KINDS.some((item) => item.id === next) ? next : "meeting";
        resetForm();
        await loadRecords();
    } catch (error) {
        loadedKey = "";
        console.error("작성 화면 조회 실패:", error);
        const message = errorText(error, "기록을 불러오지 못했습니다.");
        if (stage === "record") recordError.value = message;
        else listError.value = message;
    } finally {
        recordLoading.value = false;
    }
};

const retryRecord = () => {
    loadedKey = "";
    loadFromRoute();
};

const startNew = () => {
    loadedKey = "";
    router.push({ path: "/compose", query: { kind: kind.value } });
};

const openRecord = (id) => {
    loadedKey = "";
    router.push(`/compose/${id}`);
};

// 넓은 화면에서는 목록을 늘 펼쳐 둔다. 접고 펴는 것은 좁은 화면에서만.
const onListHeadClick = (event) => {
    if (!isNarrow.value) event.preventDefault();
};

const payload = () => {
    const base = {
        kind: kind.value,
        title: form.title.trim(),
        reportDate: form.reportDate,
        projectName: form.projectName.trim(),
    };
    if (kind.value === "meeting") {
        return {
            ...base,
            heldAt: form.heldAt,
            place: form.place.trim(),
            attendees: form.attendees.trim(),
            agenda: form.agenda.trim(),
            decisions: form.decisions.trim(),
            followups: form.followups
                .map((row) => ({
                    task: row.task.trim(),
                    owner: row.owner.trim(),
                    due: row.due,
                }))
                .filter((row) => row.task),
            transcript: form.transcript.trim(),
        };
    }
    if (kind.value === "general") {
        return { ...base, body: form.body.trim() };
    }
    return {
        ...base,
        contactName: form.contactName.trim(),
        phone: form.phone.trim(),
        email: form.email.trim(),
        organization: form.organization.trim(),
        jobTitle: form.jobTitle.trim(),
        progress: form.progress.trim(),
        nextSteps: form.nextSteps.trim(),
    };
};

/** 저장 전에 빈 필수 칸을 화면 안 문구로 알리고 그 칸으로 커서를 옮긴다.
 *  브라우저 말풍선은 금방 사라져 "눌러도 아무 반응이 없다"고 느끼게 했다. */
const composeForm = ref(null);
const missingField = () => {
    const el = composeForm.value?.querySelector(":invalid");
    if (el) {
        const label = composeForm.value.querySelector(`label[for="${el.id}"]`)?.textContent?.trim();
        return { el, text: `${label || "필수"} 칸을 채워 주세요.` };
    }
    if (kind.value === "sales" && !String(form.phone || "").trim() && !String(form.email || "").trim()) {
        return { el: document.getElementById("sales-phone"), text: "전화번호나 이메일 중 하나는 적어 주세요." };
    }
    return null;
};

const save = async () => {
    formError.value = "";
    const missing = missingField();
    if (missing) {
        formError.value = missing.text;
        missing.el?.focus();
        return;
    }
    // 저장하면 폼을 다시 채우면서 녹음도 끊긴다. 녹취록이 다 적힌 뒤에 저장한다.
    if (voiceBusy.value) {
        formError.value = "녹음을 멈추고 정리가 끝난 뒤에 저장해 주세요.";
        return;
    }
    isSaving.value = true;
    try {
        const body = payload();
        const saved = recordId.value
            ? await putWorkRecord(recordId.value, body)
            : await postWorkRecord(body);
        if (!recordId.value) {
            loadedKey = "";
            await router.replace(`/compose/${saved.id}`);
            showAlert("저장했습니다.");
            return;
        }
        applyRecord(saved);
        await loadRecords();
        showAlert("수정했습니다.");
    } catch (error) {
        formError.value = errorText(error, "저장하지 못했습니다.");
    } finally {
        isSaving.value = false;
    }
};

const remove = async () => {
    if (!recordId.value) return;
    const ok = await askConfirm(`${form.title || "이 기록"}을(를) 삭제할까요?`, {
        title: `${KIND_LABELS[kind.value]} 삭제`,
        confirmLabel: "삭제",
        help: "삭제하면 되돌릴 수 없어요.",
        danger: true,
    });
    if (!ok) return;
    try {
        await deleteWorkRecord(recordId.value);
        loadedKey = "";
        await router.push({ path: "/compose", query: { kind: kind.value } });
    } catch (error) {
        formError.value = errorText(error, "삭제하지 못했습니다.");
    }
};

/*
 * 녹음으로 채우기: 녹음을 5분씩 잘라 받아 적기 서버(Qwen3-ASR)로 보내고, 조각마다 사내 용어로 교정한
 * 글을 녹취록에 잇는다. 녹음을 멈추면 남은 소리까지 받아 적은 뒤 녹취록 전체를 한 번 요약해
 * 안건 · 결정 · 후속 할 일로 정리한다. 녹취록은 기록에 함께 저장된다.
 */
const voiceError = ref("");
// 새 회의록은 녹음 단계(record)로 시작한다. 녹음을 멈추고 정리가 끝나면 양식(form)만 남는다.
// 저장된 회의록을 열면 바로 양식이다.
const meetingStage = ref("record");
const showsForm = computed(() => kind.value !== "meeting" || meetingStage.value === "form");
const summarizing = ref(false);
const summarizeSeconds = ref(0);
const summaryText = ref("");
// 정리가 실패하거나 받아 적지 못한 조각이 있으면 받아 적은 글을 다시 보여 줘서 잃지 않게 한다.
const showTranscript = ref(false);
// 녹음을 멈춘 뒤 남은 조각을 받아 적는 동안.
const finishing = ref(false);
// 다른 기록을 열거나 새로 쓰면 올라간다. 늦게 온 결과가 엉뚱한 기록에 붙지 않게 한다.
let voiceKey = 0;
let summarizeTimer = null;

// 조각이 받아 적힐 때마다 녹취록을 회의 순서대로 다시 잇는다. 새 회의록은 빈 녹취록에서 시작한다.
const voiceChunks = useMeetingChunks({
    onText: (text) => {
        form.transcript = text;
    },
});
const pendingChunks = voiceChunks.pending;
const failedChunks = voiceChunks.failed;

const {
    recording,
    starting: micStarting,
    seconds: recordSeconds,
    level: micLevel,
    start: startRecording,
    stop: stopRecording,
} = useMeetingRecorder({
    onAudio: (samples) => voiceChunks.push(samples),
});

function resetVoice() {
    voiceKey += 1;
    stopRecording();
    voiceChunks.reset();
    finishing.value = false;
    voiceError.value = "";
    summaryText.value = "";
    showTranscript.value = false;
}

/** 남은 조각까지 받아 적고 요약한다. 받아 적지 못한 조각이 있으면 멈추고 다시 할지 묻는다. */
const finishAndSummarize = async () => {
    const key = voiceKey;
    voiceError.value = "";
    finishing.value = true;
    try {
        await voiceChunks.finish();
    } finally {
        if (key === voiceKey) finishing.value = false;
    }
    if (key !== voiceKey) return;
    if (failedChunks.value.length) {
        const minutes = Math.max(1, Math.round(failedChunks.value.reduce((sum, part) => sum + part.seconds, 0) / 60));
        voiceError.value = `녹음 ${failedChunks.value.length}조각(약 ${minutes}분)을 받아 적지 못했습니다. ${failedChunks.value[0].error || ""}`.trim();
        showTranscript.value = true;
        return;
    }
    await summarize();
};

/** 받아 적지 못한 조각을 버리고 받아 적은 데까지만 정리한다. */
const summarizeWithoutFailed = () => {
    voiceChunks.dropFailed();
    summarize();
};

const micDenied = ref(false);

const toggleRecording = async () => {
    voiceError.value = "";
    micDenied.value = false;
    if (recording.value) {
        stopRecording();
        await finishAndSummarize();
        return;
    }
    summaryText.value = "";
    showTranscript.value = false;
    try {
        await startRecording();
    } catch (error) {
        voiceError.value = error.message;
        micDenied.value = error.code === "mic-denied";
    }
};

/** 마이크가 없거나 녹음하지 않을 때. 받아 적은 글이 있으면 녹취록으로 함께 저장된다. */
const writeWithoutRecording = () => {
    voiceError.value = "";
    showTranscript.value = false;
    meetingStage.value = "form";
};

const startTimer = (counter) => {
    counter.value = 0;
    return setInterval(() => {
        counter.value += 1;
    }, 1000);
};

const summarize = async () => {
    const key = voiceKey;
    voiceError.value = "";
    if (!form.transcript.trim()) {
        voiceError.value = "받아 적은 말이 없습니다. 마이크 막대가 움직이는지 보고 다시 녹음해 주세요.";
        return;
    }
    summaryText.value = "";
    summarizing.value = true;
    summarizeTimer = startTimer(summarizeSeconds);
    try {
        const result = await summarizeMeeting(form.transcript, form.reportDate);
        if (key !== voiceKey) return;
        const values = summaryToForm(form, result);
        Object.assign(form, values);
        showTranscript.value = false;
        summaryText.value = summaryNote(values);
        meetingStage.value = "form";
    } catch (error) {
        if (key !== voiceKey) return;
        showTranscript.value = true;
        voiceError.value = errorText(error, "정리하지 못했습니다.");
    } finally {
        clearInterval(summarizeTimer);
        summarizing.value = false;
    }
};

const voiceStatus = computed(() => {
    if (micStarting.value) return "마이크 여는 중";
    if (recording.value) return `녹음 중 ${formatClock(recordSeconds.value)}`;
    if (finishing.value) return `남은 녹음 받아 적는 중 (${pendingChunks.value}조각)`;
    if (summarizing.value) return `정리하는 중 ${summarizeSeconds.value}초`;
    return "";
});

// 받아 적은 글이 길어지면 상자 맨 아래(가장 최근 말)를 보여 준다.
const liveBox = ref(null);
watch(() => form.transcript, async () => {
    await nextTick();
    if (liveBox.value) liveBox.value.scrollTop = liveBox.value.scrollHeight;
});

const voiceBusy = computed(
    () => recording.value || micStarting.value || finishing.value || summarizing.value,
);

onBeforeUnmount(() => {
    narrowQuery?.removeEventListener("change", onNarrowChange);
    clearInterval(summarizeTimer);
});

const addFollowup = () => {
    form.followups.push(blankFollow());
};

const removeFollowup = (index) => {
    form.followups.splice(index, 1);
    if (form.followups.length === 0) form.followups.push(blankFollow());
};

const dotDate = (value) => {
    const [year, month, day] = String(value || "").split("T")[0].split("-");
    if (!year || !month || !day) return value || "";
    return `${year}.${Number(month)}.${Number(day)}`;
};

watch(
    () => [route.params.id, route.query.kind],
    () => {
        loadFromRoute();
    },
);

onMounted(() => {
    narrowQuery?.addEventListener("change", onNarrowChange);
    document.title = "작성";
    loadFromRoute();
    loadUserName();
    loadProjectOptions();
});

watch(selectedUserId, loadUserName);
</script>

<template>
    <div class="page is-wide">
        <nav class="seg kind-seg" aria-label="작성할 보고">
            <router-link
                v-for="item in COMPOSE_CHOICES"
                :key="item.id"
                :to="item.to"
                :class="{ 'is-on': activeKind === item.id }"
                :aria-current="activeKind === item.id ? 'page' : null"
            >
                {{ item.label }}
            </router-link>
        </nav>

        <Report v-if="isDailyTab" />

        <div v-else class="compose-layout">
            <div v-if="recordPending && !recordError" class="compose-main compose-skeleton" aria-busy="true">
                <p class="sr-only" role="status">기록을 불러오는 중</p>
                <div class="save-bar" aria-hidden="true">
                    <span class="skel is-control" />
                </div>
                <div class="card board" aria-hidden="true">
                    <div class="skel-head"><span class="skel is-heading" /></div>
                    <div class="board-body skel-grid">
                        <span v-for="n in 4" :key="n" class="skel-field">
                            <span class="skel is-label" />
                            <span class="skel is-control" />
                        </span>
                    </div>
                </div>
            </div>

            <section v-else-if="recordError" class="card board compose-main" aria-label="기록 열기">
                <div class="board-body load-fail">
                    <p class="fail-text" role="alert">{{ recordError }}</p>
                    <button type="button" class="btn" @click="retryRecord">다시 시도</button>
                </div>
            </section>

            <form v-else ref="composeForm" class="compose-main compose-form" novalidate @submit.prevent="save">
                <div class="save-dock">
                    <div class="save-bar">
                        <input
                            id="work-date"
                            v-model="form.reportDate"
                            class="input save-date"
                            type="date"
                            aria-label="작성 날짜"
                            required
                        />
                        <span v-if="recordLoading" class="save-status save-loading" role="status">불러오는 중</span>
                        <span v-else class="status-chip save-status" :class="recordId ? 'is-saved' : 'is-draft'">
                            {{ recordId ? "저장됨" : `새 ${KIND_LABELS[kind]}` }}
                        </span>
                        <div v-if="showsForm" class="save-actions">
                            <div v-if="recordId" class="save-more">
                                <button type="button" class="btn btn-danger" @click="remove">삭제</button>
                                <button type="button" class="btn" @click="startNew">새로 작성</button>
                            </div>
                            <button type="submit" class="btn btn-primary" :disabled="isSaving">
                                {{ isSaving ? "저장 중" : recordId ? "수정" : "저장" }}
                            </button>
                        </div>
                        <p v-if="showsForm && formError" class="save-error" role="alert">{{ formError }}</p>
                    </div>
                </div>

                <section
                    v-if="!showsForm"
                    class="card board record-board"
                    :class="{ 'is-recording': recording }"
                    aria-labelledby="sec-voice"
                >
                    <div class="board-head">
                        <h2 id="sec-voice" class="board-title">녹음으로 채우기</h2>
                    </div>
                    <div class="record-body">
                        <button
                            type="button"
                            class="record-btn"
                            :class="{ 'is-stop': recording }"
                            :disabled="micStarting || (!recording && voiceBusy)"
                            @click="toggleRecording"
                        >
                            <span class="record-disc" aria-hidden="true">
                                <Square v-if="recording" :size="26" fill="currentColor" />
                                <Mic v-else :size="34" />
                            </span>
                            <span class="record-label">{{ recording ? "녹음 정지" : "녹음 시작" }}</span>
                        </button>
                        <p v-if="recording" class="record-clock" role="timer">
                            <span class="record-dot" aria-hidden="true" />{{ formatClock(recordSeconds) }}
                        </p>
                        <p v-else-if="voiceStatus" class="record-status" role="status">{{ voiceStatus }}</p>
                        <div v-if="recording" class="voice-meter" aria-hidden="true">
                            <span :style="{ transform: `scaleX(${micLevel})` }" />
                        </div>
                        <div v-if="recording && form.transcript" ref="liveBox" class="live-text" aria-live="polite">
                            <p>{{ form.transcript }}</p>
                        </div>
                        <div v-else-if="showTranscript" class="live-text">
                            <p>{{ form.transcript }}</p>
                        </div>

                        <div v-if="voiceError" class="voice-error" role="alert">
                            <p class="voice-error-text">{{ voiceError }}</p>
                            <ol v-if="micDenied" class="mic-help">
                                <li><b>브라우저</b> 주소창 왼쪽 아이콘 → 사이트 설정 → 마이크 <b>허용</b> → 새로고침</li>
                                <li><b>Mac</b> 시스템 설정 → 개인정보 보호 및 보안 → 마이크 → 쓰는 브라우저 켜기</li>
                                <li><b>Windows</b> 설정 → 개인 정보 및 보안 → 마이크 → 마이크 액세스 켜기</li>
                                <li><b>iPhone</b> 설정 → Safari → 마이크 → 허용</li>
                            </ol>
                            <div v-if="!voiceBusy && (failedChunks.length || showTranscript)" class="voice-retry">
                                <template v-if="failedChunks.length">
                                    <button type="button" class="btn btn-small" @click="finishAndSummarize">
                                        다시 받아 적기
                                    </button>
                                    <button type="button" class="btn btn-ghost btn-small" @click="summarizeWithoutFailed">
                                        받아 적은 데까지 정리
                                    </button>
                                </template>
                                <button v-else type="button" class="btn btn-small" @click="summarize">다시 정리</button>
                            </div>
                        </div>

                        <button v-if="!voiceBusy" type="button" class="btn voice-skip" @click="writeWithoutRecording">
                            녹음 없이 직접 쓰기
                        </button>
                    </div>
                </section>

                <template v-else>
                    <p v-if="summaryText" class="callout is-info summary-note" role="status">{{ summaryText }}</p>

                    <!-- 제목이 이 기록의 머리글이라 첫 보드의 머리줄 자리에 크게 둔다. -->
                    <section class="card board" aria-labelledby="sec-basic">
                        <h2 id="sec-basic" class="sr-only">
                            {{ kind === "meeting" ? "회의 정보" : kind === "sales" ? "프로젝트" : "기본 정보" }}
                        </h2>
                        <input
                            id="work-title"
                            v-model="form.title"
                            class="title-input"
                            type="text"
                            aria-label="제목"
                            :required="kind === 'general'"
                            :placeholder="kind === 'general' ? '제목' : '제목 (비워 두면 내용으로 붙입니다)'"
                        />
                        <div class="board-body">
                            <div class="field-grid">
                                <AppField
                                    :label="kind === 'sales' ? '프로젝트명' : '관련 프로젝트'"
                                    for-id="work-project"
                                >
                                    <input
                                        id="work-project"
                                        v-model="form.projectName"
                                        class="input"
                                        type="text"
                                        list="work-project-options"
                                        autocomplete="off"
                                        :required="kind === 'sales'"
                                    />
                                    <datalist id="work-project-options">
                                        <option v-for="name in projectOptions" :key="name" :value="name" />
                                    </datalist>
                                </AppField>
                                <template v-if="kind === 'meeting'">
                                    <AppField label="일시" for-id="meeting-at">
                                        <input id="meeting-at" v-model="form.heldAt" class="input" type="datetime-local" />
                                    </AppField>
                                    <AppField label="장소" for-id="meeting-place">
                                        <input id="meeting-place" v-model="form.place" class="input" type="text" />
                                    </AppField>
                                    <AppField label="참석자" for-id="meeting-people">
                                        <input
                                            id="meeting-people"
                                            v-model="form.attendees"
                                            class="input"
                                            type="text"
                                            placeholder="쉼표로 구분"
                                        />
                                    </AppField>
                                </template>
                            </div>
                        </div>
                    </section>

                    <template v-if="kind === 'meeting'">
                        <section class="card board" aria-labelledby="sec-meeting">
                            <div class="board-head">
                                <h2 id="sec-meeting" class="board-title">회의 내용</h2>
                            </div>
                            <div class="board-body">
                                <div class="pair-grid">
                                    <AppField label="안건" for-id="meeting-agenda">
                                        <textarea
                                            id="meeting-agenda"
                                            v-model="form.agenda"
                                            v-autosize
                                            class="textarea grow"
                                            rows="3"
                                            placeholder="- 논의한 주제"
                                        />
                                    </AppField>
                                    <AppField label="결정" for-id="meeting-decisions">
                                        <textarea
                                            id="meeting-decisions"
                                            v-model="form.decisions"
                                            v-autosize
                                            class="textarea grow"
                                            rows="3"
                                            placeholder="- 정해진 것"
                                        />
                                    </AppField>
                                </div>
                            </div>
                        </section>

                        <section class="card board" aria-labelledby="sec-follow">
                            <div class="board-head">
                                <h2 id="sec-follow" class="board-title">후속 할 일</h2>
                                <button type="button" class="btn btn-small" @click="addFollowup">할 일 추가</button>
                            </div>
                            <!-- 할 일 하나가 한 줄: 할 일 · 담당 · 기한 · 빼기. 보드가 좁으면 두 줄. -->
                            <div class="follow-list">
                                <div v-for="(row, index) in form.followups" :key="index" class="follow-row">
                                    <input
                                        v-model="row.task"
                                        class="input follow-task"
                                        type="text"
                                        placeholder="할 일"
                                        :aria-label="`후속 할 일 ${index + 1}`"
                                    />
                                    <input
                                        v-model="row.owner"
                                        class="input follow-owner"
                                        type="text"
                                        placeholder="담당"
                                        :aria-label="`후속 할 일 ${index + 1} 담당`"
                                    />
                                    <!-- 날짜 칸은 자리 표시 글을 못 보여서(iPhone은 빈 칸) 이름을 옆에 붙인다. -->
                                    <label class="follow-due">
                                        <span class="follow-due-label" aria-hidden="true">기한</span>
                                        <input
                                            v-model="row.due"
                                            class="input"
                                            type="date"
                                            :aria-label="`후속 할 일 ${index + 1} 기한`"
                                        />
                                    </label>
                                    <button
                                        type="button"
                                        class="btn btn-small btn-danger follow-remove"
                                        :aria-label="`후속 할 일 ${index + 1} 빼기`"
                                        @click="removeFollowup(index)"
                                    >
                                        빼기
                                    </button>
                                </div>
                            </div>
                        </section>
                    </template>

                    <section v-else-if="kind === 'general'" class="card board" aria-labelledby="sec-body">
                        <div class="board-head">
                            <h2 id="sec-body" class="board-title">내용</h2>
                        </div>
                        <div class="board-body">
                            <AppField label="본문" for-id="general-body">
                                <textarea
                                    id="general-body"
                                    v-model="form.body"
                                    v-autosize
                                    class="textarea grow"
                                    rows="6"
                                    required
                                />
                            </AppField>
                        </div>
                    </section>

                    <template v-else>
                        <section class="card board" aria-labelledby="sec-contact">
                            <div class="board-head">
                                <h2 id="sec-contact" class="board-title">담당자</h2>
                            </div>
                            <div class="board-body">
                                <div class="contact-grid">
                                    <AppField class="is-third" label="담당자명" for-id="sales-name">
                                        <input id="sales-name" v-model="form.contactName" class="input" type="text" required />
                                    </AppField>
                                    <AppField class="is-third" label="직함" for-id="sales-title">
                                        <input id="sales-title" v-model="form.jobTitle" class="input" type="text" />
                                    </AppField>
                                    <AppField class="is-third is-own-row" label="소속" for-id="sales-org">
                                        <input id="sales-org" v-model="form.organization" class="input" type="text" />
                                    </AppField>
                                    <AppField class="is-half" label="전화번호 (또는 이메일)" for-id="sales-phone">
                                        <input id="sales-phone" v-model="form.phone" class="input" type="tel" />
                                    </AppField>
                                    <AppField class="is-half" label="이메일" for-id="sales-email">
                                        <input id="sales-email" v-model="form.email" class="input" type="email" />
                                    </AppField>
                                </div>
                            </div>
                        </section>

                        <section class="card board" aria-labelledby="sec-progress">
                            <div class="board-head">
                                <h2 id="sec-progress" class="board-title">진행</h2>
                            </div>
                            <div class="board-body">
                                <div class="pair-grid">
                                    <AppField label="진행사항" for-id="sales-progress">
                                        <textarea
                                            id="sales-progress"
                                            v-model="form.progress"
                                            v-autosize
                                            class="textarea grow"
                                            rows="3"
                                            required
                                        />
                                    </AppField>
                                    <AppField label="추후 진행사항" for-id="sales-next">
                                        <textarea
                                            id="sales-next"
                                            v-model="form.nextSteps"
                                            v-autosize
                                            class="textarea grow"
                                            rows="3"
                                        />
                                    </AppField>
                                </div>
                            </div>
                        </section>
                    </template>
                </template>
            </form>

            <!-- 넓은 화면에서는 옆에 펼쳐 두고, 좁은 화면에서는 접어서 양식 아래 한 줄로 둔다. -->
            <details v-if="!recordPending" class="card board list-board" :open="!isNarrow || Boolean(listError)">
                <summary class="board-head list-head" :tabindex="isNarrow ? null : -1" @click="onListHeadClick">
                    <h2 class="board-title">내가 쓴 {{ KIND_LABELS[kind] }}</h2>
                    <span v-if="listReady && records.length" class="list-count">{{ records.length }}건</span>
                    <span class="list-toggle" aria-hidden="true" />
                </summary>
                <div v-if="listError" class="list-state is-error">
                    <p role="alert">{{ listError }}</p>
                    <button type="button" class="btn btn-small" @click="reloadRecords">다시 시도</button>
                </div>
                <div v-else-if="!listReady" class="list-skeleton" aria-busy="true">
                    <p class="sr-only" role="status">목록을 불러오는 중</p>
                    <span v-for="n in 3" :key="n" class="skel-row" aria-hidden="true">
                        <span class="skel is-title" />
                        <span class="skel is-sub" />
                    </span>
                </div>
                <p v-else-if="records.length === 0" class="list-state">아직 없어요. 저장하면 여기에 쌓여요.</p>
                <div v-else class="list-rows">
                    <button
                        v-for="row in records"
                        :key="row.id"
                        type="button"
                        class="row"
                        :class="{ 'is-current': row.id === recordId }"
                        :aria-current="row.id === recordId ? 'true' : null"
                        @click="openRecord(row.id)"
                    >
                        <span class="row-main">
                            <span class="row-title">{{ row.title }}</span>
                            <span class="row-sub">
                                {{ dotDate(row.reportDate) }}<template v-if="row.projectName"> · {{ row.projectName }}</template>
                            </span>
                        </span>
                    </button>
                </div>
            </details>
        </div>
    </div>
</template>

<style scoped src="../styles/components/compose.css"></style>
