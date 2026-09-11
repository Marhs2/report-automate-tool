<template>
    <div class="page">
        <div class="page-header">
            <div>
                <button type="button" class="btn back-btn" @click="goBack">
                    <ArrowLeft :size="16" />
                    목록으로
                </button>
                <h1>일일보고</h1>
                <p class="page-subtitle">
                    {{ userName || "작성자 미상" }}
                    <span v-if="reportDate"> · {{ formatDate(reportDate) }}</span>
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

                    <div
                        v-for="section in visibleSections(project)"
                        :key="section.key"
                        class="field-group"
                    >
                        <h3>{{ section.label }}</h3>
                        <ul v-if="section.items.length" class="item-list">
                            <li
                                v-for="(entry, entryIndex) in section.items"
                                :key="entryIndex"
                            >
                                <span>{{ itemText(entry) }}</span>
                                <span
                                    v-if="section.key === 'issues' && statusOf(entry)"
                                    class="status-badge"
                                    :class="
                                        statusOf(entry) === '해결'
                                            ? 'is-resolved'
                                            : 'is-open'
                                    "
                                >
                                    {{ statusOf(entry) }}
                                </span>
                            </li>
                        </ul>
                        <p v-else class="empty-msg">{{ section.empty }}</p>
                    </div>
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

const itemText = (value) =>
    value && typeof value === "object"
        ? (value.content ?? "")
        : String(value ?? "");

const statusOf = (value) =>
    value && typeof value === "object" ? value.status || "" : "";

const hasItems = (list) => Array.isArray(list) && list.length > 0;

const visibleSections = (project) => [
    {
        key: "completed",
        label: "완료된 업무",
        items: project.completedTasks || [],
        empty: "완료된 업무가 없습니다",
    },
    {
        key: "progress",
        label: "진행 중인 업무",
        items: project.inProgressTasks || [],
        empty: "진행 중인 업무가 없습니다",
    },
    {
        key: "issues",
        label: "이슈",
        items: project.issues || [],
        empty: "이슈가 없습니다",
    },
    {
        key: "requests",
        label: "요청사항",
        items: project.requests || [],
        empty: "요청사항이 없습니다",
    },
    {
        key: "plans",
        label: "다음 계획",
        items: project.nextPlans || [],
        empty: "다음 계획이 없습니다",
    },
].filter((section) => hasItems(section.items));

const formatDate = (value) => {
    if (!value) return "-";
    const [y, m, d] = String(value).split("-");
    if (!y || !m || !d) return value;
    return `${y}.${m}.${d}`;
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
.back-btn {
    margin-bottom: 14px;
}

.content-container {
    display: flex;
    gap: 24px;
    align-items: flex-start;
}

.json-container {
    flex: 2;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.raw-container {
    flex: 1;
    min-width: 0;
    position: sticky;
    top: 32px;
}

.raw-container h2 {
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}

.raw-container pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 13px;
    line-height: 1.5;
    max-height: 80vh;
    overflow-y: auto;
    color: var(--text);
}

.projects-container {
    display: flex;
    flex-direction: column;
}

.project-title {
    margin: 0 0 12px;
    font-size: 16px;
}

.field-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
    border: 1px solid var(--border);
    background: var(--bg);
    padding: 14px 16px;
    border-radius: var(--radius-sm);
}

.field-group:last-of-type {
    margin-bottom: 0;
}

.field-group h3 {
    margin: 0;
    font-size: 13px;
    color: var(--text);
}

.item-list {
    margin: 0;
    padding-left: 18px;
    font-size: 14px;
    line-height: 1.65;
    color: var(--text-h);
}

.item-list li + li {
    margin-top: 4px;
}

.empty-msg {
    margin: 0;
    font-size: 13px;
    color: var(--text);
    font-style: italic;
    opacity: 0.7;
}

.status-badge {
    display: inline-flex;
    margin-left: 8px;
    padding: 1px 7px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 650;
    vertical-align: middle;
}

.status-badge.is-open {
    background: var(--danger-bg);
    color: var(--danger);
}

.status-badge.is-resolved {
    background: color-mix(in srgb, var(--success) 16%, transparent);
    color: var(--success);
}

@media (max-width: 860px) {
    .content-container {
        flex-direction: column;
    }

    .raw-container {
        position: static;
    }
}
</style>
