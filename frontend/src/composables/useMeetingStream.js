import { onBeforeUnmount, ref } from "vue";
import useApi from "./useApi";

/**
 * 회의 녹음 스트림 하나 (백엔드 /meeting/stream → 받아 적기 서버 Qwen3-ASR).
 *
 * 서버 → 브라우저: ready · partial {utt, text}(말하는 중, 바뀔 수 있음) · final {utt, start, end, text}(확정)
 *                  · polishing(사내 용어로 교정 중) · done {segments, duration} · error {message}
 * 브라우저 → 서버: (로그인 토큰은 useApi가 먼저 보낸다) 16kHz 16비트 PCM 바이너리 … 끝에 "end"
 *
 * phase: idle → connecting → live → finishing("end"를 보냄) → polishing → idle
 * 녹음 중 끊기면 onError(message, 지금까지 확정된 발화)를 부른다. 받은 글은 버리지 않는다.
 */
export function useMeetingStream({ onDone, onError }) {
    const { openMeetingStream } = useApi();
    const phase = ref("idle");
    const segments = ref([]);
    const partial = ref("");
    let socket = null;

    const close = () => {
        const current = socket;
        socket = null;
        phase.value = "idle";
        try { current?.close(); } catch {}
    };

    /** 연결하고 받아 적기 서버가 준비되면 끝난다. */
    const open = () =>
        new Promise((resolve, reject) => {
            close();
            segments.value = [];
            partial.value = "";
            phase.value = "connecting";
            const mine = openMeetingStream();
            socket = mine;
            let ready = false;

            const fail = (message) => {
                if (mine !== socket) return;
                // 말하는 중이던 발화도 버리지 않는다. 확정 전이라 조금 틀릴 수 있다.
                const kept = partial.value ? [...segments.value, { text: partial.value }] : [...segments.value];
                close();
                if (ready) onError(message, kept);
                else reject(new Error(message));
            };

            mine.onmessage = (event) => {
                if (mine !== socket) return;
                let msg;
                try {
                    msg = JSON.parse(event.data);
                } catch {
                    return;
                }
                switch (msg.type) {
                    case "ready":
                        ready = true;
                        phase.value = "live";
                        resolve();
                        break;
                    case "partial":
                        partial.value = msg.text || "";
                        break;
                    case "final":
                        segments.value = [...segments.value, { start: msg.start, end: msg.end, text: msg.text }];
                        partial.value = "";
                        break;
                    case "polishing":
                        phase.value = "polishing";
                        break;
                    case "done":
                        close();
                        onDone(msg);
                        break;
                    case "error":
                        fail(msg.message || "음성 인식 서버 오류");
                        break;
                    default:
                        break;
                }
            };
            mine.onclose = () => {
                fail(ready ? "음성 인식 서버와 연결이 끊겼습니다." : "음성 인식 서버에 연결하지 못했습니다.");
            };
        });

    const send = (pcm) => {
        if (phase.value === "live" && socket?.readyState === WebSocket.OPEN) socket.send(pcm);
    };

    /** 녹음을 멈췄다. 남은 소리를 마저 받아 적고 done을 보내 달라고 한다. */
    const finish = () => {
        if (phase.value !== "live" || !socket) return;
        phase.value = "finishing";
        socket.send("end");
    };

    onBeforeUnmount(close);

    return { phase, segments, partial, open, send, finish, close };
}
