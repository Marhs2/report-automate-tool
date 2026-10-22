<script setup>
import { ChevronLeft, FileBarChart, PenLine, Users } from "lucide-vue-next";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useApi from "./composables/useApi";
import { selectedUserId } from "./composables/useSelectedUser";
import { selectedTeamId } from "./composables/useSelectedTeam";
import { hasSession, isAdmin, leaderTeamId, sessionToken } from "./composables/useSession";
import { useDialog } from "./composables/useDialog";
import { useSidebar } from "./composables/useSidebar";
import { ACCOUNT_LINKS, COMPOSE_CHOICES, MOBILE_TABS, PRIMARY_NAV } from "./lib/nav";
import { useMyWeek } from "./composables/useMyWeek";
import { TODAY_LABELS } from "./lib/weekStatus";
import { pageParentOverride, pageTitleOverride } from "./composables/usePageMeta";

const router = useRouter();
const route = useRoute();
const { getMe, getTeams, postLogout } = useApi();
const { isNarrow } = useSidebar();
const {
    open: dialogOpen,
    locked: dialogLocked,
    mode: dialogMode,
    title: dialogTitle,
    message: dialogMessage,
    help: dialogHelp,
    confirmLabel: dialogConfirmLabel,
    cancelLabel: dialogCancelLabel,
    danger: dialogDanger,
    alert: showAlert,
    accept: acceptDialog,
    reject: rejectDialog,
    isFreshKey: isFreshDialogKey,
    acceptKey: acceptDialogKey,
    rejectKey: rejectDialogKey,
} = useDialog();

const navItems = PRIMARY_NAV;

/** 화면이 자기 제목·상위 위치를 덮어쓸 수 있다.
 *  같은 라우트라도 "읽는 중"과 "고치는 중"의 이름이 달라야 한다. */
/** 오늘 화면과 회의록 · 영업보고는 같은 "쓰기" 화면이다. 제목 옆 전환으로 오간다. 기존 기록을 고칠 때는 숨긴다. */
const activeKind = computed(() => (route.name === "compose" ? String(route.query.kind || "meeting") : "daily"));
const showKindSwitch = computed(() => Boolean(route.meta.kindSwitch) && !route.params.id);
const KIND_TITLES = { meeting: "회의록", sales: "영업보고" };

const pageMeta = computed(() => ({
    title:
        pageTitleOverride.value ||
        (route.name === "compose" ? KIND_TITLES[activeKind.value] : "") ||
        route.meta.title ||
        "오늘 한 일",
    parent: pageParentOverride.value || route.meta.parent || null,
    action: route.meta.action || null,
}));

const isNavActive = (to) => route.meta.navKey === to;

/** 모바일 하단 탭: 위쪽 탭과 같은 오늘 · 팀 · 주간. */
const TAB_ICONS = {
    today: PenLine,
    team: Users,
    weekly: FileBarChart,
};
const bottomTabs = computed(() =>
    MOBILE_TABS.map((tab) => ({
        ...tab,
        icon: TAB_ICONS[tab.id],
        active: tab.navKeys.includes(String(route.meta.navKey ?? "")),
    })),
);

/** 오른쪽 위 이름 동그라미 메뉴. 관리자에게만 관리가 더 보인다. */
const accountLinks = computed(() => [
    ...ACCOUNT_LINKS,
    ...(isAdmin.value ? [{ to: "/admin", label: "관리", hint: "사용자 · 부서" }] : []),
]);
const accountOpen = ref(false);
const closeAccount = () => {
    accountOpen.value = false;
};

const { todayState, todayMissing, refreshMyWeek } = useMyWeek();
const todayLabel = computed(() => TODAY_LABELS[todayState.value] || "");

const currentUser = ref("");
const currentTeam = ref("");

const isPublicPage = computed(() => Boolean(route.meta.public));
/** 작성·수정 화면은 메뉴와 제목 줄을 치우고 뒤로 가기만 남긴다. */
const FOCUS_ROUTES = new Set(["report-result", "weekly-detail"]);
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
    leaderTeamId.value = null;
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
        leaderTeamId.value = me.leads_team_id ?? null;
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
        closeAccount();
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
    if (accountOpen.value && event.key === "Escape") {
        closeAccount();
        return;
    }
    if (!dialogOpen.value) return;
    if (event.key !== "Escape" && event.key !== "Enter") return;
    event.preventDefault();
    // 대화상자를 연 그 키와 누르고 있는 키의 반복만 무시한다. 새로 누른 키는 한 번에 닫는다.
    if (!isFreshDialogKey(event)) return;
    if (event.key === "Escape" && dialogMode.value === "confirm") rejectDialogKey();
    else acceptDialogKey();
};

onMounted(() => {
    window.addEventListener("keydown", onDialogKeydown);
    window.addEventListener("click", closeAccount);
    if (!hasSession()) {
        router.push("/login");
    }
});

onUnmounted(() => {
    window.removeEventListener("keydown", onDialogKeydown);
    window.removeEventListener("click", closeAccount);
    document.documentElement.classList.remove("is-overlay-open");
});
</script>

<template>
    <RouterView v-if="isPublicPage" />
    <template v-else>
    <header class="appbar">
        <router-link to="/" class="appbar-brand" aria-label="일일보고 처음 화면">일일보고</router-link>
        <nav class="appbar-tabs" aria-label="주요 메뉴">
            <router-link
                v-for="item in navItems"
                :key="item.to"
                :to="item.to"
                class="appbar-tab"
                :class="{ 'is-active': isNavActive(item.navKey) }"
                :aria-current="isNavActive(item.navKey) ? 'page' : null"
            >
                {{ item.label }}
                <i v-if="item.navKey === '/' && todayMissing" class="appbar-dot" :title="todayLabel" aria-label="오늘 보고 아직 안 씀"></i>
            </router-link>
        </nav>
        <div class="appbar-end">
            <button
                type="button"
                class="appbar-me"
                :aria-expanded="accountOpen"
                aria-haspopup="menu"
                :aria-label="`${currentUser || '내 계정'} · 설정과 로그아웃`"
                @click.stop="accountOpen = !accountOpen"
            >
                {{ userInitial() }}
            </button>
            <div v-if="accountOpen" class="account-menu" role="menu" @click.stop>
                <div class="account-menu-who">
                    <span class="account-menu-name">{{ currentUser || "로그인 필요" }}</span>
                    <span class="account-menu-team">{{ currentTeam || "부서 없음" }}</span>
                </div>
                <router-link
                    v-for="item in accountLinks"
                    :key="item.to"
                    :to="item.to"
                    class="account-menu-row"
                    role="menuitem"
                >
                    <span class="account-menu-label">{{ item.label }}</span>
                    <span class="account-menu-hint">{{ item.hint }}</span>
                </router-link>
                <button type="button" class="account-menu-row is-danger" role="menuitem" @click="logout">
                    <span class="account-menu-label">로그아웃</span>
                </button>
            </div>
        </div>
    </header>

    <main class="main-content" :class="{ 'has-bottom-nav': isNarrow && !isWritePage, 'is-focus-write': isWritePage }">
        <div class="main-body">
            <!-- 모든 화면이 같은 머리: 위로 가는 링크, 그 아래 큰 제목. 상세 화면은 본문이 이름을 제목으로 쓴다. -->
            <div v-if="isWritePage" class="page-hero">
                <button type="button" class="page-hero-back" @click="goBack">
                    <ChevronLeft :size="18" />{{ pageMeta.parent?.label || "뒤로" }}
                </button>
            </div>
            <div v-else-if="!route.meta.hideHero" class="page-hero">
                <router-link v-if="pageMeta.parent" class="page-hero-back" :to="pageMeta.parent.to">
                    <ChevronLeft :size="18" />{{ pageMeta.parent.label }}
                </router-link>
                <div class="page-hero-row">
                    <h1 class="page-hero-title">{{ pageMeta.title }}</h1>
                    <nav v-if="showKindSwitch" class="seg kind-switch" aria-label="보고 종류">
                        <router-link
                            v-for="item in COMPOSE_CHOICES"
                            :key="item.id"
                            :to="item.to"
                            :class="{ 'is-on': activeKind === item.id }"
                            :aria-current="activeKind === item.id ? 'page' : null"
                        >
                            {{ item.label }}
                        </router-link>
                    </nav>
                </div>
            </div>
            <RouterView />
        </div>
    </main>
    <nav v-if="isNarrow && !isWritePage" class="app-bottom-nav" aria-label="주요 메뉴">
        <router-link
            v-for="tab in bottomTabs"
            :key="tab.id"
            :to="tab.to"
            :class="{ 'is-active': tab.active }"
            :aria-current="tab.active ? 'page' : null"
        >
            <component :is="tab.icon" :size="20" />
            <span>{{ tab.label }}</span>
            <i v-if="tab.id === 'today' && todayMissing" class="tab-dot" aria-label="오늘 보고 아직 안 씀"></i>
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
                    class="btn"
                    :class="dialogDanger ? 'btn-danger-solid' : 'btn-primary'"
                    :disabled="dialogLocked"
                    @click="acceptDialog"
                >
                    {{ dialogConfirmLabel }}
                </button>
            </div>
        </div>
    </div>
</template>
