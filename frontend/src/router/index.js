import { createRouter, createWebHistory } from "vue-router";
import report from "../components/report.vue";
import reportResult from "../components/report-result.vue";
import projectList from "../components/projects-list.vue";
import activities from "../components/user-activities.vue";
import weekly from "../components/weekly-report.vue";
import users from "../components/user-select.vue";
import weeklyDetail from "../components/weekly-detail.vue";
import projectTimeline from "../components/project-timeline.vue";
import projectName from "../components/project-name.vue";
import teamSelect from "../components/team-select.vue";

const routes = [
  {
    path: "/",
    name: "",
    component: projectList,
    meta: {
      title: "일일보고",
      navKey: "/",
      action: { to: "/report", label: "보고서 작성" },
    },
  },
  {
    path: "/report",
    name: "report",
    component: report,
    meta: { title: "보고서 작성", navKey: "/report" },
  },
  {
    path: "/report-result/:id?",
    name: "report-result",
    component: reportResult,
    meta: {
      title: "분석 결과",
      navKey: "/",
      parent: { to: "/", label: "일일보고" },
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
    path: "/users",
    name: "users",
    component: users,
    meta: { title: "사용자 선택", navKey: "/users" },
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
    component: projectName,
    meta: { title: "프로젝트명 관리", navKey: "/project-name" },
  },
  {
    path: "/team-select",
    name: "team-select",
    component: teamSelect,
    meta: { title: "팀 선택", navKey: "/team-select" },
  },
];
const router = createRouter({
  history: createWebHistory("/"),
  routes,
});


export default router;
