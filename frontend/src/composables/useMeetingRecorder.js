import { onBeforeUnmount, ref } from "vue";
import {
    FINAL_MIN_SAMPLES,
    LIVE_CUT_FROM,
    LIVE_CUT_TO,
    MIN_TAIL_SAMPLES,
    SAMPLE_RATE,
    concatFloat32,
    downsample,
    encodeWav,
    normalizeGain,
    quietestCut,
    rms,
} from "../lib/meetingAudio";

function micError(error) {
    if (error?.name === "NotAllowedError") {
        return new Error("마이크 권한이 막혀 있습니다. 주소창의 사이트 설정에서 마이크를 허용한 뒤 다시 눌러 주세요.");
    }
    if (error?.name === "NotFoundError") {
        return new Error("연결된 마이크를 찾지 못했습니다.");
    }
    return new Error(`마이크를 열지 못했습니다: ${error?.message || error}`);
}

const wavBlob = (samples) => new Blob([encodeWav(normalizeGain(samples))], { type: "audio/wav" });

/**
 * 마이크를 16kHz로 녹음해 두 가지 조각을 넘긴다.
 * - onDraft(blob, start): 5초 안팎 조각. 4~6초 사이 가장 조용한 곳에서 자른다. 화면에 바로 보여 줄 용도.
 * - onFinal(blob, start, end): 초안 조각을 이어 붙인 24~30초 조각. 경계가 초안과 같아서 조용한 곳에서 끊긴다.
 *   맥락이 길어 덜 틀리므로 저장 · 요약에는 이것을 쓴다.
 * 정지하면 남은 꼬리도 넘긴다. 화면을 떠나면 마이크를 닫는다.
 */
export function useMeetingRecorder({ onDraft, onFinal }) {
    const recording = ref(false);
    const starting = ref(false);
    const seconds = ref(0);
    const level = ref(0);

    let ctx, src, proc, stream;
    let parts = [];
    let partSamples = 0;
    let totalSamples = 0;
    let segmentStart = 0;
    let finalParts = [];
    let finalSamples = 0;
    let finalStart = 0;
    // 시작 도중 정지하면 올라간다. 늦게 열린 마이크를 닫는 데 쓴다.
    let session = 0;

    const flushFinal = () => {
        if (!finalSamples) return;
        const samples = concatFloat32(finalParts);
        const start = finalStart;
        finalStart += samples.length / SAMPLE_RATE;
        finalParts = [];
        finalSamples = 0;
        if (samples.length >= MIN_TAIL_SAMPLES) onFinal(wavBlob(samples), start, finalStart);
    };

    const send = (samples) => {
        const start = segmentStart;
        segmentStart += samples.length / SAMPLE_RATE;
        if (samples.length >= MIN_TAIL_SAMPLES) onDraft(wavBlob(samples), start);
        finalParts.push(samples);
        finalSamples += samples.length;
        if (finalSamples >= FINAL_MIN_SAMPLES) flushFinal();
    };

    // 6초가 모이면 4~6초 사이 가장 조용한 곳까지 보내고, 나머지는 다음 조각 앞머리로 남긴다.
    const flush = (force) => {
        if (!partSamples || (!force && partSamples < LIVE_CUT_TO)) return;
        const samples = concatFloat32(parts);
        if (force) {
            parts = [];
            partSamples = 0;
            send(samples);
            return;
        }
        const cut = quietestCut(samples, LIVE_CUT_FROM, LIVE_CUT_TO);
        const rest = samples.slice(cut);
        parts = [rest];
        partSamples = rest.length;
        send(samples.subarray(0, cut));
    };

    const release = () => {
        try { proc?.disconnect(); } catch {}
        try { src?.disconnect(); } catch {}
        try { if (ctx && ctx.state !== "closed") ctx.close(); } catch {}
        try { stream?.getTracks().forEach((track) => track.stop()); } catch {}
        ctx = src = proc = stream = undefined;
        level.value = 0;
    };

    const start = async () => {
        if (recording.value || starting.value) return;
        if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) {
            throw new Error("이 주소에서는 마이크를 쓸 수 없습니다. https 주소나 localhost로 열어 주세요.");
        }
        const mine = ++session;
        starting.value = true;
        let mic;
        try {
            mic = await navigator.mediaDevices.getUserMedia({
                audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
            });
        } catch (error) {
            throw micError(error);
        } finally {
            starting.value = false;
        }
        if (mine !== session) {
            mic.getTracks().forEach((track) => track.stop());
            return;
        }
        stream = mic;
        parts = [];
        partSamples = 0;
        totalSamples = 0;
        segmentStart = 0;
        finalParts = [];
        finalSamples = 0;
        finalStart = 0;
        seconds.value = 0;

        ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
        src = ctx.createMediaStreamSource(stream);
        proc = ctx.createScriptProcessor(4096, 1, 1);
        proc.onaudioprocess = (event) => {
            if (!recording.value) return;
            const chunk = downsample(event.inputBuffer.getChannelData(0), ctx.sampleRate);
            parts.push(Float32Array.from(chunk));
            partSamples += chunk.length;
            totalSamples += chunk.length;
            seconds.value = totalSamples / SAMPLE_RATE;
            level.value = Math.min(1, rms(chunk) * 4);
            flush(false);
        };
        // ScriptProcessor는 destination에 이어져야 돈다. 스피커로는 소리를 내지 않는다.
        const mute = ctx.createGain();
        mute.gain.value = 0;
        src.connect(proc);
        proc.connect(mute);
        mute.connect(ctx.destination);
        recording.value = true;
    };

    const stop = () => {
        session += 1;
        const wasRecording = recording.value;
        recording.value = false;
        release();
        if (wasRecording) {
            flush(true);
            flushFinal();
        }
    };

    onBeforeUnmount(stop);

    return { recording, starting, seconds, level, start, stop };
}
