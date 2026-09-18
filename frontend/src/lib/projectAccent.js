export const PROJECT_ACCENT_COUNT = 6;

export function projectAccentIndex(index) {
    const n = Number(index);
    if (!Number.isInteger(n) || n < 0) return 0;
    return n % PROJECT_ACCENT_COUNT;
}

export function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function phrasesOf(project) {
    const phrases = [];
    const push = (value) => {
        const text =
            value && typeof value === "object"
                ? String(value.content ?? "").trim()
                : String(value ?? "").trim();
        if (text.length >= 2) phrases.push(text);
    };
    push(project?.projectName);
    for (const key of [
        "completedTasks",
        "inProgressTasks",
        "issues",
        "requests",
        "nextPlans",
        "nextWeekPlans",
    ]) {
        for (const item of project?.[key] || []) push(item);
    }
    return phrases;
}

export function highlightRangesByProject(raw, projects = []) {
    const text = String(raw ?? "");
    const candidates = [];
    projects.forEach((project, index) => {
        const accent = projectAccentIndex(index);
        for (const phrase of phrasesOf(project)) {
            candidates.push({ phrase, accent });
        }
    });
    candidates.sort(
        (left, right) =>
            right.phrase.length - left.phrase.length ||
            left.accent - right.accent,
    );
    const ranges = [];
    for (const { phrase, accent } of candidates) {
        let from = 0;
        for (;;) {
            const start = text.indexOf(phrase, from);
            if (start === -1) break;
            const end = start + phrase.length;
            const overlaps = ranges.some(([s, e]) => start < e && s < end);
            if (!overlaps) ranges.push([start, end, accent]);
            from = end;
        }
    }
    ranges.sort((left, right) => left[0] - right[0]);
    return ranges;
}

export function highlightedRawHtml(raw, projects = [], { on = true } = {}) {
    const text = String(raw ?? "");
    if (!on) return escapeHtml(text);
    const ranges = highlightRangesByProject(text, projects);
    let html = "";
    let cursor = 0;
    for (const [start, end, accent] of ranges) {
        html += escapeHtml(text.slice(cursor, start));
        html += `<mark class="raw-hit" data-accent="${accent}">${escapeHtml(
            text.slice(start, end),
        )}</mark>`;
        cursor = end;
    }
    return html + escapeHtml(text.slice(cursor));
}
