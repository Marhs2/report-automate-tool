import { ref, watch } from "vue";
import { useRoute } from "vue-router";

/** 라우트 meta는 고정이라 같은 경로도 읽는 중과 고치는 중 이름이 달라야 한다.
 *  경로가 바뀌면 덮어쓴 제목을 비운다. */
export const pageTitleOverride = ref("");
export const pageParentOverride = ref(null);

export function usePageMeta() {
    const route = useRoute();

    watch(
        () => route.fullPath,
        () => {
            pageTitleOverride.value = "";
            pageParentOverride.value = null;
        },
    );

    const setPageMeta = ({ title, parent } = {}) => {
        if (title !== undefined) pageTitleOverride.value = title || "";
        if (parent !== undefined) pageParentOverride.value = parent || null;
    };

    return { setPageMeta, pageTitleOverride, pageParentOverride };
}
