<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import {
    KIND_FIELDS,
    LINE_KINDS,
    parseLineReport,
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
const projectLabel = computed(() =>
    activeProject.value ? `${activeProject.value}, 프로젝트 변경` : "프로젝트 고르기",
);

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
    kind.value = next;
    await nextTick();
    document.getElementById("line-text")?.focus();
};

const addLine = () => {
    const text = lineValue.value.trim();
    if (!activeProject.value || !text) return;
    lines.value = [
        ...lines.value,
        { id: nextId++, project: activeProject.value, kind: kind.value, text },
    ];
    lineValue.value = "";
    publish();
};

const commitPending = () => {
    if (!lineValue.value.trim()) return "";
    if (!activeProject.value) return "프로젝트를 고른 뒤 제출하세요.";
    addLine();
    return "";
};

defineExpose({ commitPending });

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
        <div class="line-context">
            <button
                type="button"
                class="line-project"
                :aria-label="projectLabel"
                @click="openProjectPopup"
            >
                <span class="line-project-name">{{ activeProject || "프로젝트를 고르세요" }}</span>
                <span class="line-project-cue" aria-hidden="true">변경</span>
            </button>
            <slot name="date" />
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
            <label class="sr-only" for="line-text">{{ field.label }}</label>
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
            <slot name="dock" />
        </form>
    </div>
</template>

<style scoped>
.line-writer {
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: var(--space-3);
    min-width: 0;
    min-height: 100%;
}

.line-context {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-height: var(--control-h-lg);
}

.line-context :slotted(input) {
    flex: none;
    width: auto;
}

.line-project {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    flex: 1;
    min-width: 0;
    min-height: var(--control-h-lg);
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--text-strong);
    font: inherit;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    text-align: left;
    cursor: pointer;
}

.line-project-name {
    min-width: 0;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
    white-space: normal;
    line-height: 1.25;
    word-break: keep-all;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    max-width: 100%;
}

.line-project-cue {
    flex: none;
    color: var(--accent);
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
}

.line-project:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
}

.line-pick-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-height: 240px;
    margin-bottom: var(--space-3);
    overflow: auto;
}

.line-pick {
    min-height: var(--control-h-lg);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--text-strong);
    font: inherit;
    font-size: var(--fs-16);
    text-align: left;
    cursor: pointer;
}

.line-pick.is-on {
    border-color: var(--text-strong);
    background: var(--accent-soft);
}

.project-dialog .line-entry {
    margin-bottom: var(--space-3);
}

.line-kinds {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    min-width: 0;
}

.line-kinds button,
.line-quiet {
    min-height: var(--control-h-lg);
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: var(--text-strong);
    font: inherit;
    cursor: pointer;
}

.line-kinds button {
    flex: 1 1 calc(33.33% - var(--space-2));
    min-width: 0;
    padding: 0 var(--space-2);
    border-radius: var(--radius-pill);
    font-size: var(--fs-14);
    white-space: nowrap;
}

.line-kinds button.is-on {
    border-color: var(--text-strong);
    background: var(--accent-soft);
}

.line-kinds button:focus-visible,
.line-quiet:focus-visible,
.line-remove:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
}

.line-group {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-height: 0;
}

.line-bucket {
    display: flex;
    flex: 1;
    flex-direction: column;
    justify-content: center;
}

.line-preview {
    margin: 0;
    min-height: var(--control-h-lg);
    display: flex;
    align-items: center;
    border-top: 1px solid var(--border);
    font-size: var(--fs-14);
    color: var(--text);
}

.line-group h2,
.line-bucket h2 {
    margin: var(--space-2) 0 0;
    font-size: var(--fs-13);
    font-weight: var(--fw-semibold);
    color: var(--text);
}

.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}

.app-dialog h2 {
    margin: 0 0 var(--space-3);
}

.app-dialog .input {
    width: 100%;
    min-height: var(--control-h-lg);
    margin-bottom: var(--space-4);
    font-size: var(--fs-16);
}

.line-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--space-2);
    align-items: center;
    min-height: var(--control-h-lg);
    border-top: 1px solid var(--border);
    font-size: var(--fs-14);
    word-break: keep-all;
    color: var(--text-strong);
}

.line-remove {
    min-width: var(--control-h-lg);
    min-height: var(--control-h-lg);
    padding: 0 var(--space-2);
    border: 0;
    background: transparent;
    color: var(--danger-fg);
    font: inherit;
    font-size: var(--fs-14);
    cursor: pointer;
}

.line-compose {
    display: flex;
    flex: none;
    flex-direction: column;
    gap: var(--space-2);
    margin-top: auto;
    padding-top: var(--space-3);
    border-top: 1px solid var(--border);
}

.line-compose .input {
    scroll-margin-bottom: calc(var(--bottom-nav-offset) + var(--space-4));
}

.line-compose label {
    display: block;
    margin: 0;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.line-compose :slotted(.form-error) {
    margin: 0;
}

.line-compose :slotted(.line-send) {
    width: 100%;
    min-height: var(--control-h-lg);
    height: var(--control-h-lg);
}

.line-entry {
    display: flex;
    gap: var(--space-2);
    align-items: center;
}

.line-entry .input {
    min-width: 0;
    width: 100%;
    min-height: var(--control-h-lg);
    font-size: var(--fs-16);
}

.line-entry .input::placeholder {
    color: var(--text);
    opacity: 1;
}

.line-quiet {
    flex: none;
    height: var(--control-h-lg);
    padding: 0 var(--space-4);
    border-radius: var(--radius-pill);
    font-size: var(--fs-14);
}

.line-quiet:hover,
.line-quiet:active {
    background: var(--surface-soft);
}
</style>
