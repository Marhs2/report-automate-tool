import { useLocalStorage } from "@vueuse/core";

export const sessionToken = useLocalStorage("report-sessionToken", "");
export const isAdmin = useLocalStorage("report-isAdmin", false);

export const hasSession = () => String(sessionToken.value || "").trim() !== "";
