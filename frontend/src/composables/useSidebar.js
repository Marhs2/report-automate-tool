import { ref, watch } from "vue";

const STORAGE_KEY = "sidebarCollapsed";

const readCollapsed = () => {
    try {
        return localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
        return false;
    }
};

const collapsed = ref(readCollapsed());
const drawerOpen = ref(false);

watch(collapsed, (value) => {
    try {
        localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
    } catch {
        /* 저장 실패는 무시한다 */
    }
});

export function useSidebar() {
    return {
        collapsed,
        toggleCollapsed: () => {
            collapsed.value = !collapsed.value;
        },
        drawerOpen,
        openDrawer: () => {
            drawerOpen.value = true;
        },
        closeDrawer: () => {
            drawerOpen.value = false;
        },
    };
}

export default useSidebar;
