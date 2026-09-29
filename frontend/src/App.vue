<script setup>
import {
    FolderKanban,
    CalendarDays,
    FileBarChart,
    GitGraph,
    LayoutDashboard,
    PenLine,
    LogOut,
    Settings2,
    Shield,
    PanelLeftClose,
    PanelLeftOpen,
    ChevronLeft,
    ChevronRight,
    FileText,
    MessageSquare,
    MoreHorizontal,
    TrendingUp,
    X,
} from "lucide-vue-next";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "./composables/useApi";
import { selectedUserId } from "./composables/useSelectedUser";
import { selectedTeamId } from "./composables/useSelectedTeam";
import { hasSession, isAdmin, sessionToken } from "./composables/useSession";
import { useDialog } from "./composables/useDialog";
import { useSidebar } from "./composables/useSidebar";
import { COMPOSE_CHOICES, MOBILE_TABS, MORE_LINKS, PRIMARY_NAV } from "./lib/nav";
import { useMyWeek } from "./composables/useMyWeek";
import { TODAY_LABELS } from "./lib/weekStatus";
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
    "/": LayoutDashboard,
    "/compose": PenLine,
    "/reports": FolderKanban,
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
    title: pageTitleOverride.value || route.meta.title || "내 현황",
    parent: pageParentOverride.value || route.meta.parent || null,
    action: route.meta.action || null,
}));

const isNavActive = (to) => route.meta.navKey === to;

/** 모바일 하단 탭: 현황 · 일일보고 · 작성 · 주간 · 더보기. 작성과 더보기는 시트를 연다. */
const TAB_ICONS = {
    home: LayoutDashboard,
    daily: FolderKanban,
    write: PenLine,
    weekly: FileBarChart,
    more: MoreHorizontal,
};
const bottomTabs = computed(() =>
    MOBILE_TABS.map((tab) => ({
        ...tab,
        icon: TAB_ICONS[tab.id],
        active: tab.navKeys.includes(String(route.meta.navKey || "")),
    })),
);
const COMPOSE_ICONS = { daily: FolderKanban, meeting: MessageSquare, general: FileText, sales: TrendingUp };
const composeChoices = COMPOSE_CHOICES.map((item) => ({ ...item, icon: COMPOSE_ICONS[item.id] }));
const moreLinks = computed(() => [
    ...MORE_LINKS,
    ...(isAdmin.value ? [{ to: "/admin", label: "관리자", hint: "사용자 · 부서" }] : []),
]);
const openSheet = ref(null);
const closeSheet = () => {
    openSheet.value = null;
};

const { todayState, todayMissing, refreshMyWeek } = useMyWeek();
const todayLabel = computed(() => TODAY_LABELS[todayState.value] || "");

const currentUser = ref("");
const currentTeam = ref("");

const isPublicPage = computed(() => Boolean(route.meta.public));
/** 작성·수정 화면은 메뉴와 제목 줄을 치우고 뒤로 가기만 남긴다. */
const FOCUS_ROUTES = new Set(["report", "report-result", "weekly-detail"]);
const isWritePage = computed(() => FOCUS_ROUTES.has(String(route.name || "")));

const goBack = () => {
    if (window.history.state?.back) router.back();
    else if (route.name === "weekly-detail") router.push("/weekly");
    else router.push(pageMeta.value.parent?.to || "/");
};

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

/** 저장하고 돌아오면 배지가 바로 바뀌어야 한다. 화면을 옮길 때마다 다시 본다. */
watch(
    () => [route.name, selectedUserId.value],
    () => {
        closeSheet();
        if (!isPublicPage.value && hasSession()) refreshMyWeek();
    },
    { immediate: true },
);

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
        v-if="!isWritePage"
        id="app-sidebar"
        class="sidebar"
        :class="{ 'is-collapsed': collapsedEffective }"
    >
        <div class="sidebar-brand">
            <router-link v-if="!collapsedEffective" to="/" class="sidebar-brand-link">
                <span class="sidebar-mark" aria-hidden="true">보</span>
                <span class="sidebar-brand-name">보고 취합</span>
            </router-link>
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
                <span
                    v-if="item.to === '/compose' && todayMissing"
                    class="nav-badge"
                    :class="{ 'is-dot': collapsedEffective }"
                >{{ collapsedEffective ? "" : todayLabel }}</span>
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
                <LogOut :size="16" />
                <span>로그아웃</span>
            </button>
        </div>
    </aside>

    <main class="main-content" :class="{ 'has-bottom-nav': isNarrow && !isWritePage, 'is-focus-write': isWritePage }">
        <div v-if="isWritePage" class="write-backbar">
            <button type="button" class="write-back" @click="goBack">
                <ChevronLeft :size="20" />
                {{ pageMeta.parent?.label || "뒤로" }}
            </button>
            <span class="write-backbar-title">{{ pageMeta.title }}</span>
        </div>
        <header v-else class="topbar">
            <nav class="topbar-crumbs" aria-label="현재 위치">
                <router-link v-if="pageMeta.parent" class="topbar-crumb" :to="pageMeta.parent.to">
                    {{ pageMeta.parent.label }}
                </router-link>
                <span v-if="pageMeta.parent" class="topbar-crumb-sep" aria-hidden="true">›</span>
                <span class="topbar-title" aria-current="page">{{ pageMeta.title }}</span>
            </nav>
            <div class="topbar-end">
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
    <nav v-if="isNarrow && !isWritePage" class="app-bottom-nav" aria-label="주요 메뉴">
        <template v-for="tab in bottomTabs" :key="tab.id">
            <router-link
                v-if="tab.to"
                :to="tab.to"
                :class="{ 'is-active': tab.active }"
                :aria-current="tab.active ? 'page' : null"
            >
                <component :is="tab.icon" :size="20" />
                <span>{{ tab.label }}</span>
            </router-link>
            <button
                v-else
                type="button"
                :class="{ 'is-active': tab.active || openSheet === tab.sheet }"
                :aria-expanded="openSheet === tab.sheet"
                aria-haspopup="dialog"
                @click="openSheet = openSheet === tab.sheet ? null : tab.sheet"
            >
                <component :is="tab.icon" :size="20" />
                <span>{{ tab.label }}</span>
                <i v-if="tab.id === 'write' && todayMissing" class="tab-dot" aria-label="오늘 미제출"></i>
            </button>
        </template>
    </nav>
    <div v-if="openSheet" class="app-sheet-overlay" @click.self="closeSheet">
        <div
            class="app-sheet"
            role="dialog"
            aria-modal="true"
            :aria-label="openSheet === 'compose' ? '무엇을 쓸까요' : '더보기'"
        >
            <div class="app-sheet-head">
                <h2>{{ openSheet === "compose" ? "무엇을 쓸까요?" : "더보기" }}</h2>
                <button type="button" class="app-sheet-close" aria-label="닫기" @click="closeSheet">
                    <X :size="16" />
                </button>
            </div>
            <template v-if="openSheet === 'compose'">
                <router-link
                    v-for="(item, index) in composeChoices"
                    :key="item.id"
                    :to="item.to"
                    class="app-sheet-row"
                    :class="{ 'is-lead': index === 0 }"
                >
                    <span class="app-sheet-icon"><component :is="item.icon" :size="18" /></span>
                    <span class="app-sheet-text">
                        <span class="app-sheet-label">{{ item.label }}</span>
                        <span
                            class="app-sheet-hint"
                            :class="{ 'is-alert': index === 0 && todayMissing }"
                        >{{ index === 0 && todayLabel ? todayLabel : item.hint }}</span>
                    </span>
                    <ChevronRight :size="16" class="app-sheet-chevron" />
                </router-link>
            </template>
            <template v-else>
                <router-link v-for="item in moreLinks" :key="item.to" :to="item.to" class="app-sheet-row">
                    <span class="app-sheet-text">
                        <span class="app-sheet-label">{{ item.label }}</span>
                        <span class="app-sheet-hint">{{ item.hint }}</span>
                    </span>
                    <ChevronRight :size="16" class="app-sheet-chevron" />
                </router-link>
                <button type="button" class="app-sheet-row is-danger" @click="logout">
                    <span class="app-sheet-text">
                        <span class="app-sheet-label">로그아웃</span>
                        <span class="app-sheet-hint">{{ currentUser }} · {{ currentTeam || "부서 없음" }}</span>
                    </span>
                </button>
            </template>
        </div>
    </div>
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
