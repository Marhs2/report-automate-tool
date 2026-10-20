import { ref } from "vue";
import { useLocalStorage } from "@vueuse/core";

export const sessionToken = useLocalStorage("report-sessionToken", "");
export const isAdmin = useLocalStorage("report-isAdmin", false);
/** 팀장이면 그 부서 id. 서버가 판단하므로 저장하지 않고 /me로 매번 채운다. */
export const leaderTeamId = ref(null);

export const hasSession = () => String(sessionToken.value || "").trim() !== "";
