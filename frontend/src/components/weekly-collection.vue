<script setup>
import { computed, onMounted, ref } from "vue";
import { saveAs } from "file-saver";
import { ChevronLeft, ChevronRight, Download } from "lucide-vue-next";
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
const ratioOf = (team) => (team.total ? Math.round((team.submitted / team.total) * 100) : 0);

const isThisWeek = computed(() => week.value === thisMonday());
/** 팀장이면 서버가 자기 부서만 돌려준다(scope: "team"). */
const isTeam = computed(() => status.value?.scope === "team");
const scopeLabel = computed(() => (isTeam.value ? status.value?.teams?.[0]?.name || "부서" : "전체"));
const missing = computed(() => (status.value ? status.value.total - status.value.submitted : 0));
const statusLine = computed(() => {
    if (!status.value) return "";
    if (status.value.complete) return `${isTeam.value ? "부서원이 모두" : "모든 부서가"} 주간보고를 냈어요.`;
    return `아직 ${missing.value}명이 주간보고를 내지 않았어요.`;
});

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
    <section class="collection" aria-labelledby="collection-title">
        <header class="collection-head">
            <h2 id="collection-title">{{ isTeam ? `${scopeLabel} 취합` : "전체 취합" }}</h2>
            <span v-if="status" class="collection-meta" :class="{ 'is-done': status.complete }">
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
        </header>

        <div v-if="loadError" class="collection-error" role="alert">
            <span>{{ loadError }}</span>
            <button type="button" class="btn btn-small" :disabled="isLoading" @click="load">다시 시도</button>
        </div>

        <div v-else-if="isLoading && !status" class="team-list" role="status" aria-label="취합 현황을 불러오는 중">
            <div v-for="n in 3" :key="n" class="team-row is-skeleton" aria-hidden="true">
                <span class="skel skel-name"></span>
                <span class="bar"></span>
                <span class="skel skel-count"></span>
            </div>
        </div>

        <template v-else-if="status">
            <p class="collection-status">{{ statusLine }}</p>

            <p v-if="!status.teams.length" class="collection-note">취합할 부서가 없어요.</p>

            <div v-else class="team-list">
                <div v-for="team in status.teams" :key="team.id ?? team.name" class="team-row">
                    <span class="team-name">{{ team.name }}</span>
                    <span class="bar" role="img" :aria-label="`${team.total}명 중 ${team.submitted}명 제출`">
                        <span :class="{ 'is-full': team.total > 0 && team.submitted >= team.total }" :style="{ width: `${ratioOf(team)}%` }"></span>
                    </span>
                    <span class="team-count" :class="{ 'is-short': team.submitted < team.total }">{{ team.submitted }}/{{ team.total }}명</span>
                    <span class="team-members">
                        <span
                            v-for="member in shownMembers(team)"
                            :key="member.id"
                            class="cat-tag"
                            :class="member.submitted ? 'is-done' : 'is-issue'"
                        >
                            {{ member.name }} {{ member.submitted ? "제출" : "미제출" }}
                        </span>
                        <button
                            v-if="team.members.length > MEMBER_PREVIEW"
                            type="button"
                            class="team-more"
                            :aria-expanded="isTeamOpen(team)"
                            @click="toggleTeam(team)"
                        >
                            {{ isTeamOpen(team) ? "접기" : `더보기 +${team.members.length - MEMBER_PREVIEW}명` }}
                        </button>
                    </span>
                </div>
            </div>

            <footer class="collection-foot">
                <button type="button" class="btn" :disabled="isMaking || !status.submitted" @click="makeDeck">
                    <Download :size="14" />
                    {{ isMaking ? "만드는 중" : status.complete ? `${scopeLabel} PPT 만들기` : "낸 사람만으로 PPT 만들기" }}
                </button>
            </footer>
        </template>
    </section>
</template>

<style scoped src="../styles/components/weekly-collection.css"></style>
