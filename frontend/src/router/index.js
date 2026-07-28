import { createRouter, createWebHistory } from "vue-router";
import report from "../components/report.vue";
import reportResult from "../components/report-result.vue";
import projectList from "../components/projects-list.vue";
import activities from "../components/user-activities.vue";
import weekly from "../components/weekly-report.vue";
import users from "../components/user-select.vue";
import weeklyDetail from "../components/weekly-detail.vue";

const routes = [
  {
    path: "/",
    name: "",
    component: projectList,
  },
  {
    path: "/report",
    name: "report",
    component: report,
  },
  {
    path: "/report-result",
    name: "report-result",
    component: reportResult,
  },
  {
    path: "/activities",
    name: "activities",
    component: activities,
  },
  {
    path: "/weekly",
    name: "weekly",
    component: weekly,
  },
  {
    path: "/users",
    name: "users",
    component: users,
  },
  {
    path: "/weekly-detail/:id",
    name: "weekly-detail",
    component: weeklyDetail,
  },
];
const router = createRouter({
  history: createWebHistory("/"),
  routes,
});

export default router;
