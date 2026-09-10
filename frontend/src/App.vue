<script setup>
import {
    FolderKanban,
    PenSquare,
    CalendarDays,
    FileBarChart,
    GitGraph,
    LogOut,
    Settings2,
} from "lucide-vue-next";
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import useAPI from "./composables/useApi";
import { selectedUserId } from "./composables/useSelectedUser";

const router = useRouter();
const { getUsers } = useAPI();

const navGroups = [
    {
        label: "조회",
        items: [
            { to: "/", label: "프로젝트 목록", icon: FolderKanban },
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
            { to: "/project-name", label: "프로젝트 명 관리", icon: Settings2 },
        ],
    },
];

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
        alert("사용자를 선택해주세요");
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
                <LogOut :size="14" />
                사용자 변경
            </button>
        </div>
    </aside>

    <main class="main-content">
        <RouterView />
    </main>
</template>
