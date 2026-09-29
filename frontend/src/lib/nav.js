export const PRIMARY_NAV = [
    { to: "/", label: "내 현황", shortLabel: "현황", group: "작업" },
    { to: "/reports", label: "일일보고", shortLabel: "일일", group: "작업" },
    { to: "/compose", label: "작성", shortLabel: "작성", group: "작업" },
    { to: "/weekly", label: "주간 보고서", shortLabel: "주간", group: "작업" },
    { to: "/activities", label: "사용자 활동", shortLabel: "활동", group: "작업" },
    { to: "/project-timeline", label: "프로젝트 흐름", shortLabel: "흐름", group: "작업" },
    { to: "/settings", label: "설정", shortLabel: "설정", group: "설정" },
];

/** 모바일 하단 탭. 다섯 칸을 넘기지 않는다. 작성에서 일일·회의·영업으로 바로 간다. */
export const MOBILE_TABS = [
    { id: "home", to: "/", label: "현황", navKeys: ["/"] },
    { id: "daily", to: "/reports", label: "일일", navKeys: ["/reports", "/report"] },
    { id: "write", to: "/compose", label: "작성", navKeys: ["/compose"] },
    { id: "weekly", to: "/weekly", label: "주간", navKeys: ["/weekly"] },
    { id: "more", sheet: "more", label: "더보기", navKeys: ["/activities", "/project-timeline", "/settings", "/admin"] },
];

/** 작성 화면의 선택지. */
export const COMPOSE_CHOICES = [
    { id: "daily", to: "/compose?kind=daily", label: "일일보고", hint: "원문을 붙여 넣으면 AI가 프로젝트별로 정리" },
    { id: "meeting", to: "/compose?kind=meeting", label: "회의록", hint: "안건 · 결정 · 후속 할 일" },
    { id: "sales", to: "/compose?kind=sales", label: "영업보고", hint: "담당자 · 진행사항 · 추후 진행" },
];

/** 더보기 시트. 하단 탭에 못 들어간 화면. */
export const MORE_LINKS = [
    { to: "/activities", label: "사용자 활동", hint: "월 달력 · 제출과 미제출" },
    { to: "/project-timeline", label: "프로젝트 흐름", hint: "프로젝트별 타임라인" },
    { to: "/settings", label: "설정", hint: "내 부서 · 프로젝트명" },
];

/** Capability → live route path. Keep these reachable even when not in PRIMARY_NAV. */
export const CAPABILITIES = {
    dashboard: "/",
    dailyList: "/reports",
    writeReport: "/report",
    compose: "/compose",
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
    "/reports",
    "/compose",
    "/compose/:id",
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
