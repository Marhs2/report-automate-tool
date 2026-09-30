<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import { selectedUserId } from "../composables/useSelectedUser";
import AppField from "./ui/AppField.vue";
import Report from "./report.vue";
import { COMPOSE_CHOICES } from "../lib/nav";
import { useMeetingRecorder } from "../composables/useMeetingRecorder";
import { formatClock, joinTranscript } from "../lib/meetingAudio";
import { summaryNote, summaryToForm } from "../lib/meetingSummary";
import {
    attendeesFromNames,
    labeledTranscript,
    overlapCount,
    speakerSummaries,
    spokenDuration,
} from "../lib/meetingSpeakers";

const KINDS = [
    { id: "meeting", label: "회의록" },
    { id: "sales", label: "영업보고" },
];
const KIND_LABELS = {
    meeting: "회의록",
    general: "일반보고",
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
    transcribeMeetingAudio,
    createMeetingSession,
    diarizeMeetingSession,
    deleteMeetingSession,
    summarizeMeeting,
} = useApi();

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
    const next = String(value || "meeting");
    if (next === "daily" || next === "general" || next === "cards") return "daily";
    return KINDS.some((item) => item.id === next) ? next : "meeting";
};

const kind = ref(kindFromQuery(route.query.kind));
const currentChoice = computed(() => COMPOSE_CHOICES.find((item) => item.id === kind.value));
const recordId = ref(null);
const records = ref([]);
const isLoading = ref(false);
const isSaving = ref(false);
const loadError = ref("");
const formError = ref("");
let loadedKey = "";

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
    if (!["meeting", "general", "sales"].includes(kind.value)) {
        records.value = [];
        return;
    }
    records.value = await getWorkRecords(kind.value);
};

const loadFromRoute = async () => {
    const id = route.params.id;
    const key = id ? `edit:${id}` : `new:${route.query.kind || "meeting"}`;
    if (key === loadedKey) return;
    loadedKey = key;
    isLoading.value = true;
    loadError.value = "";
    formError.value = "";
    try {
        if (id) {
            const row = await getWorkRecord(id);
            applyRecord(row);
            await loadRecords();
            return;
        }
        recordId.value = null;
        const next = String(route.query.kind || "meeting");
        if (next === "daily" || next === "general" || next === "cards") {
            kind.value = "daily";
            records.value = [];
            isLoading.value = false;
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
        loadError.value = errorText(error, "기록을 불러오지 못했습니다.");
    } finally {
        isLoading.value = false;
    }
};

const switchKind = (next) => {
    if (String(route.params.id || "") || kind.value !== next) {
        loadedKey = "";
    }
    router.push({ path: "/compose", query: { kind: next } });
};

const startNew = () => {
    loadedKey = "";
    router.push({ path: "/compose", query: { kind: kind.value } });
};

const openRecord = (id) => {
    loadedKey = "";
    router.push(`/compose/${id}`);
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

const save = async () => {
    formError.value = "";
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
    if (!(await askConfirm("이 기록을 삭제할까요?"))) return;
    try {
        await deleteWorkRecord(recordId.value);
        loadedKey = "";
        await router.push({ path: "/compose", query: { kind: kind.value } });
    } catch (error) {
        formError.value = errorText(error, "삭제하지 못했습니다.");
    }
};

/*
 * 녹음으로 채우기: 녹음하는 동안 5초 안팎 초안 조각을 받아 적어 바로 보여 주고,
 * 같은 소리를 24~30초로 이은 조각을 다시 받아 적어 녹취록으로 쓴다(맥락이 길어 덜 틀린다).
 * 녹취록용 조각은 음성 인식 서버의 녹음 세션에도 쌓는다. 녹음을 멈추면 회의 전체로 말한 사람을 나누고,
 * 둘 이상이면 이름을 붙인 뒤 안건 · 결정 · 후속 할 일로 정리한다. 녹취록은 기록에 함께 저장된다.
 * 세션을 못 열면(서버가 화자 분리를 지원하지 않거나 꺼져 있음) 말한 사람 없이 이전처럼 정리한다.
 */
// 녹취록용(24~30초) 조각 중 아직 결과를 못 받은 수. 정리는 이것이 0이 된 뒤에 한다.
const pendingPieces = ref(0);
const failedPieces = ref([]);
const voiceError = ref("");
// 새 회의록은 녹음 단계(record)로 시작한다. 녹음을 멈추고 정리가 끝나면 양식(form)만 남는다.
// 저장된 회의록을 열면 바로 양식이다.
const meetingStage = ref("record");
const showsForm = computed(() => kind.value !== "meeting" || meetingStage.value === "form");
// 이번 녹음에서 녹취록용 조각으로 확정된 글과 그 끝 시각(초). 초안은 그 뒤 부분만 보여 준다.
const liveFinal = ref("");
const liveFinalEnd = ref(0);
const liveDrafts = ref([]);
const liveText = computed(() =>
    liveDrafts.value
        .filter((draft) => draft.start >= liveFinalEnd.value)
        .reduce((text, draft) => joinTranscript(text, draft.text), liveFinal.value),
);
const summarizing = ref(false);
const summarizeSeconds = ref(0);
const summaryText = ref("");
// 정리가 실패하면 받아 적은 글을 다시 보여 줘서 잃지 않게 한다.
const showTranscript = ref(false);
// 녹음 정지를 눌렀고, 남은 조각이 다 적히면 정리해야 한다.
const summarizeWhenDone = ref(false);
let pieceQueue = Promise.resolve();
let draftQueue = Promise.resolve();
// 음성 인식 서버의 녹음 세션. 없으면 말한 사람을 나누지 않는다.
const sessionId = ref("");
const speakerNote = ref("");
const diarizing = ref(false);
const diarizeSeconds = ref(0);
// 둘 이상이 말했으면 정리 전에 이름을 붙인다. { segments, summaries }
const speakerStep = ref(null);
const speakerNames = reactive({});
const memberNames = ref([]);
let diarizeTimer = null;
let overlapWarning = "";
// 세션을 여는 중이면 녹취록용 조각은 그걸 기다린다. 첫 조각부터 세션에 들어가야 회의 전체를 나눈다.
let sessionOpening = null;
// 다른 기록을 열거나 새로 쓰면 올라간다. 늦게 온 결과가 엉뚱한 기록에 붙지 않게 한다.
let voiceKey = 0;
let summarizeTimer = null;

/** 화면용 초안. 실패하거나 녹음이 끝난 뒤 도착하면 버린다. 녹취록에는 쓰지 않는다. */
const transcribeDraft = (piece) => {
    const key = voiceKey;
    draftQueue = draftQueue.then(async () => {
        if (key !== voiceKey || !recording.value) return;
        try {
            const { text } = await transcribeMeetingAudio(piece.blob);
            if (key === voiceKey && recording.value) {
                liveDrafts.value = [...liveDrafts.value, { start: piece.start, text }];
            }
        } catch {
            // 초안은 화면 표시용이다. 같은 소리는 녹취록용 조각으로 다시 받아 적는다.
        }
    });
};

/** 세션이 사라졌으면(서버 재시작 등) 이번 녹음은 말한 사람 없이 받아 적는다. */
const transcribeFinal = async (blob) => {
    if (sessionOpening) await sessionOpening;
    if (!sessionId.value) return transcribeMeetingAudio(blob, { polish: true });
    try {
        return await transcribeMeetingAudio(blob, { polish: true, session: sessionId.value });
    } catch (error) {
        if (error?.response?.status !== 404) throw error;
        sessionId.value = "";
        speakerNote.value = "음성 인식 서버의 녹음 세션이 끊겨서 이번 녹음은 말한 사람을 나누지 않습니다.";
        return transcribeMeetingAudio(blob, { polish: true });
    }
};

const transcribePiece = (piece) => {
    const key = voiceKey;
    pendingPieces.value += 1;
    pieceQueue = pieceQueue.then(async () => {
        try {
            const { text } = await transcribeFinal(piece.blob);
            if (key !== voiceKey) return;
            form.transcript = joinTranscript(form.transcript, text);
            liveFinal.value = joinTranscript(liveFinal.value, text);
            liveFinalEnd.value = Math.max(liveFinalEnd.value, piece.end);
        } catch (error) {
            if (key !== voiceKey) return;
            failedPieces.value.push(piece);
            voiceError.value = errorText(error, "받아 적지 못한 부분이 있습니다.");
        } finally {
            if (key === voiceKey) pendingPieces.value -= 1;
        }
    });
};

const {
    recording,
    starting: micStarting,
    seconds: recordSeconds,
    level: micLevel,
    start: startRecording,
    stop: stopRecording,
} = useMeetingRecorder({
    onDraft: (blob, start) => transcribeDraft({ blob, start }),
    onFinal: (blob, start, end) => transcribePiece({ blob, start, end }),
});

const clearLive = () => {
    liveFinal.value = "";
    liveFinalEnd.value = 0;
    liveDrafts.value = [];
};

const dropSession = () => {
    if (sessionId.value) deleteMeetingSession(sessionId.value).catch(() => {});
    sessionId.value = "";
};

function resetVoice() {
    voiceKey += 1;
    stopRecording();
    dropSession();
    speakerStep.value = null;
    speakerNote.value = "";
    overlapWarning = "";
    for (const key of Object.keys(speakerNames)) delete speakerNames[key];
    pendingPieces.value = 0;
    failedPieces.value = [];
    voiceError.value = "";
    clearLive();
    summaryText.value = "";
    showTranscript.value = false;
    summarizeWhenDone.value = false;
}

const toggleRecording = async () => {
    voiceError.value = "";
    if (recording.value) {
        stopRecording();
        summarizeWhenDone.value = true;
        return;
    }
    clearLive();
    summaryText.value = "";
    showTranscript.value = false;
    speakerNote.value = "";
    try {
        await startRecording();
    } catch (error) {
        voiceError.value = error.message;
        return;
    }
    // 녹음은 바로 시작하고, 세션은 그동안 연다. 첫 녹취록용 조각(24초 뒤)보다 먼저 끝난다.
    // 이어서 다시 녹음하면 이전 세션을 이어 쓴다. 그래야 회의 전체로 말한 사람을 나눈다.
    if (!sessionId.value) {
        const key = voiceKey;
        sessionOpening = createMeetingSession()
            .then(({ id }) => {
                if (key === voiceKey) sessionId.value = id;
            })
            .catch(() => {
                if (key === voiceKey) {
                    speakerNote.value = "음성 인식 서버가 말한 사람 나누기를 지원하지 않아서, 말한 사람 없이 받아 적었습니다.";
                }
            })
            .finally(() => {
                sessionOpening = null;
            });
    }
};

const retryFailed = () => {
    const pieces = failedPieces.value;
    failedPieces.value = [];
    voiceError.value = "";
    pieces.forEach(transcribePiece);
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

/**
 * 녹음을 멈춘 뒤 할 일. 세션이 있으면 회의 전체로 말한 사람을 나누고, 둘 이상이면 이름 붙이기로 간다.
 * 나누기가 실패하면 받아 적은 그대로(말한 사람 없이) 정리한다.
 */
const afterRecording = async () => {
    summarizeWhenDone.value = false;
    if (!sessionId.value) {
        summarize();
        return;
    }
    const key = voiceKey;
    const id = sessionId.value;
    diarizing.value = true;
    diarizeTimer = startTimer(diarizeSeconds);
    try {
        const result = await diarizeMeetingSession(id);
        if (key !== voiceKey) return;
        // 서버가 나누고 나서 세션을 지운다.
        sessionId.value = "";
        const segments = result.segments || [];
        const count = overlapCount(segments);
        overlapWarning = count ? `여러 명이 동시에 말한 부분 ${count}곳은 받아 적은 글이 틀렸을 수 있습니다.` : "";
        if ((result.speakerCount || 0) >= 2) {
            speakerStep.value = { segments, summaries: speakerSummaries(segments) };
            return;
        }
        summarize();
    } catch (error) {
        if (key !== voiceKey) return;
        speakerNote.value = `말한 사람을 나누지 못해서 한 덩어리로 정리합니다. (${errorText(error, "음성 인식 서버 오류")})`;
        dropSession();
        summarize();
    } finally {
        clearInterval(diarizeTimer);
        diarizing.value = false;
    }
};

/** 이름을 붙였든 건너뛰었든, 말한 사람이 표시된 녹취록으로 정리한다. */
const finishSpeakers = (useNames) => {
    const step = speakerStep.value;
    if (!step) return;
    const names = useNames ? { ...speakerNames } : {};
    form.transcript = labeledTranscript(step.segments, names);
    if (!form.attendees.trim()) form.attendees = attendeesFromNames(names);
    speakerStep.value = null;
    summarize();
};

const loadMemberNames = async () => {
    try {
        memberNames.value = (await getUsers()).map((user) => user.name).filter(Boolean);
    } catch {
        memberNames.value = [];
    }
};

/** 받아 적지 못한 조각을 버리고 적힌 것만으로 정리한다. */
const skipFailed = () => {
    failedPieces.value = [];
    voiceError.value = "";
};

const summarize = async () => {
    const key = voiceKey;
    summarizeWhenDone.value = false;
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
        summaryText.value = [summaryNote(values), speakerNote.value, overlapWarning].filter(Boolean).join(" ");
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

// 녹음을 멈춘 뒤 남은 조각이 다 적히면 곧바로 정리한다. 실패한 조각이 있으면 사용자가 고를 때까지 기다린다.
watch(
    () => [summarizeWhenDone.value, recording.value, pendingPieces.value, failedPieces.value.length],
    ([waiting, isRecording, pendingCount, failedCount]) => {
        if (waiting && !isRecording && pendingCount === 0 && failedCount === 0) afterRecording();
    },
);

const voiceStatus = computed(() => {
    if (micStarting.value) return "마이크 여는 중";
    if (recording.value) return `녹음 중 ${formatClock(recordSeconds.value)}`;
    if (pendingPieces.value) return "녹취록 마무리하는 중";
    if (diarizing.value) return `말한 사람 나누는 중 ${diarizeSeconds.value}초`;
    if (summarizing.value) return `정리하는 중 ${summarizeSeconds.value}초`;
    return "";
});

// 받아 적은 글이 길어지면 상자 맨 아래(가장 최근 말)를 보여 준다.
const liveBox = ref(null);
watch(liveText, async () => {
    await nextTick();
    if (liveBox.value) liveBox.value.scrollTop = liveBox.value.scrollHeight;
});

const voiceBusy = computed(
    () =>
        recording.value ||
        micStarting.value ||
        pendingPieces.value > 0 ||
        diarizing.value ||
        summarizing.value ||
        Boolean(speakerStep.value),
);

onBeforeUnmount(() => {
    clearInterval(summarizeTimer);
    clearInterval(diarizeTimer);
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
    document.title = "작성";
    loadFromRoute();
    loadUserName();
    loadMemberNames();
});

watch(selectedUserId, loadUserName);
</script>

<template>
    <div class="page is-wide">
        <div class="kind-bar">
            <nav class="seg kind-switch" aria-label="작성">
                <router-link
                    v-for="item in COMPOSE_CHOICES"
                    :key="item.id"
                    :to="item.to"
                    :class="{ 'is-on': kind === item.id }"
                    :aria-current="kind === item.id ? 'page' : null"
                >
                    {{ item.label }}
                </router-link>
            </nav>
            <p class="kind-hint">{{ currentChoice?.hint }}</p>
        </div>

        <Report v-if="kind === 'daily'" />
        <template v-else>
        <p v-if="isLoading" class="list-status" role="status">불러오는 중</p>
        <p v-else-if="loadError" class="list-status is-error" role="alert">{{ loadError }}</p>

        <div class="compose-layout">
            <form class="card compose-card" @submit.prevent="save">
                <!-- 일일보고 탭과 같은 머리줄: 누가 · 언제 · 저장됐는지. -->
                <div class="write-head">
                    <input
                        id="work-date"
                        v-model="form.reportDate"
                        class="input write-date"
                        type="date"
                        aria-label="작성 날짜"
                        required
                    />
                    <span class="status-chip" :class="{ 'is-saved': recordId }">
                        {{ recordId ? "저장됨 · 수정 중" : `새 ${KIND_LABELS[kind]}` }}
                    </span>
                </div>

                <section v-if="!showsForm" class="form-section" aria-labelledby="sec-voice">
                    <h2 id="sec-voice" class="section-title">회의 녹음</h2>
                    <div v-if="!speakerStep" class="voice-controls">
                        <button
                            type="button"
                            class="btn"
                            :class="recording ? 'btn-danger' : 'btn-primary'"
                            :disabled="micStarting || (!recording && voiceBusy)"
                            @click="toggleRecording"
                        >
                            {{ recording ? "녹음 정지" : "녹음 시작" }}
                        </button>
                        <p v-if="voiceStatus" class="voice-status" :class="{ 'is-live': recording }" role="status">
                            {{ voiceStatus }}
                        </p>
                    </div>
                    <div v-if="recording" class="voice-meter" aria-hidden="true">
                        <span :style="{ transform: `scaleX(${micLevel})` }" />
                    </div>
                    <div v-if="recording" ref="liveBox" class="live-text" aria-live="polite">
                        <p v-if="liveText">{{ liveText }}</p>
                        <p v-else class="live-empty">말하면 5초쯤 뒤부터 여기에 받아 적습니다.</p>
                    </div>
                    <div v-else-if="showTranscript" class="live-text">
                        <p>{{ form.transcript }}</p>
                    </div>
                    <p v-if="speakerNote && !recording" class="field-help">{{ speakerNote }}</p>

                    <!-- 둘 이상이 말했으면 정리 전에 누가 누구인지 고른다. 담당자와 참석자에 이름이 들어간다. -->
                    <div v-if="speakerStep" class="speaker-step">
                        <h3 class="speaker-title">말한 사람 {{ speakerStep.summaries.length }}명</h3>
                        <p class="field-help">
                            누구인지 고르면 후속 할 일 담당자와 참석자에 이름이 들어갑니다. 모르면 비워 두세요.
                        </p>
                        <datalist id="member-names">
                            <option v-for="name in memberNames" :key="name" :value="name" />
                        </datalist>
                        <div v-for="item in speakerStep.summaries" :key="item.speaker" class="speaker-row">
                            <div class="speaker-meta">
                                <span class="speaker-label">{{ item.label }}</span>
                                <span class="speaker-time">{{ spokenDuration(item.seconds) }}</span>
                            </div>
                            <p class="speaker-sample">“{{ item.sample }}”</p>
                            <input
                                v-model="speakerNames[item.speaker]"
                                class="input speaker-name"
                                type="text"
                                list="member-names"
                                placeholder="이름"
                                :aria-label="`${item.label} 이름`"
                                @keydown.enter.prevent="finishSpeakers(true)"
                            />
                        </div>
                        <div class="speaker-actions">
                            <button type="button" class="btn btn-ghost btn-small" @click="finishSpeakers(false)">
                                이름 없이 정리
                            </button>
                            <button type="button" class="btn btn-primary" @click="finishSpeakers(true)">
                                이 이름으로 정리하기
                            </button>
                        </div>
                    </div>
                    <div v-if="voiceError" class="form-error voice-error" role="alert">
                        <span>{{ voiceError }}</span>
                        <template v-if="failedPieces.length && !recording">
                            <button type="button" class="btn btn-small" @click="retryFailed">
                                {{ failedPieces.length }}조각 다시 받아 적기
                            </button>
                            <button v-if="summarizeWhenDone" type="button" class="btn btn-small" @click="skipFailed">
                                빼고 정리
                            </button>
                        </template>
                        <button
                            v-else-if="showTranscript && !summarizing"
                            type="button"
                            class="btn btn-small"
                            @click="summarize"
                        >
                            다시 정리
                        </button>
                    </div>
                    <button
                        v-if="!voiceBusy"
                        type="button"
                        class="btn btn-ghost btn-small voice-skip"
                        @click="writeWithoutRecording"
                    >
                        녹음 없이 직접 쓰기
                    </button>
                </section>

                <template v-if="showsForm">
                <p v-if="summaryText" class="field-help voice-note" role="status">{{ summaryText }}</p>

                <section class="form-section" aria-labelledby="sec-basic">
                    <h2 id="sec-basic" class="section-title">기본 정보</h2>
                    <div class="field-grid">
                        <AppField label="제목" for-id="work-title" :class="{ 'span-2': kind === 'meeting' }">
                            <input
                                id="work-title"
                                v-model="form.title"
                                class="input"
                                type="text"
                                :placeholder="kind === 'general' ? '제목' : '비워 두면 내용으로 붙입니다'"
                            />
                        </AppField>
                        <AppField
                            :label="kind === 'sales' ? '프로젝트명' : '관련 프로젝트'"
                            for-id="work-project"
                        >
                            <input
                                id="work-project"
                                v-model="form.projectName"
                                class="input"
                                type="text"
                                :required="kind === 'sales'"
                            />
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
                </section>

                <template v-if="kind === 'meeting'">
                    <section class="form-section" aria-labelledby="sec-meeting">
                        <h2 id="sec-meeting" class="section-title">회의 내용</h2>
                        <AppField label="안건" for-id="meeting-agenda">
                            <textarea id="meeting-agenda" v-model="form.agenda" class="textarea" rows="4" />
                        </AppField>
                        <AppField label="결정" for-id="meeting-decisions">
                            <textarea id="meeting-decisions" v-model="form.decisions" class="textarea" rows="4" />
                        </AppField>
                    </section>

                    <section class="form-section" aria-labelledby="sec-follow">
                        <div class="section-head">
                            <h2 id="sec-follow" class="section-title">후속 할 일</h2>
                            <button type="button" class="btn btn-small" @click="addFollowup">할 일 추가</button>
                        </div>
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
                            <input
                                v-model="row.due"
                                class="input follow-due"
                                type="date"
                                :aria-label="`후속 할 일 ${index + 1} 기한`"
                            />
                            <button
                                type="button"
                                class="btn btn-small btn-danger follow-remove"
                                :aria-label="`후속 할 일 ${index + 1} 빼기`"
                                @click="removeFollowup(index)"
                            >
                                빼기
                            </button>
                        </div>
                    </section>
                </template>

                <section v-else-if="kind === 'general'" class="form-section" aria-labelledby="sec-body">
                    <h2 id="sec-body" class="section-title">내용</h2>
                    <AppField label="본문" for-id="general-body">
                        <textarea id="general-body" v-model="form.body" class="textarea" rows="8" required />
                    </AppField>
                </section>

                <template v-else>
                    <section class="form-section" aria-labelledby="sec-contact">
                        <h2 id="sec-contact" class="section-title">담당자</h2>
                        <div class="field-grid">
                            <AppField label="담당자명" for-id="sales-name">
                                <input id="sales-name" v-model="form.contactName" class="input" type="text" required />
                            </AppField>
                            <AppField label="직함" for-id="sales-title">
                                <input id="sales-title" v-model="form.jobTitle" class="input" type="text" />
                            </AppField>
                            <AppField label="소속" for-id="sales-org">
                                <input id="sales-org" v-model="form.organization" class="input" type="text" />
                            </AppField>
                            <AppField label="전화번호" for-id="sales-phone">
                                <input id="sales-phone" v-model="form.phone" class="input" type="tel" />
                            </AppField>
                            <AppField label="이메일" for-id="sales-email">
                                <input id="sales-email" v-model="form.email" class="input" type="email" />
                            </AppField>
                        </div>
                    </section>

                    <section class="form-section" aria-labelledby="sec-progress">
                        <h2 id="sec-progress" class="section-title">진행</h2>
                        <AppField label="진행사항" for-id="sales-progress">
                            <textarea id="sales-progress" v-model="form.progress" class="textarea" rows="4" required />
                        </AppField>
                        <AppField label="추후 진행사항" for-id="sales-next">
                            <textarea id="sales-next" v-model="form.nextSteps" class="textarea" rows="3" />
                        </AppField>
                    </section>
                </template>

                <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
                <div class="form-actions">
                    <button v-if="recordId" type="button" class="btn btn-danger" @click="remove">삭제</button>
                    <button v-if="recordId" type="button" class="btn" @click="startNew">새로 작성</button>
                    <button type="submit" class="btn btn-primary" :disabled="isSaving">
                        {{ isSaving ? "저장 중" : recordId ? "수정" : "저장" }}
                    </button>
                </div>
                </template>
            </form>

            <aside class="group-block side-list">
                <div class="group-head">
                    <h2>내가 쓴 {{ KIND_LABELS[kind] }}</h2>
                    <span v-if="records.length" class="group-meta">{{ records.length }}건</span>
                </div>
                <div class="group">
                    <p v-if="records.length === 0" class="group-empty">
                        아직 없어요. 저장하면 여기에 쌓여요.
                    </p>
                    <button
                        v-for="row in records"
                        :key="row.id"
                        type="button"
                        class="row"
                        :class="{ 'is-current': row.id === recordId }"
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
            </aside>
        </div>
        </template>
    </div>
</template>

<style scoped>
.kind-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2) var(--space-3);
}

.kind-hint {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text-muted);
    word-break: keep-all;
}

/* 머리줄은 일일보고 탭(report.vue .write-head)과 같은 모양. 탭을 바꿔도 누가 · 언제 · 상태가 같은 자리에 있다. */
.write-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2) var(--space-3);
}

.write-author {
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.write-date {
    width: auto;
    height: var(--control-h-sm);
    font-size: var(--fs-13);
}

/* 섹션은 가는 선으로만 나눈다. 카드 안에 카드를 또 두지 않는다. */
.compose-layout .compose-card {
    gap: 0;
}

.form-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-4) 0;
    border-top: 1px solid var(--border);
}

.write-head + .form-section {
    margin-top: var(--space-4);
}

.section-title {
    margin: 0;
    font-size: var(--fs-14);
    font-weight: var(--fw-bold);
    color: var(--text-strong);
}

.section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
}

/* 짧은 값(프로젝트 · 일시 · 장소 · 연락처)은 두 칸씩 나란히. 긴 글은 전체 폭. */
.field-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-3) var(--space-4);
}

.field-grid .span-2 {
    grid-column: 1 / -1;
}

/* 폼 폭이 480px 안팎이라 한 줄 표로 두면 할 일이 잘린다. 할 일은 전체 폭, 담당 · 기한 · 빼기는 아래 줄. */
.follow-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 150px auto;
    grid-template-areas:
        "task task task"
        "owner due remove";
    gap: var(--space-2);
    align-items: center;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius);
}

.follow-task { grid-area: task; }
.follow-owner { grid-area: owner; }
.follow-due { grid-area: due; }
.follow-remove { grid-area: remove; }

.follow-row .input {
    width: 100%;
    min-width: 0;
}

.compose-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(220px, 280px);
    gap: var(--space-4);
    align-items: start;
}

.card {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
}

.voice-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
}

.voice-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin: 0 0 0 var(--space-1);
    font-size: var(--fs-13);
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
}

/* 점은 실제로 녹음 중일 때만. 깜빡이지 않는다. */
.voice-status.is-live {
    color: var(--text-strong);
    font-weight: var(--fw-semibold);
}

.voice-status.is-live::before {
    content: "";
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--danger-fg);
}

/* 마이크 소리가 들어오는지 보여 주는 막대. 녹음 중에만 보인다. */
.voice-meter {
    height: 4px;
    border-radius: 2px;
    background: var(--border);
    overflow: hidden;
}

.voice-meter span {
    display: block;
    height: 100%;
    background: var(--accent);
    transform-origin: left;
}

.voice-error {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
}

/* 녹음 중에 받아 적은 글. 편집하지 않으니 입력칸이 아니라 읽는 상자로 둔다. */
.live-text {
    max-height: 240px;
    overflow-y: auto;
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    font-size: var(--fs-14);
    line-height: var(--lh-relaxed);
    color: var(--text);
    white-space: pre-wrap;
    word-break: keep-all;
    overflow-wrap: anywhere;
}

.live-text p {
    margin: 0;
}

.live-text .live-empty {
    color: var(--text-muted);
}

/* 말한 사람 이름 붙이기: 한 사람이 한 줄. 누구인지 알아보게 첫 말을 같이 보여 준다. */
.speaker-step {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
}

.speaker-title {
    margin: 0;
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.speaker-row {
    display: grid;
    grid-template-columns: 96px minmax(0, 1fr) 180px;
    gap: var(--space-2) var(--space-3);
    align-items: center;
    padding: var(--space-3) 0;
    border-top: 1px solid var(--border);
}

.speaker-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.speaker-label {
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.speaker-time {
    font-size: var(--fs-12);
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
}

.speaker-sample {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text);
    word-break: keep-all;
    overflow-wrap: anywhere;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.speaker-name {
    width: 100%;
    min-width: 0;
}

.speaker-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    align-items: center;
    gap: var(--space-2);
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
}

/* 정리 결과 한 줄. 녹음 단계가 사라진 뒤 날짜 줄 바로 아래에 남는다. */
.voice-note {
    margin: var(--space-3) 0 0;
}

.voice-skip {
    align-self: flex-start;
}

.voice-note + .form-section {
    margin-top: var(--space-3);
}

/* 저장은 오른쪽 끝, 삭제는 왼쪽 끝. 손이 가는 순서와 되돌릴 수 없는 버튼을 떼어 둔다. */
.form-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    justify-content: flex-end;
    padding-top: var(--space-4);
    border-top: 1px solid var(--border);
}

.form-actions .btn-danger {
    margin-right: auto;
}

.compose-card > .form-error {
    margin-bottom: var(--space-3);
}

.form-error,
.list-status {
    margin: 0;
    font-size: var(--fs-14);
}

.list-status {
    color: var(--text-muted);
}

.form-error,
.list-status.is-error {
    color: var(--danger-fg);
}

@media (max-width: 860px) {
    .compose-layout {
        grid-template-columns: 1fr;
    }

    /* 날짜는 한 줄 전체, 44px 터치 높이. report.vue 모바일 머리줄과 같다. */
    .write-head {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
    }

    .write-date {
        grid-column: 1 / -1;
        width: 100%;
        min-width: 0;
        height: var(--control-h-lg);
        font-size: var(--fs-16);
    }

    .write-head .status-chip {
        justify-self: start;
    }

    .field-grid {
        grid-template-columns: minmax(0, 1fr);
    }

    .speaker-row {
        grid-template-columns: minmax(0, 1fr);
    }

    .speaker-meta {
        flex-direction: row;
        align-items: baseline;
        gap: var(--space-2);
    }

    .speaker-name {
        min-height: var(--control-h-lg);
    }

    .speaker-actions .btn {
        min-height: var(--control-h-lg);
    }

    .section-head .btn,
    .voice-controls .btn,
    .voice-error .btn,
    .form-actions .btn {
        min-height: var(--control-h-lg);
    }

    /* 좁은 화면: 기한 칸이 반 폭이면 날짜가 잘린다. 담당은 한 줄, 기한 옆에 빼기. */
    .follow-row {
        grid-template-columns: minmax(0, 1fr) auto;
        grid-template-areas:
            "task task"
            "owner owner"
            "due remove";
    }

    .follow-remove {
        min-height: var(--control-h-lg);
    }

    .form-actions .btn-primary {
        flex: 1 1 100%;
        order: -1;
    }


    .kind-bar {
        flex-direction: column;
        gap: var(--space-2);
    }

    .kind-hint {
        font-size: var(--fs-12);
    }
}
</style>
