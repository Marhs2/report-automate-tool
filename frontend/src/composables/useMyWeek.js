import { computed, ref } from "vue";
import useApi from "./useApi";
import { selectedUserId } from "./useSelectedUser";
import { todayString } from "../lib/dateScope";
import { savedDatesOf, todayState, weekDays, weekStatus } from "../lib/weekStatus";

/** 내 이번 주 제출 현황. 사이드바·하단 탭·내 현황이 같은 값을 본다. */
const days = ref([]);
const today = ref("");
const state = ref(null);
let pending = null;

const refresh = async () => {
    const memberId = selectedUserId.value;
    if (memberId == null || memberId === "") {
        days.value = [];
        state.value = null;
        return;
    }
    const { getUserActivities, getReportDraft } = useApi();
    const iso = todayString();
    const week = weekDays(iso);
    if (!week.length) return;
    const [year, month] = iso.split("-").map(Number);
    let saved = new Set();
    try {
        const rows = await getUserActivities(year, month, week[0].date, week[4].date);
        saved = savedDatesOf(rows, memberId);
    } catch {
        return;
    }
    let hasDraft = false;
    if (!saved.has(iso)) {
        try {
            const draft = await getReportDraft(memberId, iso);
            hasDraft = Boolean(String(draft?.raw_text || "").trim());
        } catch {
            hasDraft = false;
        }
    }
    const weekday = new Date().getDay();
    today.value = iso;
    days.value = weekStatus(week, saved, iso);
    state.value = todayState({
        saved: saved.has(iso),
        hasDraft,
        weekend: weekday === 0 || weekday === 6,
    });
};

export function useMyWeek() {
    const refreshMyWeek = () => {
        if (!pending) pending = refresh().finally(() => { pending = null; });
        return pending;
    };
    return {
        weekDays: days,
        today,
        todayState: state,
        todayMissing: computed(() => state.value === "missing"),
        refreshMyWeek,
    };
}
