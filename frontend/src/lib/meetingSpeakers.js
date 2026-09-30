/** 화자 분리 결과(구간 목록)를 사람이 읽는 녹취록과 이름 붙이기 화면용 목록으로 바꾼다. */

/** 이만큼 넘게 여러 명이 겹쳐 말한 구간은 받아 적은 글이 틀렸을 수 있다. */
export const OVERLAP_WARN = 0.3;

export function speakerLabel(speaker) {
    return `화자 ${Number(speaker) + 1}`;
}

/** 이름을 붙였으면 이름, 아니면 "화자 N". */
export function speakerName(speaker, names = {}) {
    const name = String(names[speaker] ?? "").trim();
    return name || speakerLabel(speaker);
}

/**
 * 이름 붙이기 화면에 보일 화자 목록. 말한 시간과, 누구인지 알아보기 쉬운 첫 문장을 함께 준다.
 * 첫 문장은 "네"처럼 짧은 대답을 건너뛰고 8자 넘는 첫 말을 고른다.
 */
export function speakerSummaries(segments = []) {
    const bySpeaker = new Map();
    for (const segment of segments) {
        const entry = bySpeaker.get(segment.speaker) || { speaker: segment.speaker, seconds: 0, count: 0, sample: "" };
        entry.seconds += Math.max(0, (segment.end || 0) - (segment.start || 0));
        entry.count += 1;
        if (!entry.sample || (entry.sample.length <= 8 && segment.text.length > 8)) entry.sample = segment.text;
        bySpeaker.set(segment.speaker, entry);
    }
    return [...bySpeaker.values()]
        .sort((a, b) => a.speaker - b.speaker)
        .map((entry) => ({ ...entry, label: speakerLabel(entry.speaker), seconds: Math.round(entry.seconds) }));
}

/** "이름: 말" 줄로 된 녹취록. 같은 사람이 이어서 말한 구간은 한 줄로 잇는다. */
export function labeledTranscript(segments = [], names = {}) {
    const lines = [];
    for (const segment of segments) {
        const text = String(segment.text || "").trim();
        if (!text) continue;
        const last = lines[lines.length - 1];
        if (last && last.speaker === segment.speaker) {
            last.text = `${last.text} ${text}`;
        } else {
            lines.push({ speaker: segment.speaker, text });
        }
    }
    return lines.map((line) => `${speakerName(line.speaker, names)}: ${line.text}`).join("\n");
}

/** 이름을 붙인 사람들로 참석자 칸을 채운다. 비운 화자는 넣지 않는다. */
export function attendeesFromNames(names = {}) {
    const seen = new Set();
    for (const value of Object.values(names)) {
        const name = String(value ?? "").trim();
        if (name) seen.add(name);
    }
    return [...seen].join(", ");
}

/** 여러 명이 겹쳐 말한 구간 수. 정리한 뒤 한 줄로 알려 준다. */
export function overlapCount(segments = [], threshold = OVERLAP_WARN) {
    return segments.filter((segment) => (segment.overlap || 0) >= threshold).length;
}

/** 초를 "3분 12초", "45초"로 적는다. */
export function spokenDuration(seconds) {
    const total = Math.max(0, Math.round(seconds));
    const m = Math.floor(total / 60);
    const s = total % 60;
    if (!m) return `${s}초`;
    return s ? `${m}분 ${s}초` : `${m}분`;
}
