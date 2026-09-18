/** Paste scaffolds for /report. Time-table is omitted on purpose (community hate). */

export const PASTE_TEMPLATES = [
    {
        id: "basic",
        label: "기본 4칸",
        hint: "완료 · 진행 · 이슈 · 내일",
        body: `
프로젝트 명:

[완료]
-
[진행]
-
[이슈]
-
[내일]
-
`,
    },
    {
        id: "scrum",
        label: "어제/오늘/막힌 것",
        hint: "스크럼 3문장",
        body: `
프로젝트 명:
        
어제:
오늘:
막힌 것:
`,
    },
    {
        id: "office",
        label: "성과/이슈/내일/특이",
        hint: "한국 회사 4칸",
        body: `
프로젝트 명:

1. 성과/진행
2. 이슈 (원인 → 영향 → 조치)
3. 내일 계획 (마감 시각)
4. 특이/외근/휴가
`,
    },
    {
        id: "vs-yesterday",
        label: "전일 대비",
        hint: "계획 대비 실행",
        body: `
프로젝트 명:     

전일 계획 대비 실행:
금일:
내일:
`,
    },
    {
        id: "requests",
        label: "지시/건의",
        hint: "요청 칸 (이슈와 분리)",
        body: `
프로젝트 명:

지시/확인 부탁:
건의:
`,
    },
];

export function templateById(id) {
    return PASTE_TEMPLATES.find((item) => item.id === id) || null;
}

export function applyTemplate(_current, template) {
    return String(template?.body || "");
}
