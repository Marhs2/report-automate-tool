/** 위쪽(모바일은 아래쪽) 탭. 하루의 순서대로 세 곳뿐이다. 나머지 화면은 지우지 않고 아래 링크 묶음에서 한 번에 간다. */
export const PRIMARY_NAV = [
    { to: "/", label: "오늘", navKey: "/" },
    { to: "/team", label: "팀", navKey: "/team" },
    { to: "/weekly", label: "주간", navKey: "/weekly" },
];

/** 모바일 하단 탭. 위쪽 탭과 같은 세 곳. */
export const MOBILE_TABS = PRIMARY_NAV.map((item) => ({
    id: item.navKey === "/" ? "today" : item.navKey.slice(1),
    to: item.to,
    label: item.label,
    navKeys: [item.navKey],
}));

/** 작성 화면의 선택지. 일일보고는 "오늘" 화면이 곧 작성 화면이다(kind=daily는 /로 보낸다). */
export const COMPOSE_CHOICES = [
    { id: "meeting", to: "/compose?kind=meeting", label: "회의록" },
    { id: "daily", to: "/compose?kind=daily", label: "일일보고" },
    { id: "sales", to: "/compose?kind=sales", label: "영업보고" },
];

/** 팀 화면에서 한 번 눌러 가는 곳. 예전 메뉴의 일일보고 목록 · 사용자 활동 · 프로젝트 흐름. */
export const TEAM_LINKS = [
    { to: "/reports", label: "검색 · 필터", hint: "모든 일일보고를 검색하고 프로젝트로 거르기" },
    { to: "/activities", label: "제출 기록", hint: "사람별 주 · 월 제출 표" },
    { to: "/project-timeline", label: "프로젝트 흐름", hint: "프로젝트별 타임라인" },
];

/** 오른쪽 위 이름 동그라미를 누르면 나오는 메뉴. */
export const ACCOUNT_LINKS = [
    { to: "/me", label: "내 현황", hint: "이번 주 · 내 프로젝트" },
    { to: "/settings", label: "설정", hint: "내 부서 · 프로젝트명 · 비밀번호" },
];

/** 예전 하단 "더보기" 시트의 항목. 지금은 팀 화면 링크와 이름 메뉴로 나뉘었다. */
export const MORE_LINKS = [...TEAM_LINKS, ...ACCOUNT_LINKS];

/** Capability → live route path. Keep these reachable even when not in PRIMARY_NAV. */
export const CAPABILITIES = {
    today: "/",
    dashboard: "/me",
    team: "/team",
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
    "/me",
    "/team",
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
