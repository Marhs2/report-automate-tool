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

const isThisWeek = computed(() => week.value === thisMonday());
/** 팀장이면 서버가 자기 부서만 돌려준다(scope: "team"). */
const isTeam = computed(() => status.value?.scope === "team");
const scopeLabel = computed(() => (isTeam.value ? status.value?.teams?.[0]?.name || "부서" : "전체"));
const missing = computed(() => (status.value ? status.value.total - status.value.submitted : 0));
const statusLine = computed(() => {
    if (!status.value) return "";
    if (status.value.complete) return "모든 부서가 주간보고를 냈어요.";
    return `아직 ${missing.value}개 부서가 주간보고를 내지 않았어요.`;
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
    if (partial && !(await askConfirm(`아직 ${missing.value}개 부서가 내지 않았어요. 낸 ${status.value.submitted}개 부서만으로 만들까요?`))) {
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
                {{ status.week.label }} · {{ status.submitted }}/{{ status.total }}개 부서 제출
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
                <component
                    :is="team.submitted ? 'router-link' : 'div'"
                    v-for="team in status.teams"
                    :key="team.id ?? team.name"
                    class="team-row"
                    :class="{ 'is-missing': !team.submitted }"
                    v-bind="team.submitted ? { to: `/weekly-detail/${team.weeklyId}` } : {}"
                >
                    <span class="team-name">{{ team.name }}</span>
                    <span class="team-who">{{ team.submitted ? `${team.authorName} 작성` : team.leaderName ? `팀장 ${team.leaderName}` : "팀장 없음" }}</span>
                    <span class="cat-tag" :class="team.submitted ? 'is-done' : 'is-issue'">{{ team.submitted ? "제출" : "미제출" }}</span>
                </component>
            </div>

            <footer class="collection-foot">
                <button type="button" class="btn" :disabled="isMaking || !status.submitted" @click="makeDeck">
                    <Download :size="14" />
                    {{ isMaking ? "만드는 중" : status.complete ? `${scopeLabel} PPT 만들기` : "낸 부서만으로 PPT 만들기" }}
                </button>
            </footer>
        </template>
    </section>
</template>

<style scoped src="../styles/components/weekly-collection.css"></style>
