<script setup>
import {
    FolderKanban,
    CalendarDays,
    FileBarChart,
    GitGraph,
    ArrowLeftRight,
    Settings2,
    PanelLeftClose,
    PanelLeftOpen,
    Menu,
} from "lucide-vue-next";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "./composables/useApi";
import { selectedUserId } from "./composables/useSelectedUser";
import { selectedTeamId } from "./composables/useSelectedTeam";
import { useDialog } from "./composables/useDialog";
import { useSidebar } from "./composables/useSidebar";
import { navGroupsFromPrimary } from "./lib/nav";

const router = useRouter();
const route = useRoute();
const { getUsers, getTeams } = useApi();
const { collapsedEffective, isNarrow, toggleCollapsed, drawerOpen, openDrawer, closeDrawer } = useSidebar();
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
    alert: showAlert,
    accept: acceptDialog,
    reject: rejectDialog,
} = useDialog();

const NAV_ICONS = {
    "/": FolderKanban,
    "/weekly": FileBarChart,
    "/activities": CalendarDays,
    "/project-timeline": GitGraph,
    "/settings": Settings2,
};

const navGroups = navGroupsFromPrimary().map((group) => ({
    ...group,
    items: group.items.map((item) => ({
        ...item,
        icon: NAV_ICONS[item.to] || Settings2,
    })),
}));


const pageMeta = computed(() => ({
    title: route.meta.title || "일일보고",
    parent: route.meta.parent || null,
    action: route.meta.action || null,
}));

const isNavActive = (to) => route.meta.navKey === to;

const currentUser = ref("");
const currentTeam = ref("");

const hasSelectedUser = () => {
    const id = selectedUserId.value;
    return id != null && String(id).trim() !== "";
};

router.beforeEach((to, from) => {
    if (to.path === "/users" || to.path.startsWith("/settings")) return true;
    if (hasSelectedUser()) return true;
    showAlert("사용자를 선택해주세요");
    return from.path === "/users" ? false : "/users";
});

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
        currentTeam.value = foundTeam ? foundTeam.team_name : `부서 ${storedTeamId}`;
    } catch {
        currentUser.value = `사용자 ${storedId}`;
        currentTeam.value = `부서 ${storedTeamId}`;
    }
};

watch(
    [selectedUserId, selectedTeamId],
    ([id, teamId]) => {
        loadCurrent(id, teamId);
    },
    { immediate: true },
);

watch(
    () => route.path,
    () => {
        closeDrawer();
    },
);

watch(isNarrow, (narrow) => {
    if (!narrow) {
        closeDrawer();
    }
});

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
    if (event.key === "Escape" && drawerOpen.value) {
        event.preventDefault();
        closeDrawer();
        return;
    }
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
    <aside
        id="app-sidebar"
        class="sidebar"
        :class="{ 'is-collapsed': collapsedEffective, 'is-drawer-open': drawerOpen }"
    >
        <div class="sidebar-brand">
            <span v-if="!collapsedEffective" class="sidebar-brand-name">일일보고</span>
            <button
                type="button"
                class="sidebar-collapse-btn"
                :aria-expanded="!collapsedEffective"
                :aria-label="collapsedEffective ? '사이드바 펼치기' : '사이드바 접기'"
                :title="collapsedEffective ? '사이드바 펼치기' : '사이드바 접기'"
                @click="toggleCollapsed"
            >
                <PanelLeftOpen v-if="collapsedEffective" :size="16" />
                <PanelLeftClose v-else :size="16" />
            </button>
        </div>

        <nav class="nav-links">
            <div v-for="group in navGroups" :key="group.label" class="nav-group">
                <p class="nav-group-label">{{ group.label }}</p>
                <router-link
                    v-for="item in group.items"
                    :key="item.to"
                    :to="item.to"
                    class="nav-link"
                    :class="{ 'router-link-exact-active': isNavActive(item.to) }"
                    :title="collapsedEffective ? item.label : null"
                >
                    <component :is="item.icon" :size="16" />
                    <span v-if="!collapsedEffective" class="nav-link-label">{{ item.label }}</span>
                </router-link>
            </div>
        </nav>

        <div class="sidebar-footer">
            <div class="sidebar-user">
                <span class="sidebar-avatar">{{ userInitial() }}</span>
                <span class="sidebar-user-meta">
                    <span class="sidebar-user-name">{{ currentUser || "사용자 미선택" }}</span>
                    <span class="sidebar-user-team">{{ currentTeam || "부서 미선택" }}</span>
                </span>
            </div>
            <button
                type="button"
                class="sidebar-logout"
                :title="collapsedEffective ? '사용자 변경' : null"
                @click="logout"
            >
                <ArrowLeftRight :size="14" />
                <span>사용자 변경</span>
            </button>
        </div>
    </aside>
    <div v-if="drawerOpen" class="sidebar-overlay" @click="closeDrawer" />

    <main class="main-content">
        <header class="topbar">
            <button
                type="button"
                class="topbar-drawer-btn"
                aria-label="메뉴 열기"
                :aria-expanded="drawerOpen"
                aria-controls="app-sidebar"
                @click="openDrawer"
            >
                <Menu :size="18" />
            </button>
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
