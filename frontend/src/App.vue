<script setup>
import {
    FolderKanban,
    PenSquare,
    CalendarDays,
    FileBarChart,
    GitGraph,
    ArrowLeftRight,
    Settings2,
    UsersRound,
    ChevronDown,
} from "lucide-vue-next";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "./composables/useApi";
import { selectedUserId } from "./composables/useSelectedUser";
import { selectedTeamId } from "./composables/useSelectedTeam";
import { useToast } from "./composables/useToast";
import { useDialog } from "./composables/useDialog";

const router = useRouter();
const route = useRoute();
const { getUsers, getTeams, getReports } = useApi();
const { toasts } = useToast();
const {
    open: dialogOpen,
    locked: dialogLocked,
    mode: dialogMode,
    title: dialogTitle,
    message: dialogMessage,
    help: dialogHelp,
    confirmLabel: dialogConfirmLabel,
    cancelLabel: dialogCancelLabel,
    confirm: askConfirm,
    accept: acceptDialog,
    reject: rejectDialog,
} = useDialog();

const navGroups = [
    {
        label: "조회",
        items: [
            { to: "/", label: "일일보고", icon: FolderKanban },
            { to: "/project-timeline", label: "프로젝트 흐름", icon: GitGraph },
            { to: "/activities", label: "사용자 활동", icon: CalendarDays },
        ],
    },
    {
        label: "작성",
        items: [
            { to: "/report", label: "보고서 작성", icon: PenSquare },
            { to: "/weekly", label: "주간 보고서", icon: FileBarChart },
        ],
    },
    {
        label: "관리",
        items: [
            { to: "/project-name", label: "프로젝트명 관리", icon: Settings2 },
            { to: "/team-select", label: "팀 선택", icon: UsersRound },
        ],
    },
];


const pageMeta = computed(() => ({
    title: route.meta.title || "일일보고",
    parent: route.meta.parent || null,
    action: route.meta.action || null,
}));

const isNavActive = (to) => route.meta.navKey === to;

const currentUser = ref("");
const currentTeam = ref("");
const tomorrowPlans = ref([]);

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

const tomorrowLabel = computed(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return `${d.getMonth() + 1}.${d.getDate()} ${WEEKDAYS[d.getDay()]}`;
});

const groupedTomorrowPlans = computed(() => {
    const groups = [];
    const indexByProject = new Map();
    for (const item of tomorrowPlans.value) {
        const project = item.project || "미분류 프로젝트";
        if (!indexByProject.has(project)) {
            indexByProject.set(project, groups.length);
            groups.push({ project, items: [] });
        }
        groups[indexByProject.get(project)].items.push(item.text);
    }
    return groups;
});

const PROJECT_TONES = [
    "#8b9a6e",
    "#6e8b9a",
    "#9a846e",
    "#7a6e9a",
    "#9a6e76",
    "#6e9a86",
    "#8b7a6e",
    "#6e7a9a",
];

const projectTone = (name) => {
    let hash = 0;
    for (let i = 0; i < name.length; i += 1) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return PROJECT_TONES[Math.abs(hash) % PROJECT_TONES.length];
};

const expandedProjects = ref(new Set());

watch(groupedTomorrowPlans, (groups) => {
    if (!groups.length) {
        expandedProjects.value = new Set();
        return;
    }
    const total = groups.reduce((sum, group) => sum + group.items.length, 0);
    if (total <= 8 && groups.length <= 3) {
        expandedProjects.value = new Set(groups.map((group) => group.project));
        return;
    }
    expandedProjects.value = new Set();
});

const isGroupOpen = (project) => expandedProjects.value.has(project);

const toggleGroup = (project) => {
    const next = new Set(expandedProjects.value);
    if (next.has(project)) next.delete(project);
    else next.add(project);
    expandedProjects.value = next;
};

const allExpanded = computed(
    () =>
        groupedTomorrowPlans.value.length > 0 &&
        groupedTomorrowPlans.value.every((group) =>
            expandedProjects.value.has(group.project),
        ),
);

const toggleAllGroups = () => {
    if (allExpanded.value) {
        expandedProjects.value = new Set();
        return;
    }
    expandedProjects.value = new Set(
        groupedTomorrowPlans.value.map((group) => group.project),
    );
};

const projectsOf = (parsedJson) => {
    if (!parsedJson) return [];
    let parsed = parsedJson;
    if (typeof parsed === "string") {
        try {
            parsed = JSON.parse(parsed);
        } catch {
            return [];
        }
    }
    return parsed.projects || [];
};

const loadTomorrowPlans = async (userId) => {
    tomorrowPlans.value = [];
    if (!userId) return;
    try {
        const reports = await getReports();
        const mine = (reports || []).filter(
            (row) => String(row.member_id) === String(userId),
        );
        if (!mine.length) return;
        const today = new Date();
        const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
        const latest =
            mine.find((row) => row.report_date === todayKey) || mine[0];
        const items = [];
        for (const project of projectsOf(latest.parsed_json)) {
            for (const plan of project.nextPlans || []) {
                const text = String(plan || "").trim();
                if (!text) continue;
                items.push({
                    project: project.projectName || "미분류 프로젝트",
                    text,
                });
            }
        }
        tomorrowPlans.value = items;
    } catch {
        tomorrowPlans.value = [];
    }
};

const loadCurrent = async (storedId, storedTeamId) => {
    if (!storedId) {
        currentUser.value = "";
        currentTeam.value = "";
        return;
    }
    try {
        const users = await getUsers();
        const found = users.find((u) => String(u.id) === String(storedId));
        currentUser.value = found ? found.name : `사용자 ${storedId}`;
        const teams = await getTeams();
        const foundTeam = teams.find((t) => String(t.id) === String(storedTeamId));
        currentTeam.value = foundTeam ? foundTeam.team_name : `팀 ${storedTeamId}`;
    } catch {
        currentUser.value = `사용자 ${storedId}`;
        currentTeam.value = `팀 ${storedTeamId}`;
    }
};

watch(
    [selectedUserId, selectedTeamId],
    ([id, teamId]) => {
        loadCurrent(id, teamId);
        loadTomorrowPlans(id);
    },
    { immediate: true },
);

watch(
    () => route.path,
    () => loadTomorrowPlans(selectedUserId.value),
);

const userInitial = () => {
    const name = currentUser.value || "";
    return name.slice(0, 1) || "?";
};

const logout = async () => {
    if (!(await askConfirm("사용자를 변경하시겠습니까?"))) return;
    selectedUserId.value = null;
    sessionStorage.removeItem("selectedUser");
    sessionStorage.removeItem("reportData");
    sessionStorage.removeItem("reportRaw");
    sessionStorage.removeItem("reportDate");
    router.push("/users");
};

const onDialogKeydown = (event) => {
    if (!dialogOpen.value || dialogLocked.value) return;
    if (event.key === "Escape") {
        event.preventDefault();
        if (dialogMode.value === "confirm") rejectDialog();
        else acceptDialog();
        return;
    }
    if (event.key === "Enter") {
        event.preventDefault();
        acceptDialog();
    }
};

onMounted(() => {
    window.addEventListener("keydown", onDialogKeydown);
    if (selectedUserId.value == null) {
        router.push("/users");
    }
});

onUnmounted(() => {
    window.removeEventListener("keydown", onDialogKeydown);
});
</script>

<template>
    <aside class="sidebar">


        <nav class="nav-links">
            <div v-for="group in navGroups" :key="group.label" class="nav-group">
                <p class="nav-group-label">{{ group.label }}</p>
                <router-link v-for="item in group.items" :key="item.to" :to="item.to" class="nav-link"
                    :class="{ 'router-link-exact-active': isNavActive(item.to) }">
                    <component :is="item.icon" :size="16" />
                    {{ item.label }}
                </router-link>
            </div>

        </nav>

        <section class="tomorrow-card" aria-label="내일 할 일">
            <div class="tomorrow-card-head">
                <div class="tomorrow-card-heading">
                    <p class="tomorrow-card-title">내일 할 일</p>
                    <span v-if="tomorrowPlans.length" class="tomorrow-card-count">{{ tomorrowPlans.length }}</span>
                </div>
                <span class="tomorrow-card-date">{{ tomorrowLabel }}</span>
            </div>
            <div v-if="groupedTomorrowPlans.length" class="tomorrow-card-toolbar">
                <p class="tomorrow-card-summary">
                    {{ groupedTomorrowPlans.length }}개 프로젝트
                </p>
                <button type="button" class="tomorrow-card-toggle-all" @click="toggleAllGroups">
                    {{ allExpanded ? "모두 접기" : "모두 펼치기" }}
                </button>
            </div>
            <div v-if="groupedTomorrowPlans.length" class="tomorrow-card-body">
                <section
                    v-for="(group, groupIndex) in groupedTomorrowPlans"
                    :key="group.project"
                    class="tomorrow-group"
                    :class="{ 'is-open': isGroupOpen(group.project) }"
                    :style="{ '--group-tone': projectTone(group.project) }"
                >
                    <button
                        type="button"
                        class="tomorrow-group-head"
                        :aria-expanded="isGroupOpen(group.project)"
                        :aria-controls="`tomorrow-group-${groupIndex}`"
                        @click="toggleGroup(group.project)"
                    >
                        <ChevronDown :size="14" class="tomorrow-group-chevron" />
                        <span class="tomorrow-group-name">{{ group.project }}</span>
                        <span class="tomorrow-group-count">{{ group.items.length }}</span>
                    </button>
                    <div
                        class="tomorrow-group-panel"
                        :id="`tomorrow-group-${groupIndex}`"
                        :aria-hidden="!isGroupOpen(group.project)"
                    >
                        <ul class="tomorrow-card-list">
                            <li v-for="(text, index) in group.items" :key="index">
                                {{ text }}
                            </li>
                        </ul>
                    </div>
                </section>
            </div>
            <p v-else class="tomorrow-card-empty">내일 예정 업무가 없어요</p>
        </section>

        <div class="sidebar-footer">
            <div class="sidebar-user">
                <span class="sidebar-avatar">{{ userInitial() }}</span>
                <span class="sidebar-user-meta">
                    <span class="sidebar-user-name">{{ currentUser || "사용자 미선택" }}</span>
                    <span class="sidebar-user-team">{{ currentTeam || "팀 미선택" }}</span>
                </span>
            </div>
            <button type="button" class="sidebar-logout" @click="logout">
                <ArrowLeftRight :size="14" />
                사용자 변경
            </button>
        </div>
    </aside>

    <main class="main-content">
        <header class="topbar">
            <nav class="topbar-crumbs" aria-label="현재 위치">
                <router-link v-if="pageMeta.parent" class="topbar-crumb" :to="pageMeta.parent.to">
                    {{ pageMeta.parent.label }}
                </router-link>
                <span v-if="pageMeta.parent" class="topbar-crumb-sep" aria-hidden="true">›</span>
                <span class="topbar-title" aria-current="page">{{ pageMeta.title }}</span>
            </nav>
            <router-link v-if="pageMeta.action" class="btn btn-primary btn-small" :to="pageMeta.action.to">
                {{ pageMeta.action.label }}
            </router-link>
        </header>
        <div class="main-body">
            <RouterView />
        </div>
    </main>
    <div class="toast-stack" aria-live="polite">
        <div v-for="item in toasts" :key="item.id" class="toast" :class="'toast-' + item.type">
            {{ item.message }}
        </div>
    </div>
    <div
        v-if="dialogOpen"
        class="app-dialog-overlay"
        :class="{ 'is-locked': dialogLocked }"
        role="dialog"
        aria-modal="true"
        aria-labelledby="app-dialog-message"
    >
        <div class="card app-dialog" @click.stop>
            <p v-if="dialogTitle" class="app-dialog-kicker">{{ dialogTitle }}</p>
            <p id="app-dialog-message" class="app-dialog-message">{{ dialogMessage }}</p>
            <p v-if="dialogHelp" class="app-dialog-help">{{ dialogHelp }}</p>
            <div class="app-dialog-actions">
                <button
                    v-if="dialogMode === 'confirm'"
                    type="button"
                    class="btn"
                    :disabled="dialogLocked"
                    @click="rejectDialog"
                >
                    {{ dialogCancelLabel }}
                </button>
                <button
                    type="button"
                    class="btn btn-primary"
                    :disabled="dialogLocked"
                    @click="acceptDialog"
                >
                    {{ dialogConfirmLabel }}
                </button>
            </div>
        </div>
    </div>
</template>
