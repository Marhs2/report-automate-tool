import { onBeforeUnmount, ref } from "vue";
import { SAMPLE_RATE, createAutoGain, downsample, rms, toInt16 } from "../lib/meetingAudio";

function micError(error) {
    if (error?.name === "NotAllowedError") {
        return new Error("마이크 권한이 막혀 있습니다. 주소창의 사이트 설정에서 마이크를 허용한 뒤 다시 눌러 주세요.");
    }
    if (error?.name === "NotFoundError") {
        return new Error("연결된 마이크를 찾지 못했습니다.");
    }
    return new Error(`마이크를 열지 못했습니다: ${error?.message || error}`);
}

/**
 * 마이크를 16kHz로 녹음해 onAudio(Int16Array)로 계속 넘긴다(0.25초 안팎마다).
 * 작은 목소리는 자동으로 키운다(createAutoGain). 막대도 키운 소리 크기를 보여 준다.
 * 발화를 끊는 일은 받아 적기 서버가 한다. 화면을 떠나면 마이크를 닫는다.
 */
export function useMeetingRecorder({ onAudio }) {
    const recording = ref(false);
    const starting = ref(false);
    const seconds = ref(0);
    const level = ref(0);

    let ctx, src, proc, stream;
    let totalSamples = 0;
    let autoGain = createAutoGain();
    // 시작 도중 정지하면 올라간다. 늦게 열린 마이크를 닫는 데 쓴다.
    let session = 0;

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
        totalSamples = 0;
        seconds.value = 0;
        autoGain = createAutoGain();

        ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
        src = ctx.createMediaStreamSource(stream);
        proc = ctx.createScriptProcessor(4096, 1, 1);
        proc.onaudioprocess = (event) => {
            if (!recording.value) return;
            const chunk = autoGain.process(downsample(event.inputBuffer.getChannelData(0), ctx.sampleRate));
            totalSamples += chunk.length;
            seconds.value = totalSamples / SAMPLE_RATE;
            level.value = Math.min(1, rms(chunk) * 4);
            onAudio(toInt16(chunk));
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
        recording.value = false;
        release();
    };

    onBeforeUnmount(stop);

    return { recording, starting, seconds, level, start, stop };
}
