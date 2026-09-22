export const PRIMARY_NAV = [
    { to: "/", label: "일일보고", shortLabel: "일일", group: "작업" },
    { to: "/weekly", label: "주간 보고서", shortLabel: "주간", group: "작업" },
    { to: "/activities", label: "사용자 활동", shortLabel: "활동", group: "작업" },
    { to: "/project-timeline", label: "프로젝트 흐름", shortLabel: "흐름", group: "작업" },
    { to: "/settings", label: "설정", shortLabel: "설정", group: "설정" },
];

/** Capability → live route path. Keep these reachable even when not in PRIMARY_NAV. */
export const CAPABILITIES = {
    dailyList: "/",
    writeReport: "/report",
    weekly: "/weekly",
    activities: "/activities",
    projectTimeline: "/project-timeline",
    projectNames: "/settings/projects",
    usersAndTeams: "/settings/teams",
    admin: "/admin/users",
};

export const SETTINGS_TABS = [
    { id: "teams", to: "/settings/teams", label: "내 부서" },
    { id: "projects", to: "/settings/projects", label: "프로젝트명" },
];

export const ADMIN_TABS = [
    { id: "users", to: "/admin/users", label: "사용자" },
    { id: "teams", to: "/admin/teams", label: "부서" },
];

export const LIVE_ROUTE_PATHS = [
    "/",
    "/report",
    "/report-result/:id?",
    "/activities",
    "/weekly",
    "/weekly-detail/:id",
    "/project-timeline",
    "/settings",
    "/settings/users",
    "/settings/teams",
    "/settings/projects",
    "/admin",
    "/admin/users",
    "/admin/teams",
    "/login",
    "/users",
    "/team-select",
    "/project-name",
];

export function primaryNavCount() {
    return PRIMARY_NAV.length;
}

export function capabilityPaths() {
    return Object.values(CAPABILITIES);
}
