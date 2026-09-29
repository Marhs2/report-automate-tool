/** "완료: 요약 기능 개발" 같은 업무 기록 한 줄을 분류 표시와 본문으로 나눈다. */

const TONES = {
    완료: "success",
    진행: "info",
    이슈: "warning",
    요청: "request",
    다음: "muted",
    추후: "muted",
    후속: "warning",
    결정: "neutral",
    담당: "neutral",
};

export function splitHistoryLine(line) {
    const text = String(line ?? "").trim();
    const match = text.match(/^([^:\s]{1,4}):\s*(.+)$/s);
    if (!match || !TONES[match[1]]) return { tag: "", tone: "", text };
    return { tag: match[1], tone: TONES[match[1]], text: match[2].trim() };
}
