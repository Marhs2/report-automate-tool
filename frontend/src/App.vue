<script setup>
import {
    FolderKanban,
    PenSquare,
    CalendarDays,
    FileBarChart,
    GitGraph,
    ArrowLeftRight,
    Settings2,
} from "lucide-vue-next";
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import useAPI from "./composables/useApi";
import { selectedUserId } from "./composables/useSelectedUser";
import { useToast } from "./composables/useToast";

const router = useRouter();
const route = useRoute();
const { getUsers } = useAPI();
const { toasts } = useToast();

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
        ],
    },
];

const isNavActive = (to) => {
    const path = route.path;
    if (to === "/") return path === "/" || /^\/report\/\d+/.test(path);
    if (to === "/report") return path === "/report" || path === "/report-result";
    return path === to || path.startsWith(`${to}/`);
};

const currentUser = ref("");

const loadCurrentUser = async (storedId) => {
    if (!storedId) {
        currentUser.value = "";
        return;
    }
    try {
        const users = await getUsers();
        const found = users.find((u) => String(u.id) === String(storedId));
        currentUser.value = found ? found.name : `사용자 ${storedId}`;
    } catch {
        currentUser.value = `사용자 ${storedId}`;
    }
};

watch(
    selectedUserId,
    (id) => {
        loadCurrentUser(id);
    },
    { immediate: true }
);

const userInitial = () => {
    const name = currentUser.value || "";
    return name.slice(0, 1) || "?";
};

const logout = () => {
    if (window.confirm("사용자를 변경하시겠습니까?")) {
        selectedUserId.value = null;
        sessionStorage.removeItem("selectedUser");
        sessionStorage.removeItem("reportData");
        sessionStorage.removeItem("reportRaw");
        sessionStorage.removeItem("reportDate");
        router.push("/users");
    }
};

onMounted(() => {
    if (selectedUserId.value == null) {
        router.push("/users");
    }
});
</script>

<template>
    <aside class="sidebar">

        <nav class="nav-links">
            <div v-for="group in navGroups" :key="group.label" class="nav-group">
                <p class="nav-group-label">{{ group.label }}</p>
                <router-link
                    v-for="item in group.items"
                    :key="item.to"
                    :to="item.to"
                    class="nav-link"
                    :class="{ 'router-link-exact-active': isNavActive(item.to) }"
                >
                    <component :is="item.icon" :size="16" />
                    {{ item.label }}
                </router-link>
            </div>
        </nav>

        <div class="sidebar-footer">
            <div class="sidebar-user">
                <span class="sidebar-avatar">{{ userInitial() }}</span>
                <span class="sidebar-user-name">{{ currentUser || "사용자 미선택" }}</span>
            </div>
            <button class="sidebar-logout" @click="logout">
                <ArrowLeftRight :size="14" />
                사용자 변경
            </button>
        </div>
    </aside>

    <main class="main-content">
        <RouterView />
    </main>
    <div class="toast-stack" aria-live="polite">
        <div
            v-for="item in toasts"
            :key="item.id"
            class="toast"
            :class="'toast-' + item.type"
        >
            {{ item.message }}
        </div>
    </div>
</template>
