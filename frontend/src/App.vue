<script setup>
import {
    FolderKanban,
    PenSquare,
    CalendarDays,
    FileBarChart,
    GitMerge,
    GitGraph,
} from "lucide-vue-next";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { LogOut, UserRound } from "lucide-vue-next";
import useAPI from "./composables/useApi";

const router = useRouter();
const { getUsers } = useAPI();

const navItems = [
    { to: "/", label: "프로젝트 목록", icon: FolderKanban },
    { to: "/project-timeline", label: "프로젝트 흐름", icon: GitGraph },
    { to: "/report", label: "보고서 작성", icon: PenSquare },
    { to: "/activities", label: "사용자 활동", icon: CalendarDays },
    { to: "/weekly", label: "주간 보고서", icon: FileBarChart },
    { to: "/aliases", label: "별칭 관리", icon: GitMerge },
    { to: "/project-name", label: "프로젝트 명 관리", icon: FolderKanban },
];

const currentUser = ref("");

const loadCurrentUser = async () => {
    const storedId = localStorage.getItem("report-selectedUser");
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

const logout = () => {
    if (window.confirm("사용자를 변경하시겠습니까?")) {
        localStorage.removeItem("report-selectedUser");
        sessionStorage.removeItem("selectedUser");
        sessionStorage.removeItem("reportData");
        sessionStorage.removeItem("reportRaw");
        sessionStorage.removeItem("reportDate");
        currentUser.value = "";
        router.push("/users");
    }
};

// DOMContentLoaded 는 Vue 마운트 이전에 이미 발생하므로 리스너가 실행되지 않는다.
// onMounted 에서 확인한다.
onMounted(() => {
    loadCurrentUser();
    if (localStorage.getItem("report-selectedUser") == null) {
        alert("사용자를 선택해주세요");
        router.push("/users");
    }
});
</script>

<template>
    <aside class="sidebar">
        <div class="sidebar-brand">
            <span class="brand-mark">R</span>
            <span class="brand-text">보고서<br />자동화 도구</span>
        </div>
        <nav class="nav-links">
            <router-link
                v-for="item in navItems"
                :key="item.to"
                :to="item.to"
                class="nav-link"
            >
                <component :is="item.icon" :size="16" />
                {{ item.label }}
            </router-link>
        </nav>

        <div class="sidebar-footer">
            <div class="sidebar-user">
                <UserRound :size="16" />
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
