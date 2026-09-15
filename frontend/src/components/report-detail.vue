<template>
    <div class="page report-doc">
        <div class="page-header">
            <div>
                <button type="button" class="btn back-btn" @click="goBack">
                    <ArrowLeft :size="16" />
                    목록으로
                </button>
                <h1 class="detail-title">{{ userName || "작성자 미상" }}</h1>
                <p v-if="reportDate" class="page-subtitle">
                    {{ formatDate(reportDate) }}
                    {{ weekday(reportDate) }}
                </p>
            </div>
        </div>

        <div v-if="isLoading" class="empty-state">불러오는 중...</div>

        <div v-else-if="reportData" class="content-container">
            <div class="json-container">
                <section
                    v-for="(project, projectIndex) in reportData.projects"
                    :key="project._uid || projectIndex"
                    class="card projects-container"
                >
                    <h2 class="project-title">
                        {{ project.projectName || "이름 없는 프로젝트" }}
                    </h2>

                    <div v-if="taskGroups(project).length" class="task-groups">
                        <section
                            v-for="group in taskGroups(project)"
                            :key="group.kind"
                            class="task-group"
                        >
                            <h3 class="task-group-label" :class="group.kind">
                                {{ group.label }}
                            </h3>
                            <ul class="task-cards">
                                <li
                                    v-for="(text, itemIndex) in group.items"
                                    :key="itemIndex"
                                    class="task-card"
                                    :class="group.kind"
                                >
                                    {{ text }}
                                </li>
                            </ul>
                        </section>
                    </div>
                    <p v-else class="empty-msg">
                        이 프로젝트에 적힌 업무가 없습니다
                    </p>
                </section>
            </div>

            <aside class="card raw-container">
                <h2>원본 보고서</h2>
                <pre class="raw-content">{{ rawData || "원문이 없습니다." }}</pre>
            </aside>
        </div>

        <div v-else class="empty-state">
            <p>보고서 데이터가 없습니다.</p>
            <button type="button" class="btn" @click="goBack">목록으로</button>
        </div>
    </div>
</template>

<script setup>
import { ref, watch } from "vue";
import { ArrowLeft } from "lucide-vue-next";
import useAPI from "../composables/useApi";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();

const reportData = ref(null);
const rawData = ref(null);
const userName = ref("");
const reportDate = ref("");
const isLoading = ref(false);

const { getUsers, GetReportById } = useAPI();

const toParsed = (parsedJson) => {
    if (!parsedJson) return null;
    if (typeof parsedJson === "string") {
        try {
            return JSON.parse(parsedJson);
        } catch {
            return null;
        }
    }
    return parsedJson;
};

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

const itemText = (value) =>
    value && typeof value === "object"
        ? String(value.content ?? "").trim()
        : String(value ?? "").trim();

const textsOf = (list) =>
    (Array.isArray(list) ? list : []).map(itemText).filter(Boolean);

const taskGroups = (project) =>
    [
        { kind: "done", label: "완료", items: textsOf(project.completedTasks) },
        { kind: "progress", label: "진행", items: textsOf(project.inProgressTasks) },
        { kind: "issue", label: "이슈", items: textsOf(project.issues) },
        { kind: "request", label: "요청", items: textsOf(project.requests) },
        { kind: "plan", label: "다음", items: textsOf(project.nextPlans) },
    ].filter((group) => group.items.length);

const formatDate = (value) => {
    if (!value) return "-";
    const [y, m, d] = String(value).split("-");
    if (!y || !m || !d) return value;
    return `${y}.${m}.${d}`;
};

const weekday = (value) => {
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return "";
    return WEEKDAYS[date.getDay()];
};

const goBack = () => {
    router.push("/");
};

const loadReport = async (id) => {
    if (!id) return;
    isLoading.value = true;
    reportData.value = null;
    try {
        const data = await GetReportById(id);
        reportData.value = toParsed(data.parsed_json);
        rawData.value = data.raw_text;
        reportDate.value = data.report_date || "";

        const users = await getUsers();
        const found = users.find(
            (user) => String(user.id) === String(data.member_id),
        );
        userName.value = found ? found.name : `사용자 ${data.member_id}`;
        document.title = `${userName.value} · 일일보고`;
    } catch (error) {
        console.error("보고서 불러오기 실패:", error);
        reportData.value = null;
    } finally {
        isLoading.value = false;
    }
};

watch(
    () => route.params.id,
    (id) => {
        loadReport(id);
    },
    { immediate: true },
);
</script>

<style scoped>
.project-title {
    margin-bottom: 16px;
}

.task-groups {
    display: flex;
    flex-direction: column;
    gap: 18px;
}

.task-group-label {
    margin: 0 0 8px;
    font-size: 12px;
    font-weight: 650;
    color: var(--text);
}

.task-group-label.done {
    color: var(--accent);
}

.task-group-label.issue {
    color: var(--danger);
}

.task-cards {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.task-card {
    padding: 12px 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
    font-size: 14px;
    color: var(--text-h);
    line-height: 1.5;
    word-break: keep-all;
}

.task-card.done {
    background: var(--accent-bg);
    border-color: var(--accent-border);
}

.task-card.issue {
    background: var(--danger-bg);
    border-color: color-mix(in srgb, var(--danger) 28%, var(--border));
}
</style>
