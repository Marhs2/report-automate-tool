<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "../composables/useApi";

const route = useRoute();
const router = useRouter();
const { getDashboard } = useApi();

const board = ref({
    projects: [],
    lastActivity: null,
    projectNames: [],
    selectedProject: "",
    history: [],
});
const isLoading = ref(false);
const loadError = ref("");

const selectedProject = computed({
    get: () => String(route.query.project || ""),
    set: (value) => {
        const project = String(value || "").trim();
        router.replace({ path: "/", query: project ? { project } : {} });
    },
});

const projectOptions = computed(() => {
    const names = [...(board.value.projectNames || [])];
    const selected = String(board.value.selectedProject || "");
    if (selected && !names.includes(selected)) names.push(selected);
    return names;
});

const dotDate = (value) => {
    const [year, month, day] = String(value || "").split("T")[0].split("-");
    if (!year || !month || !day) return "";
    return `${year}.${Number(month)}.${Number(day)}`;
};

const load = async () => {
    isLoading.value = true;
    loadError.value = "";
    try {
        board.value = await getDashboard(String(route.query.project || ""));
    } catch (error) {
        console.error("내 현황 조회 실패:", error);
        loadError.value = "내 현황을 불러오지 못했습니다.";
    } finally {
        isLoading.value = false;
    }
};

const chooseProject = (name) => {
    selectedProject.value = name;
};

watch(() => route.query.project, load, { immediate: true });

onMounted(() => {
    document.title = "내 현황";
});
</script>

<template>
    <div class="page">
        <p v-if="isLoading" class="list-status" role="status">현황을 불러오는 중</p>
        <p v-else-if="loadError" class="list-status is-error" role="alert">{{ loadError }}</p>

        <template v-else>
            <section class="dash-section" aria-labelledby="progress-title">
                <h2 id="progress-title">진행 중인 프로젝트</h2>
                <div v-if="board.projects.length" class="project-grid">
                    <button
                        v-for="project in board.projects"
                        :key="project.name"
                        type="button"
                        class="card project-card"
                        :class="{ 'is-selected': project.name === selectedProject }"
                        @click="chooseProject(project.name)"
                    >
                        <span class="project-name">{{ project.name }}</span>
                        <span class="project-status">{{ project.statusLine }}</span>
                        <span v-if="project.lastActive" class="project-date">
                            {{ dotDate(project.lastActive) }}
                        </span>
                    </button>
                </div>
                <div v-else class="empty-state">
                    <p>아직 연결된 진행 프로젝트가 없습니다.</p>
                    <router-link class="btn btn-primary" to="/compose">작성</router-link>
                </div>
            </section>

            <section class="dash-section" aria-labelledby="last-title">
                <h2 id="last-title">마지막으로 한 업무</h2>
                <router-link
                    v-if="board.lastActivity"
                    class="card last-card"
                    :to="board.lastActivity.href"
                >
                    <span class="kind">{{ board.lastActivity.kindLabel }}</span>
                    <span class="last-title">{{ board.lastActivity.title }}</span>
                    <span v-if="board.lastActivity.date" class="project-date">
                        {{ dotDate(board.lastActivity.date) }}
                    </span>
                </router-link>
                <div v-else class="empty-state">
                    <p>아직 저장한 업무가 없습니다.</p>
                    <router-link class="btn btn-primary" to="/compose">작성</router-link>
                </div>
            </section>

            <section class="dash-section" aria-labelledby="history-title">
                <div class="section-head">
                    <h2 id="history-title">프로젝트별 업무</h2>
                    <select v-model="selectedProject" class="input" aria-label="프로젝트">
                        <option value="">프로젝트를 선택하세요</option>
                        <option v-for="name in projectOptions" :key="name" :value="name">
                            {{ name }}
                        </option>
                    </select>
                </div>
                <p v-if="!selectedProject" class="list-status">
                    프로젝트를 고르면 지금까지 한 업무가 날짜순으로 나옵니다.
                </p>
                <p v-else-if="board.history.length === 0" class="list-status">
                    이 프로젝트에 기록된 업무가 없습니다.
                </p>
                <div v-else class="history">
                    <router-link
                        v-for="item in board.history"
                        :key="item.key"
                        class="card history-card"
                        :to="item.href"
                    >
                        <span class="history-meta">
                            <span class="kind">{{ item.kindLabel }}</span>
                            <span v-if="item.date">{{ dotDate(item.date) }}</span>
                        </span>
                        <span class="history-title">{{ item.title }}</span>
                        <span v-for="line in item.lines" :key="line" class="history-line">
                            {{ line }}
                        </span>
                    </router-link>
                </div>
            </section>
        </template>
    </div>
</template>

<style scoped>
.dash-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
}

.dash-section h2 {
    margin: 0;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
}

.section-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2) var(--space-3);
}

.section-head .input {
    width: min(280px, 100%);
}

.project-grid,
.history {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: var(--space-3);
}

.history {
    grid-template-columns: 1fr;
}

.project-card,
.last-card,
.history-card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-2);
    width: 100%;
    color: inherit;
    text-align: left;
    text-decoration: none;
    cursor: pointer;
}

.project-card.is-selected {
    border-color: var(--accent);
}

.project-name,
.last-title,
.history-title {
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.project-status,
.history-line {
    font-size: var(--fs-14);
    line-height: var(--lh-base);
    color: var(--text);
}

.project-date,
.history-meta {
    font-size: var(--fs-13);
    color: var(--text-muted);
}

.history-meta,
.kind {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
}

.kind {
    color: var(--accent-hover);
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
}

.list-status {
    margin: 0;
    font-size: var(--fs-14);
    color: var(--text);
}

.list-status.is-error {
    color: var(--danger-fg);
}
</style>
