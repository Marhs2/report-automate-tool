<script setup>
import {
    FolderKanban,
    CalendarDays,
    FileBarChart,
    GitGraph,
    LogOut,
    Settings2,
    Shield,
    PanelLeftClose,
    PanelLeftOpen,
} from "lucide-vue-next";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "./composables/useApi";
import { selectedUserId } from "./composables/useSelectedUser";
import { selectedTeamId } from "./composables/useSelectedTeam";
import { hasSession, isAdmin, sessionToken } from "./composables/useSession";
import { useDialog } from "./composables/useDialog";
import { useSidebar } from "./composables/useSidebar";
import { PRIMARY_NAV } from "./lib/nav";
import { pageParentOverride, pageTitleOverride } from "./composables/usePageMeta";

const router = useRouter();
const route = useRoute();
const { getMe, getTeams, postLogout } = useApi();
const { collapsedEffective, isNarrow, toggleCollapsed } = useSidebar();
const {
    open: dialogOpen,
    locked: dialogLocked,
    mode: dialogMode,
    title: dialogTitle,
    message: dialogMessage,
    help: dialogHelp,
    confirmLabel: dialogConfirmLabel,
    cancelLabel: dialogCancelLabel,
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
    "/admin": Shield,
};

const navItems = PRIMARY_NAV.map((item) => ({
    ...item,
    icon: NAV_ICONS[item.to] || Settings2,
}));

const mainNavItems = navItems.filter((item) => item.group !== "설정");
const settingsNavItems = navItems.filter((item) => item.group === "설정");
const adminNavItems = computed(() =>
    isAdmin.value
        ? [{ to: "/admin", label: "관리", shortLabel: "관리", icon: Shield }]
        : [],
);

/** 화면이 자기 제목·상위 위치를 덮어쓸 수 있다.
 *  같은 라우트라도 "읽는 중"과 "고치는 중"의 이름이 달라야 한다. */
const pageMeta = computed(() => ({
    title: pageTitleOverride.value || route.meta.title || "일일보고",
    parent: pageParentOverride.value || route.meta.parent || null,
    action: route.meta.action || null,
}));

const isNavActive = (to) => route.meta.navKey === to;

/** 모바일은 하단 탭이 작업만 담당한다. 설정과 관리는 상단으로 올려 탭을 4개로 줄인다. */
const topTools = computed(() =>
    isNarrow.value ? [...settingsNavItems, ...adminNavItems.value] : [],
);
const bottomNavItems = computed(() => (isNarrow.value ? mainNavItems : []));

const currentUser = ref("");
const currentTeam = ref("");

const isPublicPage = computed(() => Boolean(route.meta.public));

router.beforeEach((to) => {
    if (to.meta.public) {
        if (hasSession() && to.path === "/login") return "/";
        return true;
    }
    if (!hasSession()) return "/login";
    if (to.meta.admin && !isAdmin.value) return "/settings";
    return true;
});

const clearSession = () => {
    sessionToken.value = "";
    isAdmin.value = false;
    selectedUserId.value = null;
    selectedTeamId.value = null;
    currentUser.value = "";
    currentTeam.value = "";
    sessionStorage.removeItem("reportData");
    sessionStorage.removeItem("reportRaw");
    sessionStorage.removeItem("reportDate");
};

const loadCurrent = async () => {
    if (!hasSession()) {
        currentUser.value = "";
        currentTeam.value = "";
        return;
    }
    try {
        const me = await getMe();
        selectedUserId.value = me.member_id;
        selectedTeamId.value = me.team_id ?? null;
        isAdmin.value = Boolean(me.is_admin);
        currentUser.value = me.name || `사용자 ${me.member_id}`;
        const teams = await getTeams();
        const foundTeam = teams.find((t) => String(t.id) === String(me.team_id));
        currentTeam.value = foundTeam ? foundTeam.team_name : me.team_id ? `부서 ${me.team_id}` : "";
    } catch (error) {
        if (error?.response?.status === 401) {
            clearSession();
            if (route.path !== "/login") router.replace("/login");
            return;
        }
        currentUser.value = "로그인됨";
    }
};

watch(sessionToken, () => {
    loadCurrent();
}, { immediate: true });

/** 사용자를 바꾸면 앞사람이 쓰던 임시 보고가 남아 있어서는 안 된다. */
watch(selectedUserId, (id, previous) => {
    if (previous == null || String(id) === String(previous)) return;
    sessionStorage.removeItem("reportData");
    sessionStorage.removeItem("reportRaw");
    sessionStorage.removeItem("reportDate");
});

const syncOverlayLock = () => {
    document.documentElement.classList.toggle("is-overlay-open", dialogOpen.value);
};

watch(dialogOpen, syncOverlayLock, { immediate: true });

const userInitial = () => {
    const name = currentUser.value || "";
    return name.slice(0, 1) || "?";
};

const logout = async () => {
    await postLogout();
    clearSession();
    router.replace("/login");
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
    if (!hasSession()) {
        router.push("/login");
    }
});

onUnmounted(() => {
    window.removeEventListener("keydown", onDialogKeydown);
    document.documentElement.classList.remove("is-overlay-open");
});
</script>

<template>
    <RouterView v-if="isPublicPage" />
    <template v-else>
    <aside
        id="app-sidebar"
        class="sidebar"
        :class="{ 'is-collapsed': collapsedEffective }"
    >
        <div class="sidebar-brand">
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

        <nav class="nav-links" aria-label="주요 메뉴">
            <p v-if="!collapsedEffective" class="nav-group-label">작업</p>
            <router-link
                v-for="item in mainNavItems"
                :key="item.to"
                :to="item.to"
                class="nav-link"
                :class="{ 'router-link-exact-active': isNavActive(item.to) }"
                :title="collapsedEffective ? item.label : null"
            >
                <component :is="item.icon" :size="16" />
                <span v-if="!collapsedEffective" class="nav-link-label">{{ item.label }}</span>
            </router-link>
            <p v-if="!collapsedEffective" class="nav-group-label">설정</p>
            <router-link
                v-for="item in settingsNavItems"
                :key="item.to"
                :to="item.to"
                class="nav-link"
                :class="{ 'router-link-exact-active': isNavActive(item.to) }"
                :title="collapsedEffective ? item.label : null"
            >
                <component :is="item.icon" :size="16" />
                <span v-if="!collapsedEffective" class="nav-link-label">{{ item.label }}</span>
            </router-link>
            <router-link
                v-for="item in adminNavItems"
                :key="item.to"
                :to="item.to"
                class="nav-link"
                :class="{ 'router-link-exact-active': isNavActive(item.to) }"
                :title="collapsedEffective ? item.label : null"
            >
                <component :is="item.icon" :size="16" />
                <span v-if="!collapsedEffective" class="nav-link-label">{{ item.label }}</span>
            </router-link>
        </nav>

        <div class="sidebar-footer">
            <div class="sidebar-user">
                <span class="sidebar-avatar">{{ userInitial() }}</span>
                <span class="sidebar-user-meta">
                    <span class="sidebar-user-name">{{ currentUser || "로그인 필요" }}</span>
                    <span class="sidebar-user-team">{{ currentTeam || "부서 없음" }}</span>
                </span>
            </div>
            <button
                type="button"
                class="sidebar-logout"
                :title="collapsedEffective ? '로그아웃' : null"
                @click="logout"
            >
                <LogOut :size="14" />
                <span>로그아웃</span>
            </button>
        </div>
    </aside>

    <main class="main-content" :class="{ 'has-bottom-nav': isNarrow }">
        <header class="topbar">
            <nav class="topbar-crumbs" aria-label="현재 위치">
                <router-link v-if="pageMeta.parent" class="topbar-crumb" :to="pageMeta.parent.to">
                    {{ pageMeta.parent.label }}
                </router-link>
                <span v-if="pageMeta.parent" class="topbar-crumb-sep" aria-hidden="true">›</span>
                <span class="topbar-title" aria-current="page">{{ pageMeta.title }}</span>
            </nav>
            <div class="topbar-end">
                <router-link
                    v-for="item in topTools"
                    :key="item.to"
                    class="topbar-tool"
                    :class="{ 'is-active': isNavActive(item.to) }"
                    :to="item.to"
                    :aria-current="isNavActive(item.to) ? 'page' : null"
                >
                    {{ item.shortLabel || item.label }}
                </router-link>
                <router-link
                    v-if="pageMeta.action"
                    class="btn btn-primary btn-small topbar-action"
                    :to="pageMeta.action.to"
                >
                    {{ isNarrow ? "작성" : pageMeta.action.label }}
                </router-link>
            </div>
        </header>
        <div class="main-body">
            <RouterView />
        </div>
    </main>
    <nav v-if="isNarrow" class="app-bottom-nav" aria-label="주요 메뉴">
        <router-link
            v-for="item in bottomNavItems"
            :key="item.to"
            :to="item.to"
            :class="{ 'is-active': isNavActive(item.to) }"
            :aria-current="isNavActive(item.to) ? 'page' : null"
        >
            <component :is="item.icon" :size="20" />
            <span>{{ item.shortLabel || item.label }}</span>
        </router-link>
    </nav>
    </template>
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
