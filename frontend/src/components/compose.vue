<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";
import AppField from "./ui/AppField.vue";

const KINDS = [
    { id: "meeting", label: "회의록" },
    { id: "general", label: "일반보고" },
    { id: "sales", label: "영업보고" },
    { id: "cards", label: "명함" },
];

const route = useRoute();
const router = useRouter();
const { alert: showAlert, confirm: askConfirm } = useDialog();
const {
    getProjectNames,
    getWorkRecords,
    getWorkRecord,
    postWorkRecord,
    putWorkRecord,
    deleteWorkRecord,
    getBusinessCards,
    postBusinessCard,
    putBusinessCard,
    deleteBusinessCard,
} = useApi();

const kind = ref("meeting");
const recordId = ref(null);
const records = ref([]);
const cards = ref([]);
const projectNames = ref([]);
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
    saveCard: true,
    cardId: null,
});

const cardForm = reactive({
    id: null,
    name: "",
    organization: "",
    jobTitle: "",
    phone: "",
    email: "",
    memo: "",
});

const digits = (value) => String(value || "").replace(/\D/g, "");

const cardMatches = computed(() => {
    const name = form.contactName.trim().toLowerCase();
    if (!name) return [];
    const phone = digits(form.phone);
    const email = form.email.trim().toLowerCase();
    return cards.value.filter((card) => {
        if (String(card.name || "").trim().toLowerCase() !== name) return false;
        const cardPhone = digits(card.phone);
        const cardEmail = String(card.email || "").trim().toLowerCase();
        const phoneHit = phone && cardPhone && phone === cardPhone;
        const emailHit = email && cardEmail && email === cardEmail;
        return phoneHit || emailHit;
    });
});

const selectedCard = computed(() =>
    cards.value.find((card) => card.id === cardForm.id) || null,
);

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
    form.saveCard = true;
    form.cardId = null;
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
    form.saveCard = row.saveCard !== false;
    form.cardId = row.cardId || null;
};

const resetCardForm = () => {
    cardForm.id = null;
    cardForm.name = "";
    cardForm.organization = "";
    cardForm.jobTitle = "";
    cardForm.phone = "";
    cardForm.email = "";
    cardForm.memo = "";
    formError.value = "";
};

const applyCard = (card) => {
    cardForm.id = card.id;
    cardForm.name = card.name || "";
    cardForm.organization = card.organization || "";
    cardForm.jobTitle = card.jobTitle || "";
    cardForm.phone = card.phone || "";
    cardForm.email = card.email || "";
    cardForm.memo = card.memo || "";
    formError.value = "";
};

const loadCards = async () => {
    cards.value = await getBusinessCards();
};

const loadRecords = async () => {
    if (!["meeting", "general", "sales"].includes(kind.value)) {
        records.value = [];
        return;
    }
    records.value = await getWorkRecords(kind.value);
};

const loadNames = async () => {
    projectNames.value = await getProjectNames();
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
            if (row.kind === "sales") await loadCards();
            await loadRecords();
            return;
        }
        recordId.value = null;
        const next = String(route.query.kind || "meeting");
        kind.value = KINDS.some((item) => item.id === next) ? next : "meeting";
        resetForm();
        if (kind.value === "cards") {
            await loadCards();
            records.value = [];
        } else {
            if (kind.value === "sales") await loadCards();
            await loadRecords();
        }
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
        saveCard: form.saveCard,
        cardId: form.cardId ? Number(form.cardId) : null,
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
        await loadNames();
        if (saved.kind === "sales") await loadCards();
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

const cardPayload = () => ({
    name: cardForm.name.trim(),
    organization: cardForm.organization.trim(),
    jobTitle: cardForm.jobTitle.trim(),
    phone: cardForm.phone.trim(),
    email: cardForm.email.trim(),
    memo: cardForm.memo.trim(),
});

const saveCard = async () => {
    formError.value = "";
    isSaving.value = true;
    try {
        const editing = Boolean(cardForm.id);
        const saved = editing
            ? await putBusinessCard(cardForm.id, cardPayload())
            : await postBusinessCard(cardPayload());
        await loadCards();
        const fresh = cards.value.find((card) => card.id === saved.id) || saved;
        applyCard(fresh);
        showAlert(editing ? "명함을 수정했습니다." : "명함을 등록했습니다.");
    } catch (error) {
        formError.value = errorText(error, "명함을 저장하지 못했습니다.");
    } finally {
        isSaving.value = false;
    }
};

const removeCard = async () => {
    if (!cardForm.id) return;
    if (!(await askConfirm("이 명함을 삭제할까요? 연결된 영업보고는 남습니다."))) return;
    try {
        await deleteBusinessCard(cardForm.id);
        resetCardForm();
        await loadCards();
    } catch (error) {
        formError.value = errorText(error, "명함을 삭제하지 못했습니다.");
    }
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

onMounted(async () => {
    document.title = "작성";
    try {
        await loadNames();
    } catch (error) {
        console.error("프로젝트명 조회 실패:", error);
    }
    loadFromRoute();
});
</script>

<template>
    <div class="page">
        <div class="kind-switch" role="tablist" aria-label="작성 형식">
            <button
                v-for="item in KINDS"
                :key="item.id"
                type="button"
                class="btn"
                :class="{ 'btn-primary': kind === item.id }"
                role="tab"
                :aria-selected="kind === item.id"
                @click="switchKind(item.id)"
            >
                {{ item.label }}
            </button>
            <router-link class="btn" to="/report">일일보고</router-link>
        </div>

        <p v-if="isLoading" class="list-status" role="status">불러오는 중</p>
        <p v-else-if="loadError" class="list-status is-error" role="alert">{{ loadError }}</p>

        <div v-else-if="kind === 'cards'" class="compose-layout">
            <form class="card" @submit.prevent="saveCard">
                <AppField label="이름" for-id="card-name">
                    <input id="card-name" v-model="cardForm.name" class="input" type="text" required />
                </AppField>
                <AppField label="소속" for-id="card-org">
                    <input id="card-org" v-model="cardForm.organization" class="input" type="text" />
                </AppField>
                <AppField label="직함" for-id="card-title">
                    <input id="card-title" v-model="cardForm.jobTitle" class="input" type="text" />
                </AppField>
                <AppField label="전화번호" for-id="card-phone">
                    <input id="card-phone" v-model="cardForm.phone" class="input" type="tel" />
                </AppField>
                <AppField label="이메일" for-id="card-email">
                    <input id="card-email" v-model="cardForm.email" class="input" type="email" />
                </AppField>
                <AppField label="메모" for-id="card-memo">
                    <textarea id="card-memo" v-model="cardForm.memo" class="textarea" rows="3" />
                </AppField>
                <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary" :disabled="isSaving">
                        {{ cardForm.id ? "명함 수정" : "명함 등록" }}
                    </button>
                    <button type="button" class="btn" @click="resetCardForm">새로 입력</button>
                    <button v-if="cardForm.id" type="button" class="btn" @click="removeCard">삭제</button>
                </div>
                <div v-if="selectedCard && selectedCard.sales && selectedCard.sales.length" class="card-sales">
                    <p class="side-label">이 명함의 영업 기록</p>
                    <router-link
                        v-for="sale in selectedCard.sales"
                        :key="sale.id"
                        class="side-item"
                        :to="sale.href"
                    >
                        <span>{{ dotDate(sale.reportDate) }} · {{ sale.projectName }}</span>
                        <span v-if="sale.progress">{{ sale.progress }}</span>
                    </router-link>
                </div>
            </form>
            <aside class="side-list">
                <p class="side-label">등록된 명함</p>
                <p v-if="cards.length === 0" class="list-status">등록된 명함이 없습니다.</p>
                <button
                    v-for="card in cards"
                    :key="card.id"
                    type="button"
                    class="side-item"
                    :class="{ 'is-current': card.id === cardForm.id }"
                    @click="applyCard(card)"
                >
                    <span>{{ card.name }}</span>
                    <span>{{ card.organization || card.phone || card.email }}</span>
                </button>
            </aside>
        </div>

        <div v-else class="compose-layout">
            <form class="card" @submit.prevent="save">
                <AppField label="날짜" for-id="work-date">
                    <input id="work-date" v-model="form.reportDate" class="input" type="date" required />
                </AppField>
                <AppField label="제목" for-id="work-title">
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
                        list="known-project-names"
                        :required="kind === 'sales'"
                    />
                    <datalist id="known-project-names">
                        <option v-for="name in projectNames" :key="name" :value="name" />
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
                        <input id="meeting-people" v-model="form.attendees" class="input" type="text" />
                    </AppField>
                    <AppField label="안건" for-id="meeting-agenda">
                        <textarea id="meeting-agenda" v-model="form.agenda" class="textarea" rows="4" />
                    </AppField>
                    <AppField label="결정" for-id="meeting-decisions">
                        <textarea id="meeting-decisions" v-model="form.decisions" class="textarea" rows="4" />
                    </AppField>
                    <div class="followups">
                        <p class="side-label">후속 할 일</p>
                        <div v-for="(row, index) in form.followups" :key="index" class="follow-row">
                            <input v-model="row.task" class="input" type="text" placeholder="할 일" aria-label="후속 할 일" />
                            <input v-model="row.owner" class="input" type="text" placeholder="담당" aria-label="후속 담당" />
                            <input v-model="row.due" class="input" type="date" aria-label="후속 기한" />
                            <button type="button" class="btn btn-small" @click="removeFollowup(index)">빼기</button>
                        </div>
                        <button type="button" class="btn btn-small" @click="addFollowup">할 일 추가</button>
                    </div>
                </template>

                <template v-else-if="kind === 'general'">
                    <AppField label="본문" for-id="general-body">
                        <textarea id="general-body" v-model="form.body" class="textarea" rows="8" required />
                    </AppField>
                </template>

                <template v-else>
                    <AppField label="담당자명" for-id="sales-name">
                        <input id="sales-name" v-model="form.contactName" class="input" type="text" required />
                    </AppField>
                    <AppField label="전화번호" for-id="sales-phone">
                        <input id="sales-phone" v-model="form.phone" class="input" type="tel" />
                    </AppField>
                    <AppField label="이메일" for-id="sales-email">
                        <input id="sales-email" v-model="form.email" class="input" type="email" />
                    </AppField>
                    <AppField label="소속" for-id="sales-org">
                        <input id="sales-org" v-model="form.organization" class="input" type="text" />
                    </AppField>
                    <AppField label="직함" for-id="sales-title">
                        <input id="sales-title" v-model="form.jobTitle" class="input" type="text" />
                    </AppField>
                    <AppField label="진행사항" for-id="sales-progress">
                        <textarea id="sales-progress" v-model="form.progress" class="textarea" rows="4" required />
                    </AppField>
                    <AppField label="추후 진행사항" for-id="sales-next">
                        <textarea id="sales-next" v-model="form.nextSteps" class="textarea" rows="3" />
                    </AppField>
                    <label class="check">
                        <input v-model="form.saveCard" type="checkbox" />
                        명함으로도 등록
                    </label>
                    <p v-if="cardMatches.length" class="hint">
                        같은 이름과 연락처의 명함이 있습니다. 등록하면 비어 있는 소속·직함·연락처만 채웁니다.
                    </p>
                    <AppField v-if="cardMatches.length" label="연결할 명함" for-id="sales-card">
                        <select id="sales-card" v-model="form.cardId" class="input">
                            <option :value="null">자동으로 연결</option>
                            <option v-for="card in cardMatches" :key="card.id" :value="card.id">
                                {{ card.name }} · {{ card.organization || card.phone || card.email }}
                            </option>
                        </select>
                    </AppField>
                </template>

                <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary" :disabled="isSaving">
                        {{ recordId ? "수정" : "저장" }}
                    </button>
                    <button v-if="recordId" type="button" class="btn" @click="startNew">새로 작성</button>
                    <button v-if="recordId" type="button" class="btn" @click="remove">삭제</button>
                </div>
            </form>

            <aside class="side-list">
                <p class="side-label">내가 쓴 {{ KINDS.find((item) => item.id === kind)?.label }}</p>
                <p v-if="records.length === 0" class="list-status">아직 없습니다.</p>
                <button
                    v-for="row in records"
                    :key="row.id"
                    type="button"
                    class="side-item"
                    :class="{ 'is-current': row.id === recordId }"
                    @click="openRecord(row.id)"
                >
                    <span>{{ dotDate(row.reportDate) }} · {{ row.title }}</span>
                    <span v-if="row.projectName">{{ row.projectName }}</span>
                </button>
            </aside>
        </div>
    </div>
</template>

<style scoped>
.kind-switch {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
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

.form-actions,
.follow-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
}

.followups {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.follow-row .input {
    flex: 1 1 140px;
    min-width: 0;
}

.check {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--fs-14);
}

.hint,
.form-error,
.list-status,
.side-label {
    margin: 0;
    font-size: var(--fs-14);
}

.hint,
.side-label,
.list-status {
    color: var(--text-muted);
}

.form-error,
.list-status.is-error {
    color: var(--danger-fg);
}

.side-list,
.card-sales {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.side-item {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-1);
    width: 100%;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--text);
    text-align: left;
    text-decoration: none;
    cursor: pointer;
}

.side-item.is-current {
    border-color: var(--accent);
}

.side-item span:first-child {
    color: var(--text-strong);
    font-weight: var(--fw-medium);
}

@media (max-width: 860px) {
    .compose-layout {
        grid-template-columns: 1fr;
    }
}
</style>
