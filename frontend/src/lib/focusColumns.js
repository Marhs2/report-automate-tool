/**
 * 다음 할 일 세 칸(다음 계획 · 열린 이슈 · 요청). /dashboard 응답의 focus.items를 편다.
 * 프로젝트가 둘 이상이면 줄마다 프로젝트 이름을 곁들인다.
 */
export function focusColumnsOf(focus) {
    const items = focus?.items || [];
    const many = new Set(items.map((item) => item.project)).size > 1;
    const column = (key) =>
        items.flatMap((item) => (item[key] || []).map((text) => ({ text, project: many ? item.project : "" })));
    return [
        { key: "next", title: "다음 계획", items: column("nextPlans") },
        { key: "issue", title: "열린 이슈", items: column("issues") },
        { key: "request", title: "요청", items: column("requests") },
    ];
}
