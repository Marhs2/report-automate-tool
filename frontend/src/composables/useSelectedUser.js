import { useLocalStorage } from "@vueuse/core";

export const selectedUserId = useLocalStorage("report-selectedUser", null);
