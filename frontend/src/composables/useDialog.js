import { nextTick, ref } from "vue";

const queue = [];
const open = ref(false);
const locked = ref(false);
const mode = ref("alert");
const title = ref("");
const message = ref("");
const help = ref("");
const confirmLabel = ref("확인");
const cancelLabel = ref("취소");
/** 되돌릴 수 없는 확인(덮어쓰기·삭제)은 확인 버튼을 위험 색으로 칠한다. */
const danger = ref(false);

let active = null;
let unlockTimer = 0;
/** performance.now() when the current dialog opened. Key events stamped earlier
 *  belong to whatever opened it, not to the dialog. */
let openedAt = 0;

const resetLabels = () => {
    title.value = "";
    help.value = "";
    confirmLabel.value = "확인";
    cancelLabel.value = "취소";
    danger.value = false;
};

const pump = async () => {
    if (open.value || queue.length === 0) return;
    active = queue.shift();
    mode.value = active.mode;
    message.value = active.message;
    title.value = active.title || "";
    help.value = active.help || "";
    confirmLabel.value = active.confirmLabel || "확인";
    cancelLabel.value = active.cancelLabel || "취소";
    danger.value = Boolean(active.danger);
    locked.value = true;
    openedAt = performance.now();
    open.value = true;
    await nextTick();
    window.clearTimeout(unlockTimer);
    // The click/Enter that opened the dialog must not hit 확인.
    unlockTimer = window.setTimeout(() => {
        locked.value = false;
    }, 400);
};

const enqueue = (item) => {
    queue.push(item);
    queueMicrotask(pump);
};

/** Buttons wait out the lock so a double click can't confirm by accident.
 *  The keyboard path filters by event time instead (see isFreshKey), so a quick
 *  Enter right after the dialog appears still closes it on the first press. */
const close = (result, { fromKey = false } = {}) => {
    if (!open.value || (locked.value && !fromKey)) return;
    window.clearTimeout(unlockTimer);
    open.value = false;
    locked.value = false;
    resetLabels();
    const current = active;
    active = null;
    current?.resolve(result);
    queueMicrotask(pump);
};

/** A key press that started after the dialog opened and isn't auto-repeat. */
const isFreshKey = (event) => !event.repeat && event.timeStamp >= openedAt;

export function useDialog() {
    const alert = (text, options = {}) =>
        new Promise((resolve) => {
            enqueue({
                mode: "alert",
                message: String(text ?? ""),
                title: options.title || "",
                help: options.help || "",
                confirmLabel: options.confirmLabel || "확인",
                resolve: () => resolve(),
            });
        });

    const confirm = (text, options = {}) =>
        new Promise((resolve) => {
            enqueue({
                mode: "confirm",
                message: String(text ?? ""),
                title: options.title || "",
                help: options.help || "",
                confirmLabel: options.confirmLabel || "확인",
                cancelLabel: options.cancelLabel || "취소",
                danger: Boolean(options.danger),
                resolve,
            });
        });

    return {
        open,
        locked,
        mode,
        title,
        message,
        help,
        confirmLabel,
        cancelLabel,
        danger,
        alert,
        confirm,
        accept: () => close(true),
        reject: () => close(false),
        isFreshKey,
        acceptKey: () => close(true, { fromKey: true }),
        rejectKey: () => close(false, { fromKey: true }),
    };
}
