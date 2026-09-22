<script setup>
import { computed, onMounted, ref, watch } from "vue";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { isAdmin } from "../composables/useSession";
import { useDialog } from "../composables/useDialog";
import PizZip from "pizzip";
import Docxtemplater from "docxtemplater";
import { saveAs } from "file-saver";
import { ChevronLeft, ChevronRight, Download, Trash2 } from "lucide-vue-next";
import { useRouter } from "vue-router";
import AppPageHeader from "./ui/AppPageHeader.vue";
import { projectsFromDeck, toWeeklyDeck } from "../lib/weeklyDeck";
import {
    isFutureDate,
    weekKeyOfDates,
    weekRangeLabel,
} from "../lib/dateScope";


const router = useRouter();

const {
    postWeeklyReport,
    getWeeklyReport,
    deleteWeeklyReport,
    downloadWeeklyPptx,
    getUserActivities,
} = useApi();
const { alert: showAlert, confirm: askConfirm } = useDialog();

const selects = ref([]);
const weekDays = ref([]);
const userId = ref(selectedUserId.value || "");
const weeklyReport = ref(null);
const isLoading = ref(false);
const myDays = ref({});
const weekdayLabels = ["월", "화", "수", "목", "금"];

const formatLocalDate = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const normalizeDay = (value) => {
    if (!value) return "";
    const text = String(value);
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
    const parsed = new Date(text);
    if (Number.isNaN(parsed.getTime())) return text.slice(0, 10);
    return formatLocalDate(parsed);
};

const weekOffset = ref(0);

const getWeekDays = (offset) => {
    const now = new Date();
    const day = now.getDay();
    const monday = new Date(now);
    monday.setDate(now.getDate() - (day === 0 ? 7 : day) + 1 + offset * 7);

    const days = [];
    for (let i = 0; i < 5; i++) {
        const d = new Date(monday);
        d.setDate(monday.getDate() + i);
        days.push(formatLocalDate(d));
    }
    return days;
};

const loadWeek = async (offset) => {
    weekOffset.value = offset;
    weekDays.value = getWeekDays(offset);
    selects.value = [];
    await loadMyWeek();
};

const weekLabel = computed(() => {
    if (weekDays.value.length < 5) return "";
    const start = weekDays.value[0];
    const end = weekDays.value[4];
    const suffix = weekOffset.value === 0 ? " (이번 주)" : "";
    return `${start} ~ ${end}${suffix}`;
});

const shortDay = (dateStr) => {
    const parts = String(dateStr).split("-");
    if (parts.length < 3) return dateStr;
    return `${Number(parts[1])}.${Number(parts[2])}`;
};

const headerTitle = computed(() => {
    if (weekDays.value.length < 5) return "주간 보고서";
    return `${shortDay(weekDays.value[0])} ~ ${shortDay(weekDays.value[4])}`;
});

const isDayOn = (dayDate) => selects.value.includes(dayDate);

const toggleSelectDay = (dayDate) => {
    if (selects.value.includes(dayDate)) {
        selects.value = selects.value.filter((day) => day !== dayDate);
        return;
    }
    selects.value = weekDays.value.filter(
        (day) => day === dayDate || selects.value.includes(day),
    );
};

const reportRange = (report) => {
    const days = [...(report?.selectedDate || [])]
        .map(normalizeDay)
        .filter(Boolean)
        .sort();
    if (!days.length) return "";
    if (days.length === 1) return days[0];
    return `${days[0]} ~ ${days[days.length - 1]}`;
};


const prevWeek = () => loadWeek(weekOffset.value - 1);
const nextWeek = () => loadWeek(weekOffset.value + 1);

/** 내가 그 날 일일보고를 냈는지. 주간보고는 내 일일보고만으로 만든다. */
const hasMine = (dayDate) => (myDays.value[dayDate] || 0) > 0;

/** 아직 오지 않은 날. 월요일에 화~금이 기본으로 켜져 있으면 끝난 주처럼 보인다. */
const isFutureDay = (dayDate) => isFutureDate(dayDate);

const dayState = (dayDate) => {
    if (isFutureDay(dayDate)) return hasMine(dayDate) ? "예정 · 작성함" : "예정";
    return hasMine(dayDate) ? "작성함" : "없음";
};

const myDayCount = computed(
    () =>
        weekDays.value.filter((day) => hasMine(day) && !isFutureDay(day)).length,
);

const headerSubtitle = computed(() => {
    const week = weekOffset.value === 0 ? "이번 주" : weekLabel.value;
    return `${week} · 오늘까지 내 일일보고 ${myDayCount.value}일`;
});

weekDays.value = getWeekDays(0);

const deleteWeekly = async (reportId) => {
    const report = (weeklyReport.value || []).find((row) => String(row.id) === String(reportId));
    if (
        !report ||
        (String(report.member_id) !== String(userId.value) && !isAdmin.value)
    ) {
        showAlert("자신의 주간 보고만 삭제할 수 있습니다.");
        return;
    }
    if (!(await askConfirm("이 주간 보고서를 삭제할까요?"))) return;
    isLoading.value = true;
    try {
        await deleteWeeklyReport(reportId);
        showAlert("주간 보고서를 삭제했습니다.");
        await fetchWeeklyReport();
    } catch (error) {
        const detail = error.response?.data?.detail;
        console.error("주간 보고서 삭제 실패:", error);
        showAlert(detail || "주간 보고서 삭제에 실패했습니다. 다시 시도해주세요.");
    } finally {
        isLoading.value = false;
    }
};

const sendDates = async () => {
    if (!userId.value) {
        showAlert("로그인이 필요합니다.");
        return;
    }
    if (selects.value.length === 0) {
        showAlert("기간(날짜)을 최소 1개 선택해주세요.");
        return;
    }
    isLoading.value = true;
    try {
        const response = await postWeeklyReport(userId.value, selects.value);
        const draft = response.data || {};
        if (!draft.report) {
            showAlert("주간 보고서 초안을 만들지 못했습니다.");
            return;
        }
        sessionStorage.setItem(
            "weeklyDraft",
            JSON.stringify({
                memberId: draft.memberId ?? userId.value,
                selects: draft.selects || [...selects.value],
                report: draft.report,
            }),
        );
        router.push("/weekly-detail/new");
    } catch (error) {
        const detail = error.response?.data?.detail;
        console.error("주간 보고서 생성 실패:", error);
        showAlert(detail || "주간 보고서 생성에 실패했습니다. 다시 시도해주세요.");
    } finally {
        isLoading.value = false;
    }
};

/** 이번 주에 내가 낸 일일보고만 조회해 선택 가능한 날짜를 정한다. */
const loadMyWeek = async () => {
    myDays.value = {};
    if (weekDays.value.length < 5 || !userId.value) return;
    try {
        const rows = await getUserActivities(
            Number(weekDays.value[0].slice(0, 4)),
            Number(weekDays.value[0].slice(5, 7)),
            weekDays.value[0],
            weekDays.value[4],
        );
        const mine = (rows || []).find(
            (row) => String(row.member_id) === String(userId.value),
        );
        const mineByDay = {};
        for (const item of mine?.activities || []) {
            mineByDay[item.report_date] = item.count || 0;
        }
        myDays.value = mineByDay;
        // 기본 선택은 오늘까지다. 아직 오지 않은 날은 직접 켜야 들어간다.
        selects.value = weekDays.value.filter(
            (day) => (mineByDay[day] || 0) > 0 && !isFutureDate(day),
        );
    } catch (error) {
        console.error("내 일일보고 조회 실패:", error);
    }
};

const fetchWeeklyReport = async () => {
    if (!userId.value) {
        weeklyReport.value = [];
        return;
    }
    isLoading.value = true;
    try {
        weeklyReport.value = await getWeeklyReport(userId.value);
    } catch (error) {
        console.error("주간 보고서 조회 실패:", error);
        weeklyReport.value = [];
    } finally {
        isLoading.value = false;
    }
};

const viewReport = (report) => {
    router.push(`/weekly-detail/${report.id}`);
};

/* 주간보고는 한 주에 하나다.
   예전에는 날짜 조합(월~수 / 월~금)이 다르면 새 문서가 쌓여서 같은 주가 두 줄로 남았다.
   새로 만들 때는 백엔드가 같은 주를 덮어쓰고, 이미 쌓인 것은 여기서 한 줄로 접는다. */
const weeklyGroups = computed(() => {
    const map = new Map();
    for (const report of weeklyReport.value || []) {
        const key = weekKeyOfDates(report.selectedDate) || `id-${report.id}`;
        if (!map.has(key)) map.set(key, []);
        map.get(key).push(report);
    }
    return [...map.entries()]
        .map(([key, rows]) => {
            const sorted = [...rows].sort((a, b) => Number(b.id) - Number(a.id));
            return {
                key,
                label: weekRangeLabel(key) || reportRange(sorted[0]),
                latest: sorted[0],
                older: sorted.slice(1),
            };
        })
        .sort((a, b) => String(b.key).localeCompare(String(a.key)));
});

/** 같은 주에 남은 옛 문서를 한 번에 치운다. */
const cleanupOlder = async (group) => {
    const ok = await askConfirm(
        `${group.label} 주의 이전 버전 ${group.older.length}건을 지울까요?`,
        {
            title: "같은 주 정리",
            help: "가장 최근에 만든 한 건만 남습니다.",
            confirmLabel: "정리",
        },
    );
    if (!ok) return;
    isLoading.value = true;
    try {
        for (const report of group.older) {
            await deleteWeeklyReport(report.id);
        }
        await fetchWeeklyReport();
    } catch (error) {
        console.error("이전 버전 정리 실패:", error);
        showAlert("이전 버전 정리에 실패했습니다.");
    } finally {
        isLoading.value = false;
    }
};

const downloadReport = async (report) => {
    try {
        isLoading.value = true;

        const response = await fetch("/asset/weekly-report-template.docx");
        if (!response.ok) {
            throw new Error("템플릿 파일을 찾을 수 없습니다.");
        }
        const arrayBuffer = await response.arrayBuffer();
        const header = new Uint8Array(arrayBuffer, 0, 2);
        if (header.length < 2 || header[0] !== 0x50 || header[1] !== 0x4b) {
            throw new Error("템플릿 파일이 올바른 Word 문서가 아닙니다.");
        }

        const zip = new PizZip(arrayBuffer);
        const doc = new Docxtemplater(zip, {
            paragraphLoop: true,
            linebreaks: true,
        });

        const sortedDates = [...(report.selectedDate || [])]
            .map((d) => formatLocalDate(new Date(d)))
            .sort();
        const period_start = sortedDates[0] || "";
        const period_end = sortedDates[sortedDates.length - 1] || "";
        const selectedDateRange = period_start
            ? [`${period_start} ~ ${period_end}`]
            : [];

        const createdDateRaw =
            report.createdAt || report.created_at || new Date().toISOString();
        const created_date = formatLocalDate(new Date(createdDateRaw));

        const asReportItems = (items) => {
            const values = Array.isArray(items)
                ? items.filter((item) => {
                    if (item === null || item === undefined) return false;
                    return typeof item !== "string" || item.trim().length > 0;
                })
                : [];
            return values.length > 0 ? values : ["없음"];
        };

        const mapped = projectsFromDeck(toWeeklyDeck(report.report));
        const projectsList = (mapped.length ? mapped : report.report?.projects || []).map((p) => {
            const nextPlans =
                Array.isArray(p.nextWeekPlans) && p.nextWeekPlans.length > 0
                    ? p.nextWeekPlans
                    : p.nextPlans;

            return {
                project_name: p.projectName || "",
                completed: asReportItems(p.completedTasks),
                inProgress: asReportItems(p.inProgressTasks),
                issues: asReportItems(p.issues).map((issue) => {
                    const content =
                        typeof issue === "string"
                            ? issue
                            : issue.content || "없음";
                    return { content };
                }),
                nextPlans: asReportItems(nextPlans),
            };
        });

        const project_count = projectsList.length;
        const missing = [];
        const missing_count = missing.length;



        const data = {
            selectedDate: selectedDateRange,
            created_date,
            project_count,
            missing_count,
            projects: projectsList,
            missing,
        };

        doc.render(data);

        const out = doc.getZip().generate({
            type: "blob",
            mimeType:
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        });

        const filename = `${fileBaseName(report)}.docx`;

        saveAs(out, filename);
    } catch (error) {
        console.error("보고서 다운로드 실패:", error);
        showAlert("보고서 다운로드 중 오류가 발생했습니다: " + error.message);
    } finally {
        isLoading.value = false;
    }
};

const periodEndOf = (report) => {
    const sortedDates = [...(report.selectedDate || [])]
        .map((d) => formatLocalDate(new Date(d)))
        .sort();
    return sortedDates[sortedDates.length - 1] || "";
};

/** 팀 폴더에 그대로 넣을 수 있게 실제 파일명 규칙을 따른다: DXel 주간보고 20260918_경영지원센터 */
const fileBaseName = (report) => {
    const stamp = periodEndOf(report).replaceAll("-", "");
    const center = String(report.report?.center || "").trim();
    const owner =
        center && center !== "미지정"
            ? center
            : report.memberName || `사용자${report.memberId}`;
    return `DXel 주간보고 ${stamp}_${owner}`;
};

const downloadPptx = async (report) => {
    if (!report?.id) {
        showAlert("저장된 주간 보고서만 PPT로 받을 수 있습니다.");
        return;
    }
    isLoading.value = true;
    try {
        const blob = await downloadWeeklyPptx(report.id);
        const filename = `${fileBaseName(report)}.pptx`;
        saveAs(blob, filename);
    } catch (error) {
        console.error("PPT 다운로드 실패:", error);
        showAlert("PPT 다운로드 중 오류가 발생했습니다.");
    } finally {
        isLoading.value = false;
    }
};


const projectNamesOf = (report) => {
    const deck = toWeeklyDeck(report?.report);
    const names = [...(deck.done || []), ...(deck.next || [])]
        .map((section) => String(section.title || "").trim())
        .filter(Boolean);
    if (names.length) return [...new Set(names)];
    return (report?.report?.projects || [])
        .map((project) => project.projectName)
        .filter(Boolean);
};

watch(
    selectedUserId,
    async (id) => {
        userId.value = id || "";
        await loadMyWeek();
        await fetchWeeklyReport();
    },
);

onMounted(async () => {
    userId.value = selectedUserId.value || "";
    await loadMyWeek();
    await fetchWeeklyReport();
});
</script>

<template>
    <div class="page weekly-report-page">
        <AppPageHeader :title="headerTitle" :subtitle="headerSubtitle">
            <template #filters>
                <div class="week-nav">
                    <button
                        v-if="weekOffset !== 0"
                        type="button"
                        class="btn btn-small"
                        @click="loadWeek(0)"
                        :disabled="isLoading"
                    >
                        이번 주로
                    </button>
                    <div class="week-nav-arrows">
                        <button class="icon-btn" aria-label="이전 주" @click="prevWeek" :disabled="isLoading">
                            <ChevronLeft :size="16" />
                        </button>
                        <button class="icon-btn" aria-label="다음 주" @click="nextWeek" :disabled="isLoading">
                            <ChevronRight :size="16" />
                        </button>
                    </div>
                </div>
            </template>
            <template #actions>
                <button class="btn btn-primary hide-on-narrow" @click="sendDates()" :disabled="isLoading || selects.length === 0">
                    {{ isLoading ? "만드는 중..." : "내 주간 보고서 만들기" }}
                </button>
            </template>
        </AppPageHeader>

        <section class="card" aria-label="넣을 날짜">
            <div class="section-head">
                <h2>넣을 날짜</h2>
                <p>{{ selects.length }}일 선택</p>
            </div>
            <div class="day-chips" role="group" aria-label="넣을 날짜">
                <button
                    v-for="(dayDate, index) in weekDays"
                    :key="dayDate"
                    type="button"
                    class="day-chip"
                    :class="{
                        on: isDayOn(dayDate),
                        'is-blank': !hasMine(dayDate),
                        'is-future': isFutureDay(dayDate),
                    }"
                    :aria-pressed="isDayOn(dayDate)"
                    :disabled="!hasMine(dayDate)"
                    :title="hasMine(dayDate) ? (isFutureDay(dayDate) ? '아직 오지 않은 날입니다' : null) : '이 날 작성한 일일보고가 없습니다'"
                    @click="toggleSelectDay(dayDate)"
                >
                    <span class="day-chip-name">{{ weekdayLabels[index] }}</span>
                    <span class="day-chip-date">{{ shortDay(dayDate) }}</span>
                    <span class="day-chip-state">{{ dayState(dayDate) }}</span>
                </button>
            </div>
            <p v-if="myDayCount === 0" class="week-hint">
                이 주에 오늘까지 작성한 일일보고가 없습니다.
                <router-link to="/report">일일보고를 먼저 작성</router-link>하면 여기서 모을 수 있습니다.
            </p>
            <p v-else class="week-hint">
                내가 쓴 일일보고만 모아 만듭니다. 팀 전체 제출 현황은
                <router-link to="/activities">사용자 활동</router-link>에서 봅니다.
            </p>
            <button
                class="btn btn-primary create-week-btn"
                @click="sendDates()"
                :disabled="isLoading || selects.length === 0"
            >
                {{ isLoading ? "만드는 중..." : "내 주간 보고서 만들기" }}
            </button>
        </section>

        <section class="card" aria-label="만든 주간 보고서">
            <div class="section-head">
                <h2>내가 만든 보고서</h2>
                <p>{{ weeklyGroups.length }}주</p>
            </div>
            <div v-if="weeklyGroups.length === 0" class="empty-state">
                아직 만든 주간 보고서가 없습니다
            </div>
            <ul v-else class="report-list">
                <li v-for="group in weeklyGroups" :key="group.key" class="report-row">
                    <button type="button" class="report-main" :disabled="isLoading" @click="viewReport(group.latest)">
                        <strong>{{ group.label }}</strong>
                        <span v-if="projectNamesOf(group.latest).length">
                            {{ projectNamesOf(group.latest).join(" · ") }}
                        </span>
                        <span v-if="group.older.length" class="report-dupe">
                            같은 주 이전 버전 {{ group.older.length }}건
                        </span>
                    </button>
                    <div class="report-row-actions">
                        <button
                            v-if="group.older.length"
                            type="button"
                            class="btn btn-small cleanup-btn"
                            :disabled="isLoading"
                            @click="cleanupOlder(group)"
                        >
                            이전 버전 정리
                        </button>
                        <button type="button" class="btn btn-small" @click="downloadReport(group.latest)" :disabled="isLoading">
                            <Download :size="14" /> Word
                        </button>
                        <button type="button" class="btn btn-small" @click="downloadPptx(group.latest)" :disabled="isLoading">
                            <Download :size="14" /> PPT
                        </button>
                        <button
                            type="button"
                            class="icon-btn is-danger"
                            aria-label="주간 보고서 삭제"
                            @click="deleteWeekly(group.latest.id)"
                            :disabled="isLoading"
                        >
                            <Trash2 :size="15" />
                        </button>
                    </div>
                </li>
            </ul>
        </section>
    </div>
</template>

<style scoped>
.week-nav {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
}

.week-nav-arrows {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    margin-left: auto;
}

.icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: 50%;
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
    transition:
        background var(--dur-fast) var(--ease),
        color var(--dur-fast) var(--ease);
}

.icon-btn:hover {
    background: var(--surface-soft);
    color: var(--text-strong);
}

.icon-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.icon-btn.is-danger {
    border-color: transparent;
    color: var(--text-muted);
}

.icon-btn.is-danger:hover {
    background: var(--danger-bg);
    color: var(--danger-fg);
}

.weekly-report-page > .card {
    margin-bottom: var(--space-4);
}

.section-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
}

.section-head h2 {
    margin: 0;
    font-size: var(--fs-16);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.section-head p {
    margin: 0;
    font-size: var(--fs-13);
    color: var(--text);
}

/* 날짜 칩에 그날 제출 인원을 같이 적어 표를 펼치지 않아도 흐름이 보인다. */
.day-chips {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: var(--space-2);
}

.day-chip {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--text);
    font: inherit;
    cursor: pointer;
    transition:
        border-color var(--dur-fast) var(--ease),
        background var(--dur-fast) var(--ease);
}

.day-chip:hover {
    border-color: var(--border-strong);
}

.day-chip.on {
    border-color: var(--accent);
    background: var(--accent-soft);
}

.day-chip-name {
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.day-chip-date {
    font-size: var(--fs-12);
    color: var(--text);
}

.day-chip-state {
    margin-left: auto;
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    color: var(--success-fg);
}

.day-chip.is-blank {
    cursor: not-allowed;
    background: var(--bg);
}

.day-chip.is-blank .day-chip-name,
.day-chip.is-blank .day-chip-date {
    color: var(--text-muted);
}

.day-chip.is-blank .day-chip-state {
    color: var(--text-muted);
    font-weight: var(--fw-medium);
}

.day-chip.is-blank:hover {
    border-color: var(--border);
}

/* 아직 오지 않은 날. 켤 수는 있지만 끝난 날처럼 보이지 않게 흐리게 둔다. */
.day-chip.is-future:not(.on) {
    opacity: 0.7;
}

.day-chip.is-future .day-chip-state {
    color: var(--text);
    font-weight: var(--fw-medium);
}

.report-dupe {
    color: var(--warning-fg);
    font-weight: var(--fw-semibold);
}

.week-hint {
    margin-top: var(--space-3);
    font-size: var(--fs-13);
    color: var(--text);
}

.week-hint a {
    color: var(--accent-hover);
}

.report-list {
    list-style: none;
    margin: 0;
    padding: 0;
}

.report-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) 0;
    border-top: 1px solid var(--border);
}

.report-row:first-child {
    border-top: none;
}

.report-main {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    flex: 1;
    min-width: 0;
    margin: 0;
    padding: var(--space-1) var(--space-2);
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    font: inherit;
    text-align: left;
    cursor: pointer;
}

.report-main:hover {
    background: var(--surface-soft);
}

.report-main strong {
    font-size: var(--fs-14);
    color: var(--text-strong);
}

.report-main span {
    font-size: var(--fs-12);
    color: var(--text);
}

.report-row-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
}

.create-week-btn {
    display: none;
}

@media (max-width: 860px) {
    :deep(.page-header-actions) {
        display: none;
    }

    .week-nav .icon-btn {
        width: 44px;
        height: 44px;
    }

    .day-chips {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        overflow: visible;
        margin: 0;
        padding: 0;
        gap: 6px;
    }

    .day-chip {
        min-width: 0;
        min-height: 72px;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 2px;
        padding: 8px 2px;
    }

    .day-chip-name {
        font-size: 14px;
    }

    .day-chip-date,
    .day-chip-state {
        margin-left: 0;
        font-size: 11px;
    }

    .create-week-btn {
        display: flex;
        width: 100%;
        min-height: 48px;
        margin-top: var(--space-3);
    }

    .report-row {
        flex-direction: column;
        align-items: stretch;
        gap: 8px;
        padding: 14px 0;
    }

    .report-main {
        padding: 8px 0;
        min-height: 44px;
    }

    .report-main strong {
        font-size: 15px;
    }

    .report-row-actions {
        display: grid;
        grid-template-columns: 1fr 1fr 44px;
        width: 100%;
        gap: 8px;
    }

    .report-row-actions .cleanup-btn {
        grid-column: 1 / -1;
    }

    .report-row-actions .btn {
        min-height: 44px;
        width: 100%;
    }

    .cleanup-btn {
        grid-column: 1 / -1;
    }

    .report-row-actions .icon-btn {
        width: 44px;
        height: 44px;
        justify-self: end;
    }
}

</style>
