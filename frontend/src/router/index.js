import { createRouter, createWebHistory } from "vue-router";
// 화면마다 따로 나눠 불러온다. 한 번에 묶으면 첫 화면이 모든 화면 코드를 다 받을 때까지 기다린다.
const reportResult = () => import("../components/report-result.vue");
const projectList = () => import("../components/projects-list.vue");
// 첫 화면(오늘 = 일일보고 쓰기)은 나누지 않는다. 나누면 본 코드 다음에 한 번 더 받아야 해서 첫 글자가 늦게 뜬다.
import today from "../components/report.vue";
const dashboard = () => import("../components/dashboard.vue");
const team = () => import("../components/team.vue");
const compose = () => import("../components/compose.vue");
const activities = () => import("../components/user-activities.vue");
const weekly = () => import("../components/weekly-report.vue");
const weeklyDetail = () => import("../components/weekly-detail.vue");
const projectTimeline = () => import("../components/project-timeline.vue");
const settings = () => import("../components/settings.vue");
const admin = () => import("../components/admin.vue");
const login = () => import("../components/login.vue");

const routes = [
  {
    path: "/",
    name: "today",
    component: today,
    meta: { title: "오늘 한 일", navKey: "/", narrow: true },
  },
  {
    path: "/me",
    name: "dashboard",
    component: dashboard,
    meta: { title: "내 현황", navKey: "", hideHero: true },
  },
  {
    path: "/team",
    name: "team",
    component: team,
    meta: { title: "팀", navKey: "/team", narrow: true },
  },
  {
    path: "/reports",
    name: "reports",
    component: projectList,
    meta: {
      title: "검색 · 필터",
      navKey: "/team",
      parent: { to: "/team", label: "팀" },
    },
  },
  {
    path: "/compose/:id?",
    name: "compose",
    component: compose,
    meta: {
      title: "다른 보고",
      navKey: "/",
      parent: { to: "/", label: "오늘" },
    },
    // 일일보고는 "오늘" 화면이 곧 작성 화면이다.
    beforeEnter: (to) => {
      const kind = String(to.query.kind || "daily");
      if (!to.params.id && ["daily", "general", "cards"].includes(kind)) return { path: "/" };
      return true;
    },
  },
  {
    path: "/report",
    redirect: "/",
  },
  {
    path: "/report-result/:id?",
    name: "report-result",
    component: reportResult,
    meta: {
      title: "일일보고 상세",
      navKey: "/team",
      parent: { to: "/team", label: "팀" },
    },
  },
  {
    path: "/activities",
    name: "activities",
    component: activities,
    meta: {
      title: "제출 기록",
      navKey: "/team",
      parent: { to: "/team", label: "팀" },
    },
  },
  {
    path: "/weekly",
    name: "weekly",
    component: weekly,
    meta: { title: "주간 보고", navKey: "/weekly" },
  },
  {
    path: "/weekly-report",
    redirect: "/weekly",
  },
  {
    path: "/login",
    name: "login",
    component: login,
    meta: { title: "로그인", public: true },
  },
  {
    path: "/users",
    redirect: "/login",
  },
  {
    path: "/settings",
    redirect: "/settings/teams",
  },
  {
    path: "/settings/users",
    redirect: "/settings/teams",
  },
  {
    path: "/settings/:tab",
    name: "settings",
    component: settings,
    meta: { title: "설정", navKey: "" },
  },
  {
    path: "/admin",
    redirect: "/admin/users",
  },
  {
    path: "/admin/:tab",
    name: "admin",
    component: admin,
    meta: { title: "관리", navKey: "", admin: true },
  },
  {
    path: "/weekly-detail/:id",
    name: "weekly-detail",
    component: weeklyDetail,
    meta: {
      title: "주간 상세",
      navKey: "/weekly",
      parent: { to: "/weekly", label: "주간 보고" },
    },
  },
  {
    path: "/report/:id",
    redirect: (to) => ({ name: "report-result", params: { id: to.params.id } }),
  },

  {
    path: "/project-timeline",
    name: "project-timeline",
    component: projectTimeline,
    meta: { title: "프로젝트 흐름", navKey: "/team", parent: { to: "/team", label: "팀" } },
  },
  {
    path: "/project-name",
    name: "project-name",
    redirect: "/settings/projects",
  },
  {
    path: "/team-select",
    name: "team-select",
    redirect: "/settings/teams",
  },
];
const router = createRouter({
  history: createWebHistory("/"),
  routes,
});


// 탭 제목은 화면 이름을 따른다. 화면이 따로 정하지 않으면 '일일보고'로 남아 주간 상세 등에서 헷갈렸다.
router.afterEach((to) => {
  document.title = to.meta?.title || "일일보고";
});

export default router;
