import { createRouter, createWebHistory } from "vue-router";
import report from "../components/report.vue";
import reportResult from "../components/report-result.vue";
import projectList from "../components/projects-list.vue";

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
];
const router = createRouter({
  history: createWebHistory("/"),
  routes,
});

export default router;
