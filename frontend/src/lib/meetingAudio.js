/** 회의 녹음을 음성 인식 서버가 받는 모양(16kHz 모노 WAV 조각)으로 바꾼다. */

export const SAMPLE_RATE = 16000;
/** 5초 안팎마다 보내서 말하는 동안 글이 바로 붙게 한다. R2T2 서버는 max_model_len 8192라 긴 음성을 한 번에 못 받기도 한다. */
export const LIVE_SECONDS = 5;
/** 5초 앞뒤 1초 안에서 가장 조용한 곳을 자른다. 딱 5초에서 자르면 단어가 두 조각에 걸린다. */
export const LIVE_CUT_FROM = SAMPLE_RATE * (LIVE_SECONDS - 1);
export const LIVE_CUT_TO = SAMPLE_RATE * (LIVE_SECONDS + 1);
/**
 * 녹음 중 화면에 보이는 글은 5초 조각으로 빨리 받아 적고, 저장 · 요약에 쓰는 글은 5초 조각을 이어 붙인
 * 24~30초 조각으로 다시 받아 적는다. 시끄러운 방에서 5초 조각은 앞뒤 맥락이 없어 훨씬 많이 틀린다
 * (합성 회의 음성에 잡음을 섞어 잰 글자 오류율: 5초 37~43%, 30초 23~26%).
 */
export const FINAL_MIN_SAMPLES = SAMPLE_RATE * 24;
/** 조각 소리 크기를 이 RMS로 맞춘다. 멀리 있는 마이크처럼 작은 소리일수록 인식이 많이 틀린다. */
export const TARGET_RMS = 0.1;
/** 잡음만 있는 조각을 지나치게 키우지 않도록 올리는 배수에 한도를 둔다. */
export const MAX_GAIN = 20;
/** 정지 직후 남은 이 길이보다 짧은 꼬리는 보내지 않는다. 대부분 버튼 누르는 소리다. */
export const MIN_TAIL_SAMPLES = Math.floor(SAMPLE_RATE * 0.5);

/** 브라우저가 16kHz AudioContext를 거부했을 때를 위한 최근접 샘플 다운샘플. */
export function downsample(input, inRate, outRate = SAMPLE_RATE) {
    if (inRate === outRate) return input;
    const ratio = inRate / outRate;
    const out = new Float32Array(Math.floor(input.length / ratio));
    for (let i = 0; i < out.length; i++) out[i] = input[Math.floor(i * ratio)];
    return out;
}

export function concatFloat32(parts) {
    let length = 0;
    for (const part of parts) length += part.length;
    const out = new Float32Array(length);
    let offset = 0;
    for (const part of parts) {
        out.set(part, offset);
        offset += part.length;
    }
    return out;
}

/**
 * samples[from..to) 안에서 소리가 가장 작은 frame(기본 20ms) 구간의 시작 위치를 돌려준다.
 * 말 사이 쉬는 곳에서 자르려는 것이다. 범위가 모자라면 가능한 끝을 돌려준다.
 */
export function quietestCut(samples, from, to, frame = Math.floor(SAMPLE_RATE / 50)) {
    const end = Math.min(to, samples.length);
    if (end - from < frame) return Math.max(0, Math.min(end, samples.length));
    let best = from;
    let bestEnergy = Infinity;
    for (let start = from; start + frame <= end; start += frame) {
        let energy = 0;
        for (let i = start; i < start + frame; i++) energy += samples[i] * samples[i];
        if (energy < bestEnergy) {
            bestEnergy = energy;
            best = start;
        }
    }
    return best;
}

/** 조각 소리 크기를 TARGET_RMS 근처로 맞춘다. 줄이지는 않고, 올릴 때도 MAX_GAIN배까지만. */
export function normalizeGain(samples, target = TARGET_RMS, maxGain = MAX_GAIN) {
    const level = rms(samples);
    if (!level) return samples;
    const factor = Math.min(maxGain, target / level);
    if (factor <= 1) return samples;
    const out = new Float32Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
        out[i] = Math.max(-0.99, Math.min(0.99, samples[i] * factor));
    }
    return out;
}

export function encodeWav(samples, sampleRate = SAMPLE_RATE) {
    const buf = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buf);
    const ascii = (offset, text) => {
        for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
    };
    ascii(0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    ascii(8, "WAVE");
    ascii(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    ascii(36, "data");
    view.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return buf;
}

export function rms(samples) {
    if (!samples.length) return 0;
    let sum = 0;
    for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
    return Math.sqrt(sum / samples.length);
}

/** 조각 결과를 공백 하나로 잇는다. 사용자가 끝에 줄바꿈을 넣었으면 그대로 둔다. */
export function joinTranscript(current, next) {
    const add = String(next || "").trim();
    if (!add) return current;
    const text = String(current || "");
    if (!text.trim()) return add;
    return /\s$/.test(text) ? text + add : `${text} ${add}`;
}

/** 초를 3:07, 1:02:07 처럼 적는다. */
export function formatClock(totalSeconds) {
    const seconds = Math.max(0, Math.floor(totalSeconds));
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = String(seconds % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}
