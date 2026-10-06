<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import { selectedUserId } from "../composables/useSelectedUser";
import AppField from "./ui/AppField.vue";
import Report from "./report.vue";
import { COMPOSE_CHOICES } from "../lib/nav";
import { Mic, Square } from "lucide-vue-next";
import { useMeetingRecorder } from "../composables/useMeetingRecorder";
import { useMeetingStream } from "../composables/useMeetingStream";
import { formatClock, joinTranscript, liveTranscript } from "../lib/meetingAudio";
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
 * 녹음으로 채우기: 녹음하는 동안 소리를 받아 적기 서버(Qwen3-ASR)로 계속 흘려 보낸다. 서버는 말이 끊길 때마다
 * 발화 하나를 확정해 돌려주고, 말하는 중인 발화도 미리 보여 준다. 녹음을 멈추면 남은 소리를 마저 적고
 * 사내 용어로 교정한 뒤 안건 · 결정 · 후속 할 일로 정리한다. 녹취록은 기록에 함께 저장된다.
 */
const voiceError = ref("");
// 새 회의록은 녹음 단계(record)로 시작한다. 녹음을 멈추고 정리가 끝나면 양식(form)만 남는다.
// 저장된 회의록을 열면 바로 양식이다.
const meetingStage = ref("record");
const showsForm = computed(() => kind.value !== "meeting" || meetingStage.value === "form");
const summarizing = ref(false);
const summarizeSeconds = ref(0);
const summaryText = ref("");
// 정리가 실패하거나 연결이 끊기면 받아 적은 글을 다시 보여 줘서 잃지 않게 한다.
const showTranscript = ref(false);
// 다른 기록을 열거나 새로 쓰면 올라간다. 늦게 온 결과가 엉뚱한 기록에 붙지 않게 한다.
let voiceKey = 0;
let summarizeTimer = null;

/** 받아 적은 발화를 녹취록 뒤에 붙인다. 녹음을 끊었다 다시 하면 앞 녹음 뒤로 이어진다. */
const appendTranscript = (segments) => {
    form.transcript = segments.reduce((text, segment) => joinTranscript(text, segment.text), form.transcript);
};

const voiceStream = useMeetingStream({
    onDone: (result) => {
        appendTranscript(result.segments || []);
        summarize();
    },
    // 녹음 중 끊겼다. 받은 데까지는 녹취록에 남기고, 다시 녹음하거나 그대로 정리할 수 있게 한다.
    onError: (message, kept) => {
        stopRecording();
        voiceError.value = message;
        appendTranscript(kept);
        if (form.transcript.trim()) showTranscript.value = true;
    },
});
const streamPhase = voiceStream.phase;
const liveText = computed(() => liveTranscript(voiceStream.segments.value, voiceStream.partial.value));

const {
    recording,
    starting: micStarting,
    seconds: recordSeconds,
    level: micLevel,
    start: startRecording,
    stop: stopRecording,
} = useMeetingRecorder({
    onAudio: (pcm) => voiceStream.send(pcm),
});

function resetVoice() {
    voiceKey += 1;
    stopRecording();
    voiceStream.close();
    voiceError.value = "";
    summaryText.value = "";
    showTranscript.value = false;
}

const toggleRecording = async () => {
    voiceError.value = "";
    if (recording.value) {
        stopRecording();
        voiceStream.finish();
        return;
    }
    summaryText.value = "";
    showTranscript.value = false;
    const key = voiceKey;
    try {
        // 받아 적기 서버에 먼저 붙은 뒤 마이크를 연다. 첫마디가 서버에 닿기 전에 버려지지 않게 한다.
        await voiceStream.open();
        if (key !== voiceKey) return;
        await startRecording();
    } catch (error) {
        voiceStream.close();
        voiceError.value = error.message;
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
    if (streamPhase.value === "connecting") return "음성 인식 서버에 연결하는 중";
    if (micStarting.value) return "마이크 여는 중";
    if (recording.value) return `녹음 중 ${formatClock(recordSeconds.value)}`;
    if (streamPhase.value === "finishing") return "녹취록 마무리하는 중";
    if (streamPhase.value === "polishing") return "사내 용어로 다듬는 중";
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
    () => recording.value || micStarting.value || streamPhase.value !== "idle" || summarizing.value,
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
});

watch(selectedUserId, loadUserName);
</script>

<template>
    <div class="page is-wide">
        <div class="kind-bar">
            <nav class="app-tabs kind-switch" aria-label="작성">
                <router-link
                    v-for="item in COMPOSE_CHOICES"
                    :key="item.id"
                    :to="item.to"
                    class="app-tab"
                    :class="{ 'is-active': kind === item.id }"
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

                <section
                    v-if="!showsForm"
                    class="form-section record-stage"
                    :class="{ 'is-recording': recording }"
                    aria-labelledby="sec-voice"
                >
                    <h2 id="sec-voice" class="sr-only">회의 녹음</h2>
                    <!-- 녹음 단계의 주인공은 버튼 하나. 카드 가운데에 크게 두고, 나머지는 그 아래로 모은다. -->
                    <div class="record-center">
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
                        <p v-else class="record-help">
                            회의를 시작하면서 누르세요. 정지하면 제목, 안건, 결정, 할 일을 채운 회의록이 열립니다.
                        </p>
                    </div>
                    <div v-if="recording" class="voice-meter" aria-hidden="true">
                        <span :style="{ transform: `scaleX(${micLevel})` }" />
                    </div>
                    <div v-if="recording" ref="liveBox" class="live-text" aria-live="polite">
                        <p v-if="liveText">{{ liveText }}</p>
                        <p v-else class="live-empty">말하면 1~2초 뒤부터 여기에 받아 적습니다.</p>
                    </div>
                    <div v-else-if="showTranscript" class="live-text">
                        <p>{{ form.transcript }}</p>
                    </div>

                    <div v-if="voiceError" class="form-error voice-error" role="alert">
                        <span>{{ voiceError }}</span>
                        <button
                            v-if="showTranscript && !summarizing && !recording"
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
                <p v-if="summaryText" class="voice-note" role="status">{{ summaryText }}</p>

                <!-- 제목이 이 기록의 머리글이다. 다른 칸보다 크게 둬서 무엇을 쓰는지 먼저 보이게 한다. -->
                <input
                    id="work-title"
                    v-model="form.title"
                    class="title-input"
                    type="text"
                    aria-label="제목"
                    :required="kind === 'general'"
                    :placeholder="kind === 'general' ? '제목' : '제목 (비워 두면 내용으로 붙입니다)'"
                />

                <section class="form-section" aria-labelledby="sec-basic">
                    <h2 id="sec-basic" class="section-title">
                        {{ kind === "meeting" ? "회의 정보" : kind === "sales" ? "프로젝트" : "기본 정보" }}
                    </h2>
                    <div class="detail-grid">
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
                    </section>

                    <section class="form-section" aria-labelledby="sec-follow">
                        <div class="section-head">
                            <h2 id="sec-follow" class="section-title">후속 할 일</h2>
                            <button type="button" class="btn btn-small" @click="addFollowup">할 일 추가</button>
                        </div>
                        <!-- 한 할 일이 한 줄: 할 일 · 담당 · 기한 · 빼기. 좁은 화면에서는 두 줄. -->
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
                        </div>
                    </section>
                </template>

                <section v-else-if="kind === 'general'" class="form-section" aria-labelledby="sec-body">
                    <h2 id="sec-body" class="section-title">내용</h2>
                    <AppField label="본문" for-id="general-body">
                        <textarea id="general-body" v-model="form.body" v-autosize class="textarea grow" rows="6" required />
                    </AppField>
                </section>

                <template v-else>
                    <section class="form-section" aria-labelledby="sec-contact">
                        <h2 id="sec-contact" class="section-title">담당자</h2>
                        <div class="detail-grid">
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
                            <textarea id="sales-next" v-model="form.nextSteps" v-autosize class="textarea grow" rows="2" />
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

            <!-- 넓은 화면에서는 옆에 펼쳐 두고, 좁은 화면에서는 접어서 양식 아래 한 줄로 둔다. -->
            <details class="group-block side-list" :open="!isNarrow">
                <summary class="group-head">
                    <h2>내가 쓴 {{ KIND_LABELS[kind] }}</h2>
                    <span v-if="records.length" class="group-meta">{{ records.length }}건</span>
                </summary>
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
            </details>
        </div>
        </template>
    </div>
</template>

<style scoped>
/* 설정 화면과 같은 밑줄 탭. 설명은 탭 줄 아래 한 줄. */
.kind-bar {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
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

/* 섹션은 가는 선으로만 나눈다. 카드 안에 카드를 또 두지 않는다.
   container: 할 일 줄이 화면 폭이 아니라 이 양식의 폭을 보고 한 줄 · 두 줄을 고른다. */
.compose-layout .compose-card {
    --card-pad: var(--space-5);
    gap: 0;
    padding: var(--card-pad);
    container-type: inline-size;
}

/* 제목이 이 기록의 머리글. 테두리 상자 대신 큰 글자와 밑줄로 입력칸임을 보인다. */
.title-input {
    width: 100%;
    min-width: 0;
    margin: var(--space-4) 0 0;
    padding: var(--space-1) 0 var(--space-2);
    border: 0;
    border-bottom: 2px solid transparent;
    background: transparent;
    font: var(--fw-semibold) var(--fs-20) / var(--lh-tight) var(--sans);
    color: var(--text-strong);
    outline: none;
}

.title-input::placeholder {
    color: var(--text-muted);
    font-weight: var(--fw-medium);
}

.title-input:hover {
    border-bottom-color: var(--border);
}

.title-input:focus-visible {
    border-bottom-color: var(--accent);
}

.title-input + .form-section {
    margin-top: var(--space-3);
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

/* 곁들이는 짧은 값(프로젝트 · 일시 · 장소 · 참석자 · 연락처). 넓으면 한 줄에 여럿, 좁아지면 저절로 줄을 바꾼다. */
.detail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(200px, 100%), 1fr));
    gap: var(--space-3) var(--space-4);
}

/* 글 상자는 내용만큼만. 전역 최소 높이(200px) 때문에 두세 줄 글도 큰 빈 상자가 되던 것을 없앤다. */
.textarea.grow {
    min-height: 0;
    overflow-y: hidden;
    resize: none;
}

/* 할 일 하나가 한 줄: 할 일 · 담당 · 기한 · 빼기. 줄 사이는 틈으로만 나눈다. */
.follow-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.follow-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 140px) 152px auto;
    grid-template-areas: "task owner due remove";
    gap: var(--space-2);
    align-items: center;
}

.follow-task { grid-area: task; }
.follow-owner { grid-area: owner; }
.follow-due { grid-area: due; }
.follow-remove { grid-area: remove; }

.follow-row .input {
    width: 100%;
    min-width: 0;
}

/* 양식이 좁으면(모바일 · 좁은 창) 할 일은 윗줄, 담당 · 기한은 아랫줄. 한 할 일이 두 줄을 넘지 않는다. */
@container (max-width: 560px) {
    .follow-row {
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
        grid-template-areas:
            "task task remove"
            "owner due due";
        padding-bottom: var(--space-2);
        border-bottom: 1px solid var(--border);
    }

    .follow-row:last-child {
        padding-bottom: 0;
        border-bottom: 0;
    }
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

/* 정리 결과 한 줄. 녹음 단계가 사라진 뒤 날짜 줄 바로 아래에 남는다. */
.voice-note {
    margin: var(--space-3) 0 0;
    font-size: var(--fs-13);
    line-height: var(--lh-base);
    color: var(--text);
    word-break: keep-all;
}

.voice-skip {
    align-self: flex-start;
}

.voice-note + .form-section {
    margin-top: var(--space-3);
}

/* 녹음 단계: 버튼 하나가 카드 가운데. 녹음이 시작되면 시간 · 소리 막대 · 받아 적은 글이 그 아래로 붙는다. */
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
}

.record-stage {
    justify-content: center;
    min-height: min(440px, 60vh);
    gap: var(--space-4);
}

.record-stage.is-recording {
    justify-content: flex-start;
}

.record-center {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
    text-align: center;
}

.record-btn {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2);
    border: 0;
    border-radius: var(--radius);
    background: none;
    color: var(--text-strong);
    font: inherit;
    cursor: pointer;
}

/* 누르는 동그라미. 녹음 버튼이 동그란 것은 장치에서 익숙한 모양이라서다. 빛 · 깜빡임은 넣지 않는다. */
.record-disc {
    display: grid;
    place-items: center;
    width: 88px;
    height: 88px;
    border-radius: 50%;
    background: var(--accent);
    color: var(--text-on-accent);
    transition: background var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease);
}

.record-btn:hover:not(:disabled) .record-disc {
    background: var(--accent-hover);
}

.record-btn:active:not(:disabled) .record-disc {
    transform: scale(0.97);
}

.record-btn.is-stop .record-disc {
    background: var(--danger-fg);
}

.record-btn:focus-visible {
    outline: none;
}

.record-btn:focus-visible .record-disc {
    box-shadow: 0 0 0 4px var(--surface), 0 0 0 7px var(--accent);
}

.record-btn:disabled {
    cursor: default;
}

.record-btn:disabled .record-disc {
    background: var(--surface-soft);
    color: var(--text-muted);
}

.record-label {
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
}

.record-clock {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    margin: 0;
    font-size: var(--fs-24);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    font-variant-numeric: tabular-nums;
}

/* 점은 실제로 녹음 중일 때만 보인다. */
.record-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--danger-fg);
}

.record-status,
.record-help {
    margin: 0;
    max-width: 34em;
    font-size: var(--fs-14);
    line-height: var(--lh-base);
    color: var(--text-muted);
    word-break: keep-all;
    text-wrap: balance;
}

.record-status {
    color: var(--text-strong);
    font-weight: var(--fw-medium);
    font-variant-numeric: tabular-nums;
}

.record-stage .voice-meter {
    width: min(320px, 100%);
    align-self: center;
}

.record-stage .voice-error {
    justify-content: center;
    text-align: center;
}

.record-stage .voice-skip {
    align-self: center;
    min-height: var(--control-h-lg);
    color: var(--text-muted);
}

/* 저장은 오른쪽 끝, 삭제는 왼쪽 끝. 손이 가는 순서와 되돌릴 수 없는 버튼을 떼어 둔다.
   화면 아래에 붙어 있어서 긴 양식 중간에서도 저장할 수 있다. 모바일에서는 아래 탭 막대 위에 선다. */
.form-actions {
    position: sticky;
    bottom: var(--bottom-nav-offset, 0px);
    z-index: 2;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    justify-content: flex-end;
    margin: var(--space-2) calc(-1 * var(--card-pad)) calc(-1 * var(--card-pad));
    padding: var(--space-3) var(--card-pad);
    border-top: 1px solid var(--border);
    border-radius: 0 0 var(--radius) var(--radius);
    background: var(--surface);
}

/* 넓은 화면에서는 늘 펼쳐 둔다. 접는 것은 좁은 화면에서만. */
.side-list > summary {
    display: flex;
    justify-content: flex-start;
    gap: var(--space-2);
    list-style: none;
    pointer-events: none;
}

.side-list > summary .group-meta {
    margin-left: auto;
}

.side-list > summary::-webkit-details-marker {
    display: none;
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

    .compose-layout .compose-card {
        --card-pad: var(--space-4);
    }

    /* style.css가 767px 이하 입력칸을 16px !important로 묶는다(iOS 확대 방지).
       제목은 16px보다 커서 확대가 일어나지 않으니 머리글 크기를 지킨다. */
    .title-input {
        font-size: var(--fs-20) !important;
        margin-top: var(--space-3);
    }

    /* 목록은 접어 두고 "내가 쓴 회의록 6건" 한 줄만. 누르면 펼친다. */
    .side-list > summary {
        pointer-events: auto;
        cursor: pointer;
        min-height: var(--control-h-lg);
        align-items: center;
    }

    .side-list > summary .group-meta {
        margin-left: 0;
    }

    .side-list > summary::after {
        content: "펼치기";
        margin-left: auto;
        font-size: var(--fs-12);
        color: var(--text-muted);
    }

    .side-list[open] > summary::after {
        content: "접기";
    }

    .section-head .btn,
    .voice-controls .btn,
    .voice-error .btn,
    .form-actions .btn {
        min-height: var(--control-h-lg);
    }

    .follow-remove {
        min-height: var(--control-h-lg);
    }

    /* 아래에 붙는 막대라 한 줄로 둔다. 두 줄이면 탭 막대와 합쳐 화면 1/4을 가린다. */
    .form-actions {
        flex-wrap: nowrap;
    }

    .form-actions .btn-primary {
        flex: 1 1 auto;
    }


    .kind-hint {
        font-size: var(--fs-12);
    }
}
</style>
