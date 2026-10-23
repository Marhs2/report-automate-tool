import { ref } from "vue";

/** "system" | "light" | "dark". 저장값이 없으면 OS를 따른다. 첫 적용은 index.html이 먼저 한다. */
const KEY = "report-theme";
const media = window.matchMedia("(prefers-color-scheme: dark)");
export const themeChoice = ref(localStorage.getItem(KEY) || "system");

const apply = () => {
    const dark = themeChoice.value === "dark" || (themeChoice.value === "system" && media.matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
};

media.addEventListener("change", apply);

export function setTheme(choice) {
    themeChoice.value = choice;
    if (choice === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, choice);
    apply();
}

export const THEME_OPTIONS = [
    { id: "system", label: "시스템" },
    { id: "light", label: "라이트" },
    { id: "dark", label: "다크" },
];
