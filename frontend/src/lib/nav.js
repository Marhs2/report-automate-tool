/** Primary sidebar destinations. App.vue imports this list. */
export const PRIMARY_NAV = [
    { to: "/", label: "일일보고", group: "작업" },
    { to: "/weekly", label: "주간 보고서", group: "작업" },
    { to: "/activities", label: "사용자 활동", group: "작업" },
    { to: "/project-timeline", label: "프로젝트 흐름", group: "작업" },
    { to: "/settings", label: "설정", group: "설정" },
];

/** Capability → live route path. Keep these reachable even when not in PRIMARY_NAV. */
export const CAPABILITIES = {
    dailyList: "/",
    writeReport: "/report",
    weekly: "/weekly",
    activities: "/activities",
    projectTimeline: "/project-timeline",
    projectNames: "/settings/projects",
    usersAndTeams: "/settings/users",
};

export const SETTINGS_TABS = [
    { id: "users", to: "/settings/users", label: "사용자" },
    { id: "teams", to: "/settings/teams", label: "부서" },
    { id: "projects", to: "/settings/projects", label: "프로젝트명" },
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

export function navGroupsFromPrimary() {
    const groups = [];
    const index = new Map();
    for (const item of PRIMARY_NAV) {
        let group = index.get(item.group);
        if (!group) {
            group = { label: item.group, items: [] };
            index.set(item.group, group);
            groups.push(group);
        }
        group.items.push(item);
    }
    return groups;
}
