<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import { selectedUserId } from "../composables/useSelectedUser";
import AppField from "./ui/AppField.vue";
import Report from "./report.vue";
import { COMPOSE_CHOICES } from "../lib/nav";

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
    formError.value = "";
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

    .section-head .btn,
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
