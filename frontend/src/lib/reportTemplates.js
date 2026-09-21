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

/** 형식 넣기.
 *  mode "replace": 쓴 내용을 형식으로 바꾼다(빈 칸에서 시작할 때 기대하는 동작).
 *  mode "append": 쓴 내용 아래에 형식을 덧붙인다.
 *  이미 쓴 글이 있는데 말없이 덧붙이면 저장된 하루가 망가진다. 호출하는 쪽에서 먼저 물어본다. */
export function applyTemplate(current, template, mode = "append") {
    const body = String(template?.body || "");
    const typed = String(current || "").replace(/\s+$/, "");
    if (mode === "replace") return body;
    return typed ? `${typed}\n\n${body}` : body;
}

export function hasTypedContent(current) {
    return String(current || "").trim().length > 0;
}
