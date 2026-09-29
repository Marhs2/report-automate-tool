import { createRouter, createWebHistory } from "vue-router";
import report from "../components/report.vue";
import reportResult from "../components/report-result.vue";
import projectList from "../components/projects-list.vue";
import dashboard from "../components/dashboard.vue";
import compose from "../components/compose.vue";
import activities from "../components/user-activities.vue";
import weekly from "../components/weekly-report.vue";
import weeklyDetail from "../components/weekly-detail.vue";
import projectTimeline from "../components/project-timeline.vue";
import settings from "../components/settings.vue";
import admin from "../components/admin.vue";
import login from "../components/login.vue";

const routes = [
  {
    path: "/",
    name: "dashboard",
    component: dashboard,
    meta: {
      title: "내 현황",
      navKey: "/",
      action: { to: "/report", label: "보고서 작성" },
    },
  },
  {
    path: "/reports",
    name: "reports",
    component: projectList,
    meta: {
      title: "일일보고",
      navKey: "/reports",
    },
  },
  {
    path: "/compose/:id?",
    name: "compose",
    component: compose,
    meta: {
      title: "작성",
      navKey: "/reports",
      parent: { to: "/reports", label: "일일보고" },
    },
  },
  {
    path: "/report",
    name: "report",
    component: report,
    meta: {
      title: "보고서 작성",
      navKey: "/reports",
      parent: { to: "/reports", label: "일일보고" },
    },
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
      action: { to: "/report", label: "보고서 작성" },
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


export default router;
