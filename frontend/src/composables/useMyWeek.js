import { computed, ref } from "vue";
import useApi from "./useApi";
import { selectedUserId } from "./useSelectedUser";
import { isAdmin } from "./useSession";
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
    const { getUserActivities, getReportDraft, getHolidays } = useApi();
    const iso = todayString();
    const week = weekDays(iso);
    if (!week.length) return;
    const [year, month] = iso.split("-").map(Number);
    let saved = new Set();
    let holidays = {};
    try {
        const years = [...new Set([week[0].date.slice(0, 4), week[4].date.slice(0, 4)])];
        const [rows, ...holidayLists] = await Promise.all([
            getUserActivities(year, month, week[0].date, week[4].date),
            ...years.map((y) => getHolidays(Number(y))),
        ]);
        saved = savedDatesOf(rows, memberId);
        holidays = Object.fromEntries(
            holidayLists.flat().filter((row) => row?.date).map((row) => [row.date, row.name]),
        );
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
    days.value = weekStatus(week, saved, iso, holidays);
    // 이번 주 보고를 한 번도 안 쓴 관리자는 보고 대상이 아니다. 배지로 재촉하지 않는다.
    const quietAdmin = Boolean(isAdmin.value) && saved.size === 0 && !hasDraft;
    state.value = todayState({
        saved: saved.has(iso),
        hasDraft,
        weekend: weekday === 0 || weekday === 6 || Boolean(holidays[iso]) || quietAdmin,
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
