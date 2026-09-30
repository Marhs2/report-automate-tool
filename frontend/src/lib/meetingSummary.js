/** 요약 결과를 회의록 폼에 넣는 규칙. 컴포넌트는 결과만 받아서 대입한다. */

export const blankFollowup = () => ({ task: "", owner: "", due: "" });

/**
 * 폼에 넣을 값을 돌려준다. 제목은 사용자가 적어 둔 것을 지키고, 비어 있을 때만 요약 제목을 쓴다.
 * 후속 할 일이 없으면 빈 줄 하나를 둬서 폼 모양이 그대로 남게 한다.
 */
export function summaryToForm(form, summary) {
    const followups = (summary?.followups || [])
        .map((row) => ({
            task: String(row?.task || "").trim(),
            owner: String(row?.owner || "").trim(),
            due: String(row?.due || "").trim(),
        }))
        .filter((row) => row.task);
    return {
        title: String(form?.title || "").trim() ? form.title : String(summary?.title || "").trim(),
        agenda: String(summary?.agenda || "").trim(),
        decisions: String(summary?.decisions || "").trim(),
        followups: followups.length ? followups : [blankFollowup()],
    };
}

/** 채운 뒤 보여 줄 한 줄. 무엇이 채워졌는지 적는다. */
export function summaryNote(values) {
    const filled = [];
    if (values.agenda) filled.push("안건");
    if (values.decisions) filled.push("결정");
    const tasks = values.followups.filter((row) => row.task).length;
    if (tasks) filled.push(`후속 할 일 ${tasks}개`);
    if (!filled.length) return "녹취록에서 안건, 결정, 할 일을 찾지 못했습니다. 녹취록을 확인해 주세요.";
    // 안건 · 결정은 받침이 있어 "을", "N개"는 받침이 없어 "를".
    const particle = tasks ? "를" : "을";
    return `${filled.join(", ")}${particle} 채웠습니다. 확인하고 저장하세요.`;
}
