<script setup>
import { computed, onMounted, ref } from "vue";
import { saveAs } from "file-saver";
import { Check, ChevronLeft, ChevronRight, CircleAlert, Download } from "lucide-vue-next";
import useApi from "../composables/useApi";
import { useDialog } from "../composables/useDialog";

const { getWeeklyCollection, downloadWeeklyCollectionPptx } = useApi();
const { alert: showAlert, confirm: askConfirm } = useDialog();

const isoDate = (day) => {
    const month = String(day.getMonth() + 1).padStart(2, "0");
    const date = String(day.getDate()).padStart(2, "0");
    return `${day.getFullYear()}-${month}-${date}`;
};
const thisMonday = () => {
    const now = new Date();
    now.setDate(now.getDate() - ((now.getDay() + 6) % 7));
    return isoDate(now);
};

const week = ref(thisMonday());
const status = ref(null);
const isLoading = ref(false);
const isMaking = ref(false);
const loadError = ref("");

/** 부서마다 처음 보여 줄 사람 수. 안 낸 사람을 앞에 두고, 나머지는 '더보기'로 펼친다. */
const MEMBER_PREVIEW = 6;
const openTeams = ref([]);
const teamKey = (team) => String(team.id ?? team.name);
const isTeamOpen = (team) => openTeams.value.includes(teamKey(team));
const toggleTeam = (team) => {
    const key = teamKey(team);
    openTeams.value = isTeamOpen(team) ? openTeams.value.filter((k) => k !== key) : [...openTeams.value, key];
};
const sortedMembers = (team) => [...team.members].sort((a, b) => Number(a.submitted) - Number(b.submitted));
const shownMembers = (team) => (isTeamOpen(team) ? sortedMembers(team) : sortedMembers(team).slice(0, MEMBER_PREVIEW));

const isThisWeek = computed(() => week.value === thisMonday());
/** 팀장이면 서버가 자기 부서만 돌려준다(scope: "team"). */
const isTeam = computed(() => status.value?.scope === "team");
const scopeLabel = computed(() => (isTeam.value ? status.value?.teams?.[0]?.name || "부서" : "전체"));
const missing = computed(() => (status.value ? status.value.total - status.value.submitted : 0));

const load = async () => {
    isLoading.value = true;
    loadError.value = "";
    try {
        status.value = await getWeeklyCollection(week.value);
    } catch (error) {
        status.value = null;
        loadError.value = "취합 현황을 불러오지 못했습니다.";
        console.error("주간 취합 현황 조회 실패:", error);
    } finally {
        isLoading.value = false;
    }
};

const shift = (weeks) => {
    const [y, m, d] = week.value.split("-").map(Number);
    week.value = isoDate(new Date(y, m - 1, d + weeks * 7));
    load();
};
const resetWeek = () => {
    week.value = thisMonday();
    load();
};

const blobMessage = async (error, fallback) => {
    const data = error?.response?.data;
    if (data instanceof Blob) {
        try {
            const detail = JSON.parse(await data.text())?.detail;
            if (typeof detail === "string") return detail;
        } catch {
            return fallback;
        }
    }
    return fallback;
};

const makeDeck = async () => {
    if (!status.value?.submitted) return;
    const partial = !status.value.complete;
    if (partial && !(await askConfirm(`아직 ${missing.value}명이 내지 않았어요. 낸 ${status.value.submitted}명만으로 만들까요?`))) {
        return;
    }
    isMaking.value = true;
    try {
        const blob = await downloadWeeklyCollectionPptx(week.value, partial);
        saveAs(blob, `DXel 주간보고 ${scopeLabel.value} ${status.value.week.start}.pptx`);
    } catch (error) {
        showAlert(await blobMessage(error, "통합 PPT를 만들지 못했습니다."));
    } finally {
        isMaking.value = false;
    }
};

onMounted(load);
</script>

<template>
    <section class="group-block collection" aria-labelledby="collection-title">
        <div class="group-head collection-head">
            <h2 id="collection-title">{{ isTeam ? `${scopeLabel} 취합` : "전체 취합" }}</h2>
            <span v-if="status" class="group-meta" :class="{ 'is-done': status.complete }">
                {{ status.week.label }} · 주간보고 {{ status.submitted }}/{{ status.total }}명 제출
            </span>
            <div class="stepper" role="group" aria-label="취합할 주">
                <button type="button" aria-label="이전 주" :disabled="isLoading" @click="shift(-1)">
                    <ChevronLeft :size="16" />
                </button>
                <button type="button" class="stepper-reset" :disabled="isLoading || isThisWeek" @click="resetWeek">
                    이번 주
                </button>
                <button type="button" aria-label="다음 주" :disabled="isLoading" @click="shift(1)">
                    <ChevronRight :size="16" />
                </button>
            </div>
        </div>

        <p v-if="isLoading && !status" class="list-status" role="status">불러오는 중</p>
        <p v-else-if="loadError" class="list-status is-error" role="alert">{{ loadError }}</p>
        <template v-else-if="status">
            <p class="collection-note">
                {{ status.complete
                    ? `${isTeam ? "부서원이 모두" : "모든 부서가"} 주간보고를 냈어요. 한 파일로 합친 PPT를 만들 수 있어요.`
                    : `아직 ${missing}명이 주간보고를 내지 않았어요. 다 모이면 ${scopeLabel} PPT를 만들 수 있어요.` }}
            </p>
            <div class="group collection-teams">
                <div v-for="team in status.teams" :key="team.id ?? team.name" class="row collection-team">
                    <span class="row-main">
                        <span class="row-title">{{ team.name }}</span>
                        <span class="collection-members">
                            <span
                                v-for="member in shownMembers(team)"
                                :key="member.id"
                                class="cat-tag"
                                :class="member.submitted ? 'is-done' : 'is-issue'"
                            >
                                <Check v-if="member.submitted" :size="12" :stroke-width="2.5" aria-hidden="true" />
                                <CircleAlert v-else :size="12" aria-hidden="true" />
                                {{ member.name }} {{ member.submitted ? "제출" : "미제출" }}
                            </span>
                            <button
                                v-if="team.members.length > MEMBER_PREVIEW"
                                type="button"
                                class="collection-more"
                                :aria-expanded="isTeamOpen(team)"
                                @click="toggleTeam(team)"
                            >
                                {{ isTeamOpen(team) ? "접기" : `더보기 +${team.members.length - MEMBER_PREVIEW}명` }}
                            </button>
                        </span>
                    </span>
                    <span class="row-end group-meta">{{ team.submitted }}/{{ team.total }}</span>
                </div>
            </div>
            <div class="collection-actions">
                <button
                    type="button"
                    class="btn"
                    :class="status.complete ? 'btn-primary' : ''"
                    :disabled="isMaking || !status.submitted"
                    @click="makeDeck"
                >
                    <Download :size="14" />
                    {{ isMaking ? "만드는 중" : status.complete ? `${scopeLabel} PPT 만들기` : "낸 사람만으로 PPT 만들기" }}
                </button>
            </div>
        </template>
    </section>
</template>

<style scoped src="../styles/components/weekly-collection.css"></style>
