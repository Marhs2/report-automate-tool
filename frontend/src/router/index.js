import { createRouter, createWebHistory } from "vue-router";
// 화면마다 따로 나눠 불러온다. 한 번에 묶으면 첫 화면이 모든 화면 코드를 다 받을 때까지 기다린다.
const reportResult = () => import("../components/report-result.vue");
const projectList = () => import("../components/projects-list.vue");
// 첫 화면(내 현황)은 나누지 않는다. 나누면 본 코드 다음에 한 번 더 받아야 해서 가장 큰 글자가 늦게 뜬다.
import dashboard from "../components/dashboard.vue";
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
    name: "dashboard",
    component: dashboard,
    meta: {
      title: "내 현황",
      navKey: "/",
    },
  },
  {
    path: "/reports",
    name: "reports",
    component: projectList,
    meta: {
      title: "일일보고",
      navKey: "/reports",
      action: { to: "/compose?kind=daily", label: "일일보고 쓰기" },
    },
  },
  {
    path: "/compose/:id?",
    name: "compose",
    component: compose,
    meta: {
      title: "작성",
      navKey: "/compose",
    },
  },
  {
    path: "/report",
    redirect: { path: "/compose", query: { kind: "daily" } },
  },
  {
    path: "/report-result/:id?",
    name: "report-result",
    component: reportResult,
    meta: {
      title: "일일보고 상세",
      navKey: "/reports",
      parent: { to: "/reports", label: "일일보고" },
    },
  },
  {
    path: "/activities",
    name: "activities",
    component: activities,
    meta: {
      title: "사용자 활동",
      navKey: "/activities",
    },
  },
  {
    path: "/weekly",
    name: "weekly",
    component: weekly,
    meta: { title: "주간 보고서", navKey: "/weekly" },
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
    meta: { title: "설정", navKey: "/settings" },
  },
  {
    path: "/admin",
    redirect: "/admin/users",
  },
  {
    path: "/admin/:tab",
    name: "admin",
    component: admin,
    meta: { title: "관리", navKey: "/admin", admin: true },
  },
  {
    path: "/weekly-detail/:id",
    name: "weekly-detail",
    component: weeklyDetail,
    meta: {
      title: "주간 상세",
      navKey: "/weekly",
      parent: { to: "/weekly", label: "주간 보고서" },
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
    meta: { title: "프로젝트 흐름", navKey: "/project-timeline" },
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
