<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import { ChevronDown, X } from "lucide-vue-next";
import KindTag from "./KindTag.vue";
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

/** 분류 색과 아이콘은 모든 화면이 같은 KindTag를 쓴다. */
const KIND_OF = { 완료: "done", 진행: "progress", 이슈: "issue", 요청: "request", "다음 계획": "next" };
/** 종류 버튼 다섯 개를 390px 한 줄에 넣는다. */
const SHORT_KIND = { "다음 계획": "다음" };

/** 프로젝트를 여럿 써도 넣은 줄을 한눈에 본다. 고른 프로젝트는 빈 칸까지 보고 틀로 보여 준다. */
const groups = computed(() => {
    const names = [];
    for (const line of lines.value) {
        if (!names.includes(line.project)) names.push(line.project);
    }
    if (activeProject.value && !names.includes(activeProject.value)) names.push(activeProject.value);
    return names.map((name) => ({
        name,
        kinds: LINE_KINDS.map((item) => ({
            item,
            rows: lines.value.filter((line) => line.project === name && line.kind === item),
        })),
    }));
});

/** 빈 칸을 누르면 그 프로젝트 · 종류로 바로 쓴다. */
const pickSlot = (name, item) => {
    activeProject.value = name;
    selectKind(item);
};

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

        <section v-if="groups.length" class="line-groups" aria-label="쓴 줄">
            <div v-for="group in groups" :key="group.name" class="line-group">
                <h2 class="line-group-name">{{ group.name }}</h2>
                <template v-for="bucket in group.kinds" :key="bucket.item">
                    <div v-for="line in bucket.rows" :key="line.id" class="line-row">
                        <KindTag :kind="KIND_OF[line.kind]" :label="SHORT_KIND[line.kind] || line.kind" />
                        <span class="line-text">{{ line.text }}</span>
                        <button
                            type="button"
                            class="line-remove"
                            :aria-label="`${line.text} 빼기`"
                            @click="removeLine(line.id)"
                        >
                            <X :size="16" />
                        </button>
                    </div>
                    <button
                        v-if="!bucket.rows.length"
                        type="button"
                        class="line-row line-row-empty"
                        :aria-label="`${group.name} ${bucket.item} 쓰기`"
                        @click="pickSlot(group.name, bucket.item)"
                    >
                        <KindTag :kind="KIND_OF[bucket.item]" :label="SHORT_KIND[bucket.item] || bucket.item" />
                        <span class="line-text">없음</span>
                    </button>
                </template>
            </div>
        </section>

        <form class="line-compose" @submit.prevent="addLine">
            <button
                type="button"
                class="line-project"
                :aria-label="projectLabel"
                @click="openProjectPopup"
            >
                <span class="line-project-name">{{ activeProject || "프로젝트를 고르세요" }}</span>
                <ChevronDown :size="16" aria-hidden="true" />
            </button>
            <div class="line-kinds" role="group" aria-label="종류">
                <button
                    v-for="item in LINE_KINDS"
                    :key="item"
                    type="button"
                    :aria-label="item"
                    :aria-pressed="item === kind"
                    :class="{ 'is-on': item === kind }"
                    @click="selectKind(item)"
                >
                    <KindTag :kind="KIND_OF[item]" :label="SHORT_KIND[item] || item" bare />
                </button>
            </div>
            <label class="sr-only" for="line-text">{{ field.label }}</label>
            <div class="line-entry">
                <span class="line-field">
                    <KindTag class="line-field-icon" :kind="KIND_OF[kind]" :label="kind" icon-only />
                    <input
                        id="line-text"
                        v-model="lineValue"
                        class="input"
                        type="text"
                        :placeholder="field.placeholder"
                        enterkeyhint="done"
                        required
                    />
                </span>
                <button class="btn line-quiet" type="submit">추가</button>
            </div>
            <slot name="dock" />
        </form>
    </div>
</template>

<style scoped src="../../styles/components/ui/line-writer.css"></style>
