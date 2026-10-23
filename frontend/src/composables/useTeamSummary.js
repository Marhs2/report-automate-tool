import { computed, ref, watch } from "vue";
import useApi from "./useApi";
import { isAdmin, leaderTeamId } from "./useSession";
import { buildRows, periodDays, todayByTeam, todayIso } from "../lib/submissionGrid";

/**
 * 부서 오늘 제출 · 주간 취합. 팀장은 우리 부서, 관리자는 전체.
 * 내 현황(/me)과 팀 화면(/team)이 같은 값을 쓴다.
 */
export function useTeamSummary() {
    const { getUserActivities, getTeams, getUsers, getWeeklyCollection } = useApi();

    const role = computed(() => (isAdmin.value ? "admin" : leaderTeamId.value != null ? "leader" : "member"));
    const thisMonday = () => periodDays("week", todayIso())[0];

    /* ---- 부서 오늘 제출 ---------------------------------------------- */
    const teamToday = ref([]);
    const openTeams = ref([]);
    const toggleTeam = (key) => {
        openTeams.value = openTeams.value.includes(key) ? openTeams.value.filter((k) => k !== key) : [...openTeams.value, key];
    };
    const teamKey = (team) => String(team.teamId ?? "none");
    const loadTeamToday = async () => {
        const today = todayIso();
        const days = periodDays("week", today);
        try {
            const [activities, teams, users] = await Promise.all([
                getUserActivities(Number(days[0].slice(0, 4)), Number(days[0].slice(5, 7)), days[0], days.at(-1)),
                getTeams(),
                getUsers().catch(() => []),
            ]);
            const rows = buildRows(activities || [], days, {
                today,
                adminIds: new Set((users || []).filter((user) => user.is_admin).map((user) => String(user.id))),
                teamNames: Object.fromEntries((teams || []).map((team) => [String(team.id), team.team_name])),
                teamFilter: role.value === "leader" ? String(leaderTeamId.value) : "all",
            });
            // 안 낸 사람이 많은 부서부터.
            teamToday.value = todayByTeam(rows, days, today).sort((a, b) => b.pending.length - a.pending.length);
        } catch (error) {
            console.error("부서별 오늘 현황 조회 실패:", error);
            teamToday.value = [];
        }
    };
    const todayTotal = computed(() => {
        const done = teamToday.value.reduce((sum, team) => sum + team.done, 0);
        const total = teamToday.value.reduce((sum, team) => sum + team.total, 0);
        return { done, total, left: total - done };
    });
    const myTeam = computed(() => teamToday.value[0] || null);
    const pct = (done, total) => (total ? Math.round((done / total) * 100) : 0);

    /* ---- 주간 취합 ------------------------------------------------- */
    const collection = ref(null);
    const loadCollection = async () => {
        try {
            collection.value = await getWeeklyCollection(thisMonday());
        } catch {
            collection.value = null;
        }
    };
    /** 팀장이 보는 우리 부서 이번 주 주간보고(부서에 하나). */
    const myWeeklyTeam = computed(() =>
        (collection.value?.teams || []).find((team) => String(team.id) === String(leaderTeamId.value)) || null,
    );

    const loadRoleBlocks = () => {
        teamToday.value = [];
        collection.value = null;
        if (role.value === "member") return;
        loadTeamToday();
        loadCollection();
    };
    // 관리자 · 팀장 여부는 /me 응답 뒤에 정해진다. 그때 블록을 불러온다.
    watch(role, loadRoleBlocks, { immediate: true });

    return { role, teamToday, openTeams, toggleTeam, teamKey, todayTotal, myTeam, pct, collection, myWeeklyTeam };
}
