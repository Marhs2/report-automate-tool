import { computed, ref, watch } from "vue";
import useApi from "./useApi";
import { selectedUserId } from "./useSelectedUser";
import { isAdmin, leaderTeamId } from "./useSession";
import { periodDays, todayIso } from "../lib/submissionGrid";

const WEEKLY = {
    none: { label: "안 만듦", tone: "muted", action: "주간보고 만들기", to: "/weekly" },
    /** 팀원: 부서 주간보고는 팀장이 만든다. */
    waiting: { label: "팀장 작성 전", tone: "muted", action: "주간 보고서 보기", to: "/weekly" },
    draft: { label: "초안", tone: "warning", action: "이어서 만들기", to: "/weekly-detail/new" },
    saved: { label: "저장됨", tone: "success", action: "주간보고 열기", to: "" },
};

/** 이번 주 부서 주간보고: 안 만듦(팀원은 팀장 작성 전) · 초안 · 저장됨. 내 현황(/me)과 오늘 화면(/)이 같이 쓴다. */
export function useMyWeekly() {
    const { getWeeklyReport } = useApi();
    const thisMonday = () => periodDays("week", todayIso())[0];
    const myWeekly = ref(null);

    const weeklyState = computed(() => {
        if (myWeekly.value) return "saved";
        if (!isAdmin.value && leaderTeamId.value == null) return "waiting";
        try {
            const draft = JSON.parse(sessionStorage.getItem("weeklyDraft") || "null");
            const monday = thisMonday();
            const friday = periodDays("week", monday).at(-1);
            if ((draft?.selects || []).some((day) => day >= monday && day <= friday)) return "draft";
        } catch {
            return "none";
        }
        return "none";
    });
    const weeklyCard = computed(() => {
        const base = WEEKLY[weeklyState.value];
        return { ...base, to: base.to || `/weekly-detail/${myWeekly.value?.id}` };
    });
    /** 목 · 금에는 만들 때라 버튼을 크게, 그 밖의 날은 한 줄로 조용히. */
    const weeklyEmph = computed(() => [4, 5].includes(new Date().getDay()));

    const loadMyWeekly = async () => {
        myWeekly.value = null;
        if (selectedUserId.value == null || selectedUserId.value === "") return;
        try {
            const rows = await getWeeklyReport(selectedUserId.value);
            const monday = thisMonday();
            const friday = periodDays("week", monday).at(-1);
            myWeekly.value =
                (rows || [])
                    .filter((row) => (row.selectedDate || []).some((day) => day >= monday && day <= friday))
                    .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)))[0] || null;
        } catch {
            myWeekly.value = null;
        }
    };
    watch(selectedUserId, loadMyWeekly, { immediate: true });

    return { myWeekly, weeklyState, weeklyCard, weeklyEmph };
}
