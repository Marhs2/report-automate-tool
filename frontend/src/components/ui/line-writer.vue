<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import {
    KIND_FIELDS,
    LINE_KINDS,
    parseLineReport,
    scheduleLine,
    onlyStructuredLineReport,
    serializeLineReport,
} from "../../lib/lineReport.js";

const props = defineProps({
    modelValue: { type: String, default: "" },
    projects: { type: Array, default: () => [] },
});

const emit = defineEmits(["update:modelValue", "add-project"]);

const lines = ref([]);
const activeProject = ref("");
const kind = ref("완료");
const lineValue = ref("");
const scheduleTitle = ref("");
const addedNames = ref([]);
const newProjectName = ref("");
const addingProject = ref(false);
let lastEmitted = props.modelValue;
let nextId = 1;

const projectNames = computed(() => {
    const names = [];
    const add = (name) => {
        const value = String(name || "").trim();
        if (value && !names.includes(value)) names.push(value);
    };
    for (const name of props.projects) add(name);
    for (const name of addedNames.value) add(name);
    for (const line of lines.value) add(line.project);
    return names;
});

const rowsFor = (item) =>
    lines.value.filter(
        (line) => line.project === activeProject.value && line.kind === item,
    );

const chooseProject = (name) => {
    activeProject.value = name;
    closeProjectPopup();
};

const field = computed(() => KIND_FIELDS[kind.value]);

const publish = () => {
    const raw = serializeLineReport(lines.value);
    lastEmitted = raw;
    emit("update:modelValue", raw);
};

const hydrate = (raw) => {
    const canonical = onlyStructuredLineReport(raw);
    lines.value = parseLineReport(canonical).lines.map((line) => ({
        ...line,
        id: nextId++,
    }));
    if (canonical !== String(raw || "")) {
        lastEmitted = canonical;
        emit("update:modelValue", canonical);
        return;
    }
    lastEmitted = raw;
};

watch(
    () => props.modelValue,
    (value) => {
        if (value === lastEmitted) return;
        hydrate(value);
    },
    { immediate: true },
);

watch(
    projectNames,
    (names) => {
        if (!names.includes(activeProject.value)) {
            activeProject.value = names[0] || "";
        }
    },
    { immediate: true },
);

const selectKind = async (next) => {
    const switchingDate = (kind.value === "일정") !== (next === "일정");
    kind.value = next;
    if (switchingDate) {
        lineValue.value = "";
        scheduleTitle.value = "";
    }
    await nextTick();
    document.getElementById(next === "일정" ? "line-date" : "line-text")?.focus();
};

const addLine = () => {
    if (!activeProject.value) return;
    const text =
        kind.value === "일정"
            ? scheduleLine(lineValue.value, scheduleTitle.value)
            : lineValue.value.trim();
    if (!text) return;
    lines.value = [
        ...lines.value,
        { id: nextId++, project: activeProject.value, kind: kind.value, text },
    ];
    lineValue.value = "";
    scheduleTitle.value = "";
    publish();
};

const removeLine = (id) => {
    lines.value = lines.value.filter((line) => line.id !== id);
    publish();
};

const addProject = () => {
    const name = newProjectName.value.trim();
    if (!name) return;
    if (!addedNames.value.includes(name)) addedNames.value = [...addedNames.value, name];
    activeProject.value = name;
    closeProjectPopup();
    emit("add-project", name);
};

const openProjectPopup = () => {
    newProjectName.value = "";
    addingProject.value = true;
    document.documentElement.classList.add("is-overlay-open");
};

const closeProjectPopup = () => {
    addingProject.value = false;
    newProjectName.value = "";
    document.documentElement.classList.remove("is-overlay-open");
};

const onProjectKey = (event) => {
    if (event.key === "Escape" && addingProject.value) closeProjectPopup();
};

watch(addingProject, (open) => {
    if (open) window.addEventListener("keydown", onProjectKey);
    else window.removeEventListener("keydown", onProjectKey);
});

onUnmounted(() => {
    window.removeEventListener("keydown", onProjectKey);
    if (addingProject.value) document.documentElement.classList.remove("is-overlay-open");
});
</script>

<template>
    <div class="line-writer">
        <div class="line-current">
            <p>{{ activeProject || "프로젝트를 고르세요" }}</p>
            <button type="button" class="line-more" @click="openProjectPopup">더보기</button>
        </div>
        <Teleport to="body">
            <div
                v-if="addingProject"
                class="app-dialog-overlay"
                @click.self="closeProjectPopup"
            >
                <div class="card app-dialog project-dialog" role="dialog" aria-modal="true" aria-labelledby="line-project-title">
                    <h2 id="line-project-title" class="app-dialog-message">프로젝트</h2>
                    <div class="line-pick-list" role="listbox" aria-label="프로젝트 목록">
                        <button
                            v-for="name in projectNames"
                            :key="name"
                            type="button"
                            class="line-pick"
                            :class="{ 'is-on': name === activeProject }"
                            :aria-selected="name === activeProject"
                            @click="chooseProject(name)"
                        >
                            {{ name }}
                        </button>
                    </div>
                    <form class="line-entry" @submit.prevent="addProject">
                        <input
                            id="line-new-project"
                            v-model="newProjectName"
                            class="input"
                            type="text"
                            placeholder="새 프로젝트 이름"
                            aria-label="새 프로젝트 이름"
                            enterkeyhint="done"
                        />
                        <button class="btn line-quiet" type="submit">추가</button>
                    </form>
                    <div class="app-dialog-actions">
                        <button class="btn" type="button" @click="closeProjectPopup">닫기</button>
                    </div>
                </div>
            </div>
        </Teleport>

        <section v-if="activeProject" class="line-group" :aria-label="activeProject">
            <div v-for="item in LINE_KINDS" :key="item" class="line-bucket">
                <h2>{{ item }}</h2>
                <div v-for="line in rowsFor(item)" :key="line.id" class="line-row">
                    <span>{{ line.text }}</span>
                    <button type="button" class="line-remove" @click="removeLine(line.id)">
                        삭제
                    </button>
                </div>
                <p v-if="!rowsFor(item).length" class="line-preview">없음</p>
            </div>
        </section>

        <form class="line-compose" @submit.prevent="addLine">
            <div class="line-kinds" role="group" aria-label="종류">
                <button
                    v-for="item in LINE_KINDS"
                    :key="item"
                    type="button"
                    :aria-pressed="item === kind"
                    :class="{ 'is-on': item === kind }"
                    @click="selectKind(item)"
                >
                    {{ item }}
                </button>
            </div>
            <template v-if="kind === '일정'">
                <label for="line-date">일정 날짜</label>
                <input id="line-date" v-model="lineValue" class="input" type="date" required />
                <label for="line-schedule">일정 내용</label>
                <div class="line-entry">
                    <input
                        id="line-schedule"
                        v-model="scheduleTitle"
                        class="input"
                        type="text"
                        placeholder="일정 내용"
                        enterkeyhint="done"
                        required
                    />
                    <button class="btn line-quiet" type="submit">넣기</button>
                </div>
            </template>
            <template v-else>
                <label for="line-text">{{ field.label }}</label>
                <div class="line-entry">
                    <input
                        id="line-text"
                        v-model="lineValue"
                        class="input"
                        type="text"
                        :placeholder="field.placeholder"
                        enterkeyhint="done"
                        required
                    />
                    <button class="btn line-quiet" type="submit">넣기</button>
                </div>
            </template>
        </form>
    </div>
</template>

<style scoped>
.line-writer {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-width: 0;
}

.line-current {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    min-height: 44px;
}

.line-current p {
    margin: 0;
    min-width: 0;
    font-size: 16px;
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    word-break: keep-all;
}

.line-more {
    flex: none;
    min-height: 44px;
    padding: 0 12px;
    border: 0;
    background: transparent;
    color: #007aff;
    font: inherit;
    font-size: 16px;
    cursor: pointer;
}

.line-pick-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 240px;
    margin-bottom: 12px;
    overflow: auto;
}

.line-pick {
    min-height: 44px;
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--text-strong);
    font: inherit;
    font-size: 16px;
    text-align: left;
    cursor: pointer;
}

.line-pick.is-on {
    border-color: var(--text-strong);
    background: var(--accent-soft);
}

.project-dialog .line-entry {
    margin-bottom: 12px;
}

.line-kinds {
    display: flex;
    gap: 6px;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
}

.line-kinds::-webkit-scrollbar {
    display: none;
}

.line-kinds button,
.line-quiet {
    min-height: 44px;
    border: 1px solid #7a7268;
    background: var(--surface);
    color: var(--text-strong);
    font: inherit;
    cursor: pointer;
}

.line-kinds button {
    flex: none;
    padding: 0 12px;
    border-radius: var(--radius-pill);
    font-size: 14px;
}

.line-kinds button.is-on {
    border-color: var(--text-strong);
    background: var(--accent-soft);
}

.line-kinds button:focus-visible,
.line-quiet:focus-visible,
.line-remove:focus-visible {
    outline: 2px solid var(--text-strong);
    outline-offset: 2px;
}

.line-group h2,
.line-bucket h2 {
    margin: 8px 0 0;
    font-size: 13px;
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.line-preview {
    margin: 0;
    min-height: 44px;
    display: flex;
    align-items: center;
    border-top: 1px solid var(--border);
    font-size: 15px;
    color: var(--text-muted);
}

.app-dialog h2 {
    margin: 0 0 12px;
}

.app-dialog .input {
    width: 100%;
    min-height: 44px;
    margin-bottom: 16px;
    font-size: 16px;
}

.line-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 6px;
    align-items: center;
    min-height: 44px;
    border-top: 1px solid var(--border);
    font-size: 15px;
    word-break: keep-all;
    color: var(--text-strong);
}

.line-remove {
    min-width: 44px;
    min-height: 44px;
    padding: 0 8px;
    border: 0;
    background: transparent;
    color: var(--danger-fg);
    font: inherit;
    font-size: 14px;
    cursor: pointer;
}

.line-compose label {
    display: block;
    margin: 8px 0 4px;
    font-size: 12px;
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.line-entry {
    display: flex;
    gap: 8px;
    align-items: center;
}

.line-entry .input,
.line-compose .input[type="date"] {
    min-width: 0;
    width: 100%;
    min-height: 44px;
    font-size: 16px;
}

.line-entry .input::placeholder {
    color: var(--text);
    opacity: 1;
}

.line-quiet {
    flex: none;
    height: 44px;
    padding: 0 14px;
    border-radius: var(--radius-pill);
    font-size: 14px;
}

.line-quiet:hover,
.line-quiet:active {
    background: var(--surface-soft);
}
</style>
