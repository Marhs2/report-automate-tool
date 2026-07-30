<script setup>
import {
    FolderKanban,
    PenSquare,
    CalendarDays,
    FileBarChart,
    GitMerge,
    GitGraph,
} from "lucide-vue-next";
import { onMounted } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

const navItems = [
    { to: "/", label: "프로젝트 목록", icon: FolderKanban },
    { to: "/project-timeline", label: "프로젝트 흐름", icon: GitGraph },
    { to: "/report", label: "보고서 작성", icon: PenSquare },
    { to: "/activities", label: "활동 기록", icon: CalendarDays },
    { to: "/weekly", label: "주간 보고서", icon: FileBarChart },
    { to: "/aliases", label: "별칭 관리", icon: GitMerge },
];

// DOMContentLoaded 는 Vue 마운트 이전에 이미 발생하므로 리스너가 실행되지 않는다.
// onMounted 에서 확인한다.
onMounted(() => {
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
    </aside>

    <main class="main-content">
        <RouterView />
    </main>
</template>
