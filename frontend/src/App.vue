<script setup>
import {
    FolderKanban,
    PenSquare,
    CalendarDays,
    FileBarChart,
} from "lucide-vue-next";

const navItems = [
    { to: "/", label: "프로젝트 목록", icon: FolderKanban },
    { to: "/report", label: "보고서 작성", icon: PenSquare },
    { to: "/activities", label: "활동 기록", icon: CalendarDays },
    { to: "/weekly", label: "주간 보고서", icon: FileBarChart },
    { to: "/users", label: "사용자 선택", icon: FileBarChart },
];
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
