import { ref, watch } from "vue";
import { useRoute } from "vue-router";

/** 라우터 meta는 고정값이라 "분석 결과"처럼 상황에 안 맞는 이름이 그대로 남는다.
 *  화면이 스스로 제목과 상위 위치를 바꿀 수 있게 덮어쓰기 슬롯을 둔다.
 *  경로가 바뀌면 자동으로 비워서 다음 화면에 새지 않게 한다. */
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
