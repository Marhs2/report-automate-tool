import { ref } from "vue";

const toasts = ref([]);
let nextId = 1;

const dismiss = (id) => {
    toasts.value = toasts.value.filter((item) => item.id !== id);
};

const show = (message, type = "info") => {
    const text = String(message || "").trim();
    if (!text) return;
    const id = nextId++;
    toasts.value.push({ id, message: text, type });
    window.setTimeout(() => dismiss(id), 3200);
};

export function useToast() {
    return {
        toasts,
        show,
        success: (message) => show(message, "success"),
        error: (message) => show(message, "error"),
        dismiss,
    };
}
