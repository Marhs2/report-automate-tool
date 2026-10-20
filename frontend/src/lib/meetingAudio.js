/**
 * 회의 녹음을 5분 안팎의 조각으로 자르고 받아 적기 서버(Qwen3-ASR)가 받는 WAV(16kHz 모노 16비트)로 바꾼다.
 * 돌아온 발화는 화면용 글로 잇는다.
 */

export const SAMPLE_RATE = 16000;
/** 조각 하나의 길이. 이만큼 쌓이면 받아 적기 서버로 보낸다. */
export const CHUNK_SECONDS = 300;
/** 말 한가운데를 자르지 않도록, 조각 끝 이 길이 안에서 가장 조용한 곳을 찾아 자른다. */
export const CUT_WINDOW_SECONDS = 10;
/** 조용한 곳을 찾는 단위(0.1초). */
const CUT_FRAME = SAMPLE_RATE / 10;
/** 정지할 때 남은 소리가 이보다 짧으면 보내지 않는다(서버도 0.5초 미만은 버린다). */
export const MIN_CHUNK_SECONDS = 0.5;

/** 브라우저가 16kHz AudioContext를 거부했을 때를 위한 최근접 샘플 다운샘플. */
export function downsample(input, inRate, outRate = SAMPLE_RATE) {
    if (inRate === outRate) return input;
    const ratio = inRate / outRate;
    const out = new Float32Array(Math.floor(input.length / ratio));
    for (let i = 0; i < out.length; i++) out[i] = input[Math.floor(i * ratio)];
    return out;
}

/** 자동 소리 키우기의 목표 크기(RMS). 앞서 R2T2 벤치마크에서 조각을 이 크기로 맞추면 덜 틀렸다. */
export const TARGET_RMS = 0.1;
/** 잡음까지 지나치게 키우지 않도록 올리는 배수에 한도를 둔다(26dB). */
export const MAX_GAIN = 20;
/** 이보다 작은 소리는 말이 아닌 것으로 보고 크기 판단에 쓰지 않는다(-50dBFS). */
export const SPEECH_GATE = 0.003;
/** 한 번(0.25초 안팎)에 올리는 배수의 한도. 약 +1dB라 갑자기 커지지 않는다. */
export const GAIN_RISE = 1.12;

/**
 * 멀리 앉은 사람 목소리처럼 작은 소리를 키우는 자동 증폭.
 * 말하는 동안의 크기를 천천히 따라가며 TARGET_RMS에 맞추고, 조용할 때는 배수를 그대로 둔다(잡음을 키우지 않게).
 * 커질 때는 바로 줄이고, 그래도 넘치는 곳은 부드럽게 눌러(soft clip) 깨지지 않게 한다.
 * process(chunk)는 새 Float32Array를 돌려준다. 녹음 한 번에 하나를 만들어 쓴다.
 */
export function createAutoGain({ target = TARGET_RMS, maxGain = MAX_GAIN, gate = SPEECH_GATE, rise = GAIN_RISE } = {}) {
    let level = 0;
    let gain = 1;
    return {
        get gain() {
            return gain;
        },
        process(chunk) {
            const now = rms(chunk);
            if (now > gate) level = level ? level * 0.8 + now * 0.2 : now;
            let next = gain;
            if (level) {
                const wanted = Math.max(1, Math.min(maxGain, target / level));
                next = wanted > gain ? Math.min(wanted, gain * rise) : wanted;
            }
            // 이번 조각 안에서 배수를 서서히 바꿔 뚝 끊기는 소리가 나지 않게 한다.
            const out = new Float32Array(chunk.length);
            const step = chunk.length ? (next - gain) / chunk.length : 0;
            for (let i = 0; i < chunk.length; i++) out[i] = softClip(chunk[i] * (gain + step * i));
            gain = next;
            return out;
        },
    };
}

/** 0.9를 넘는 소리를 0.999 안쪽으로 부드럽게 누른다. */
export function softClip(x) {
    const a = Math.abs(x);
    if (a <= 0.9) return x;
    return Math.sign(x) * (0.9 + 0.099 * Math.tanh((a - 0.9) / 0.1));
}

/** -1~1 실수를 16비트 정수로. WAV에 이 값을 담는다(실수의 절반 크기). */
export function toInt16(samples) {
    const out = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return out;
}

export function rms(samples) {
    if (!samples.length) return 0;
    let sum = 0;
    for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
    return Math.sqrt(sum / samples.length);
}

/** samples[from, to)에서 가장 조용한 0.1초 구간의 가운데 위치. 같으면 뒤쪽을 고른다(조각이 덜 짧아진다). 구간이 짧으면 to. */
export function quietestCut(samples, from, to, frame = CUT_FRAME) {
    let best = to;
    let bestLevel = Infinity;
    for (let at = Math.max(0, from); at + frame <= to; at += frame) {
        const level = rms(samples.subarray(at, at + frame));
        if (level <= bestLevel) {
            bestLevel = level;
            best = at + Math.floor(frame / 2);
        }
    }
    return best;
}

/**
 * 녹음을 chunkSeconds 안팎의 조각으로 자른다. push(소리)는 다 찬 조각들을, flush()는 남은 소리를 돌려준다.
 * 조각은 {samples, offset}이고 offset은 녹음 처음부터 센 조각 시작 시각(초)이다.
 */
export function createChunker({ chunkSeconds = CHUNK_SECONDS, windowSeconds = CUT_WINDOW_SECONDS, sampleRate = SAMPLE_RATE } = {}) {
    const chunkSamples = Math.round(chunkSeconds * sampleRate);
    const windowSamples = Math.min(chunkSamples, Math.round(windowSeconds * sampleRate));
    let pieces = [];
    let size = 0;
    let start = 0;

    const take = () => {
        const all = new Float32Array(size);
        let at = 0;
        for (const piece of pieces) {
            all.set(piece, at);
            at += piece.length;
        }
        return all;
    };

    return {
        push(samples) {
            pieces.push(samples);
            size += samples.length;
            const out = [];
            while (size >= chunkSamples) {
                const all = take();
                const cut = quietestCut(all, chunkSamples - windowSamples, chunkSamples, Math.max(1, Math.round(sampleRate / 10)));
                out.push({ samples: all.slice(0, cut), offset: start / sampleRate });
                start += cut;
                pieces = [all.slice(cut)];
                size = all.length - cut;
            }
            return out;
        },
        flush() {
            const all = take();
            const chunk = { samples: all, offset: start / sampleRate };
            start += all.length;
            pieces = [];
            size = 0;
            return all.length >= MIN_CHUNK_SECONDS * sampleRate ? chunk : null;
        },
    };
}

/** -1~1 실수 소리를 16비트 모노 WAV 파일 내용으로. */
export function encodeWav(samples, sampleRate = SAMPLE_RATE) {
    const pcm = toInt16(samples);
    const buffer = new ArrayBuffer(44 + pcm.length * 2);
    const view = new DataView(buffer);
    const text = (at, value) => {
        for (let i = 0; i < value.length; i++) view.setUint8(at + i, value.charCodeAt(i));
    };
    text(0, "RIFF");
    view.setUint32(4, 36 + pcm.length * 2, true);
    text(8, "WAVE");
    text(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    text(36, "data");
    view.setUint32(40, pcm.length * 2, true);
    new Int16Array(buffer, 44).set(pcm);
    return buffer;
}

/** 조각 결과를 공백 하나로 잇는다. 사용자가 끝에 줄바꿈을 넣었으면 그대로 둔다. */
export function joinTranscript(current, next) {
    const add = String(next || "").trim();
    if (!add) return current;
    const text = String(current || "");
    if (!text.trim()) return add;
    return /\s$/.test(text) ? text + add : `${text} ${add}`;
}

/** 받아 적은 발화들을 한 덩어리 글로. */
export function segmentsText(segments = []) {
    return segments.reduce((all, segment) => joinTranscript(all, segment.text), "");
}

/** 초를 3:07, 1:02:07 처럼 적는다. */
export function formatClock(totalSeconds) {
    const seconds = Math.max(0, Math.floor(totalSeconds));
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = String(seconds % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}
