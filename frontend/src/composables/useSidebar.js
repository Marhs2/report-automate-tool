import { computed, ref, watch } from "vue";

const STORAGE_KEY = "sidebarCollapsed";
const NARROW_QUERY = "(max-width: 860px)";

const readCollapsed = () => {
    try {
        return localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
        return false;
    }
};

const getNarrowQuery = () => {
    try {
        if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
            return null;
        }
        return window.matchMedia(NARROW_QUERY);
    } catch {
        return null;
    }
};

const narrowQuery = getNarrowQuery();

const collapsed = ref(readCollapsed());
const drawerOpen = ref(false);
const isNarrow = ref(narrowQuery ? narrowQuery.matches : false);

// 좁은 화면(드로어 상태)에서는 사용자의 접힘 설정을 무시하고 항상 전체 메뉴를 보여준다.
// `collapsed`는 설정값 그대로 유지하고, 화면 표시에는 `collapsedEffective`를 쓴다.
const collapsedEffective = computed(() => collapsed.value && !isNarrow.value);

if (narrowQuery) {
    const onNarrowChange = (event) => {
        isNarrow.value = event.matches;
    };
    if (typeof narrowQuery.addEventListener === "function") {
        narrowQuery.addEventListener("change", onNarrowChange);
    } else if (typeof narrowQuery.addListener === "function") {
        narrowQuery.addListener(onNarrowChange);
    }
}

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
        collapsedEffective,
        isNarrow,
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
