/** 팀 화면: 하루치 팀원 목록. 누가 냈는지, 무엇을 썼는지를 한 줄씩. */
import { parseReportJson } from "./reportSummary.js";

/** 보고 JSON 칸 → 분류 태그(KindTag kind). 화면에 보이는 순서대로. */
const FIELDS = [
    ["completedTasks", "done", "완료"],
    ["inProgressTasks", "progress", "진행"],
    ["issues", "issue", "이슈"],
    ["requests", "request", "요청"],
    ["nextPlans", "next", "다음"],
];

const textOf = (value) =>
    String(value && typeof value === "object" ? value.content ?? "" : value ?? "").trim();

/** 한 보고의 줄을 프로젝트 순서대로 펼친다. */
export function reportLines(parsedJson) {
    const lines = [];
    for (const project of parseReportJson(parsedJson).projects || []) {
        if (!project || typeof project !== "object") continue;
        const name = String(project.projectName || "").trim();
        for (const [field, kind, label] of FIELDS) {
            const list = field === "nextPlans" && !project.nextPlans?.length ? project.nextWeekPlans : project[field];
            for (const item of Array.isArray(list) ? list : []) {
                const text = textOf(item);
                if (text) lines.push({ project: name, kind, label, text });
            }
        }
    }
    return lines;
}

/**
 * 그날의 팀원 목록.
 * status: submitted(제출) · waiting(오늘인데 아직) · missing(지난 날인데 없음) · upcoming(아직 오지 않은 날).
 * 관리자 계정은 보고 대상이 아니라 뺀다(사용자 활동 표와 같은 기준).
 * 순서: 제출한 사람(이슈 있는 사람 먼저) → 안 낸 사람. 같은 묶음은 이름순.
 */
export function teamDay({ reports = [], users = [], teams = [], date, today }) {
    const teamName = new Map((teams || []).map((team) => [String(team.id), team.team_name]));
    const byMember = new Map();
    for (const report of reports || []) {
        if (String(report?.report_date) === String(date)) byMember.set(String(report.member_id), report);
    }
    const people = (users || [])
        .filter((user) => !user?.is_admin)
        .map((user) => {
            const report = byMember.get(String(user.id)) || null;
            const lines = report ? reportLines(report.parsed_json) : [];
            const projects = [...new Set(lines.map((line) => line.project).filter(Boolean))];
            let status = "submitted";
            if (!report) {
                if (date === today) status = "waiting";
                else if (date < today) status = "missing";
                else status = "upcoming";
            }
            return {
                memberId: user.id,
                name: user.name || `사용자 ${user.id}`,
                team: teamName.get(String(user.team_id)) || "",
                reportId: report?.id ?? null,
                status,
                lines,
                projects,
                issueCount: lines.filter((line) => line.kind === "issue").length,
            };
        });
    const rank = (person) => (person.status === "submitted" ? (person.issueCount ? 0 : 1) : 2);
    people.sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name, "ko"));
    return {
        people,
        total: people.length,
        submitted: people.filter((person) => person.status === "submitted").length,
        notYet: people.filter((person) => person.status === "waiting" || person.status === "missing"),
    };
}

/** 하루 앞뒤로. 주말은 건너뛴다(보고는 평일에만 쓴다). */
export function shiftWorkday(dateStr, step) {
    const [year, month, day] = String(dateStr).split("-").map(Number);
    const next = new Date(year, month - 1, day);
    do {
        next.setDate(next.getDate() + step);
    } while (next.getDay() === 0 || next.getDay() === 6);
    const pad = (value) => String(value).padStart(2, "0");
    return `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}`;
}
