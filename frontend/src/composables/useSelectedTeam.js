import { ref, watch } from "vue";
import useApi from "./useApi";
import { selectedUserId } from "./useSelectedUser";

const { getTeamByMemberId } = useApi();

/** 선택된 사용자의 members.team_id (부서 id) — DB에서 조회 */
export const selectedTeamId = ref(null);

watch(
  selectedUserId,
  async (memberId) => {
    if (memberId == null || memberId === "") {
      selectedTeamId.value = null;
      return;
    }
    try {
      const team = await getTeamByMemberId(memberId);
      selectedTeamId.value = team?.id ?? null;
    } catch (error) {
      console.error("부서 id 조회 실패:", error);
      selectedTeamId.value = null;
    }
  },
  { immediate: true },
);
