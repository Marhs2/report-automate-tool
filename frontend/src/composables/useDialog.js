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

let active = null;
let unlockTimer = 0;

const resetLabels = () => {
    title.value = "";
    help.value = "";
    confirmLabel.value = "확인";
    cancelLabel.value = "취소";
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
    locked.value = true;
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

const close = (result) => {
    if (!open.value || locked.value) return;
    window.clearTimeout(unlockTimer);
    open.value = false;
    locked.value = false;
    resetLabels();
    const current = active;
    active = null;
    current?.resolve(result);
    queueMicrotask(pump);
};

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
        alert,
        confirm,
        accept: () => close(true),
        reject: () => close(false),
    };
}
