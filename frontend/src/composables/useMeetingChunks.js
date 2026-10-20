import { computed, onBeforeUnmount, shallowRef } from "vue";
import useApi from "./useApi";
import { SAMPLE_RATE, createChunker, encodeWav, segmentsText } from "../lib/meetingAudio";
import { errorMessage } from "../lib/errorMessage";

/** 조각 하나를 받아 적다 실패하면 이만큼 쉬고 한 번 더 해 본다. */
const RETRY_DELAY_MS = 3000;

/**
 * 회의 녹음을 5분 조각으로 받아 적는다(백엔드 /meeting/transcribe → 받아 적기 서버 Qwen3-ASR).
 *
 * 녹음하는 동안 push(소리)로 받은 소리가 5분 차면 조용한 곳에서 잘라 WAV로 보낸다. 조각은 하나씩 차례로
 * 보낸다(GPU 하나가 차례로 받아 적는다). 녹음을 이어서 다시 하면 앞 녹음 뒤에 붙는다.
 * finish()는 남은 소리까지 보내고 모든 조각이 끝나면 풀린다.
 * 실패한 조각의 소리는 버리지 않는다. retryFailed()로 다시 보낼 수 있다.
 *
 * onText(전체 녹취록)는 조각이 받아 적힐 때마다 회의 순서대로 이은 글로 부른다.
 */
export function useMeetingChunks({ onText }) {
    const { transcribeMeetingChunk } = useApi();
    // 조각마다 {offset, seconds, wav, status: "waiting" | "sending" | "done" | "failed", segments}
    const parts = shallowRef([]);
    let chunker = createChunker();
    // 앞서 녹음한 길이(초). 녹음을 다시 시작해도 조각 시각이 겹치지 않게 한다.
    let recordedBefore = 0;
    let recordedNow = 0;
    // reset()마다 올라간다. 늦게 온 결과가 새 기록에 붙지 않게 한다.
    let generation = 0;
    let running = null;
    let drained = [];

    const pending = computed(() => parts.value.filter((part) => part.status === "waiting" || part.status === "sending").length);
    const failed = computed(() => parts.value.filter((part) => part.status === "failed"));
    const text = computed(() =>
        segmentsText(parts.value.filter((part) => part.status === "done").flatMap((part) => part.segments)),
    );

    const update = (part, fields) => {
        parts.value = parts.value.map((item) => (item === part ? Object.assign(part, fields) : item));
    };

    const sendOne = async (part, mine) => {
        for (let attempt = 0; attempt < 2; attempt++) {
            if (attempt) await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
            if (mine !== generation) return;
            try {
                const result = await transcribeMeetingChunk(part.wav, part.offset);
                if (mine !== generation) return;
                update(part, { status: "done", segments: result.segments || [], wav: null, error: "" });
                onText(text.value);
                return;
            } catch (error) {
                if (mine !== generation) return;
                part.error = errorMessage(error, "받아 적지 못했습니다.");
            }
        }
        update(part, { status: "failed" });
    };

    const run = async () => {
        const mine = generation;
        let next;
        while (mine === generation && (next = parts.value.find((part) => part.status === "waiting"))) {
            update(next, { status: "sending" });
            await sendOne(next, mine);
        }
        if (mine !== generation) return;
        running = null;
        const waiting = drained;
        drained = [];
        waiting.forEach((resolve) => resolve());
    };

    const kick = () => {
        if (!running) running = run();
    };

    const enqueue = (chunk) => {
        parts.value = [
            ...parts.value,
            {
                offset: recordedBefore + chunk.offset,
                seconds: chunk.samples.length / SAMPLE_RATE,
                wav: encodeWav(chunk.samples),
                status: "waiting",
                segments: [],
                error: "",
            },
        ];
        kick();
    };

    /** 녹음한 소리(16kHz Float32Array)를 받는다. */
    const push = (samples) => {
        recordedNow += samples.length / SAMPLE_RATE;
        chunker.push(samples).forEach(enqueue);
    };

    const idle = () =>
        new Promise((resolve) => {
            if (!running) resolve();
            else drained.push(resolve);
        });

    /** 녹음을 멈췄다. 남은 소리를 보내고, 실패했던 조각도 한 번 더 보낸 뒤 모두 끝나면 풀린다. */
    const finish = async () => {
        const rest = chunker.flush();
        if (rest) enqueue(rest);
        chunker = createChunker();
        recordedBefore += recordedNow;
        recordedNow = 0;
        retryFailed();
        await idle();
    };

    const retryFailed = () => {
        if (!failed.value.length) return;
        parts.value = parts.value.map((part) => (part.status === "failed" ? { ...part, status: "waiting" } : part));
        kick();
    };

    /** 실패한 조각을 버리고 받아 적은 데까지만 쓴다. */
    const dropFailed = () => {
        parts.value = parts.value.filter((part) => part.status !== "failed");
    };

    const reset = () => {
        generation += 1;
        running = null;
        const waiting = drained;
        drained = [];
        waiting.forEach((resolve) => resolve());
        parts.value = [];
        chunker = createChunker();
        recordedBefore = 0;
        recordedNow = 0;
    };

    onBeforeUnmount(reset);

    return { parts, pending, failed, text, push, finish, retryFailed, dropFailed, reset };
}
