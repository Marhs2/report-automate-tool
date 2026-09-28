<script setup>
import { computed, onMounted, ref, watch } from "vue";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { isAdmin } from "../composables/useSession";
import { useDialog } from "../composables/useDialog";
import PizZip from "pizzip";
import Docxtemplater from "docxtemplater";
import { saveAs } from "file-saver";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-vue-next";
import { useRouter } from "vue-router";
import { projectsFromDeck, toWeeklyDeck } from "../lib/weeklyDeck";
import { useSidebar } from "../composables/useSidebar";
import {
    isFutureDate,
    mondayOf,
    weekdayLabelOf,
    weekKeyOfDates,
    weekRangeLabel,
} from "../lib/dateScope";


const router = useRouter();
const { isNarrow } = useSidebar();

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

const weekdayName = (dateStr) => weekdayLabelOf(dateStr);

const parseIso = (value) => {
    const [year, month, day] = String(value || "").split("-").map(Number);
    if (!year || !month || !day) return null;
    const date = new Date(year, month - 1, day);
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
        return null;
    }
    return date;
};

const thisWorkWeek = () => {
    const now = new Date();
    const weekday = now.getDay();
    const monday = new Date(now);
    monday.setDate(now.getDate() - (weekday === 0 ? 7 : weekday) + 1);
    const friday = new Date(monday);
    friday.setDate(monday.getDate() + 4);
    return { start: formatLocalDate(monday), end: formatLocalDate(friday) };
};

const workdaysBetween = (start, end) => {
    const from = parseIso(start);
    const to = parseIso(end);
    if (!from || !to || from > to) return [];
    const days = [];
    const cursor = new Date(from);
    while (cursor <= to) {
        const weekday = cursor.getDay();
        if (weekday !== 0 && weekday !== 6) days.push(formatLocalDate(cursor));
        cursor.setDate(cursor.getDate() + 1);
    }
    return days;
};

const openingWeek = thisWorkWeek();
const rangeStart = ref(openingWeek.start);
const rangeEnd = ref(openingWeek.end);

const applyRange = async (start, end) => {
    if (!start || !end || start > end) return;
    const from = parseIso(start);
    const to = parseIso(end);
    const span = Math.round((to - from) / 86400000);
    if (span > 62) {
        showAlert("기간은 두 달 안으로 골라 주세요.");
        return;
    }
    rangeStart.value = start;
    rangeEnd.value = end;
    weekDays.value = workdaysBetween(start, end);
    selects.value = [];
    await loadMyWeek();
};

const pickStart = (value) => {
    if (!value) return;
    const end = value > rangeEnd.value ? value : rangeEnd.value;
    applyRange(value, end);
};

const pickEnd = (value) => {
    if (!value) return;
    const start = value < rangeStart.value ? value : rangeStart.value;
    applyRange(start, value);
};

const shiftRange = (weeks) => {
    const start = parseIso(rangeStart.value);
    const end = parseIso(rangeEnd.value);
    if (!start || !end) return;
    start.setDate(start.getDate() + weeks * 7);
    end.setDate(end.getDate() + weeks * 7);
    applyRange(formatLocalDate(start), formatLocalDate(end));
};

const resetThisWeek = () => {
    const week = thisWorkWeek();
    applyRange(week.start, week.end);
};

const isThisWeek = computed(() => {
    const week = thisWorkWeek();
    return rangeStart.value === week.start && rangeEnd.value === week.end;
});

const shortDay = (dateStr) => {
    const parts = String(dateStr).split("-");
    if (parts.length < 3) return dateStr;
    return `${Number(parts[1])}.${Number(parts[2])}`;
};

const headerTitle = computed(() => {
    if (!rangeStart.value || !rangeEnd.value) return "주간 보고서";
    return `${shortDay(rangeStart.value)} ~ ${shortDay(rangeEnd.value)}`;
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


const prevWeek = () => shiftRange(-1);
const nextWeek = () => shiftRange(1);

/** 내가 그 날 일일보고를 냈는지. 주간보고는 내 일일보고만으로 만든다. */
const hasMine = (dayDate) => (myDays.value[dayDate] || 0) > 0;

/** 아직 오지 않은 날. 월요일에 화~금이 기본으로 켜져 있으면 끝난 주처럼 보인다. */
const isFutureDay = (dayDate) => isFutureDate(dayDate);

const dayState = (dayDate) => {
    if (isFutureDay(dayDate)) return hasMine(dayDate) ? "예정 · 작성함" : "예정";
    return hasMine(dayDate) ? "작성함" : "보고 없음";
};

const myDayCount = computed(
    () =>
        weekDays.value.filter((day) => hasMine(day) && !isFutureDay(day)).length,
);

const headerSubtitle = computed(() => {
    const week = isThisWeek.value ? "이번 주 · " : "";
    return `${week}내 일일보고 ${myDayCount.value}일`;
});

const weekGroups = computed(() => {
    const groups = [];
    for (const day of weekDays.value) {
        const key = mondayOf(day);
        let group = groups.find((item) => item.key === key);
        if (!group) {
            group = { key, days: [] };
            groups.push(group);
        }
        group.days.push(day);
    }
    return groups.map((group) => {
        const written = group.days.filter((day) => hasMine(day) && !isFutureDay(day)).length;
        const picked = group.days.filter((day) => selects.value.includes(day)).length;
        return {
            key: group.key,
            days: group.days,
            label: `${shortDay(group.days[0])} ~ ${shortDay(group.days[group.days.length - 1])}`,
            summary: written ? `선택 ${picked}` : "보고 없음",
            picked,
        };
    });
});

const foldWeeks = computed(() => isNarrow.value && weekGroups.value.length > 1);
const openWeek = ref("");

watch(weekGroups, (groups) => {
    if (!groups.length) {
        openWeek.value = "";
        return;
    }
    if (groups.some((group) => group.key === openWeek.value)) return;
    const picked = [...groups].reverse().find((group) => group.picked > 0);
    openWeek.value = (picked || groups[groups.length - 1]).key;
});

weekDays.value = workdaysBetween(rangeStart.value, rangeEnd.value);

const deleteWeekly = async (reportId) => {
    const report = (weeklyReport.value || []).find((row) => String(row.id) === String(reportId));
    // 목록 API는 memberId다. member_id만 보면 본인 보고서도 소유자가 비어 삭제가 막힌다.
    const ownerId = report?.memberId ?? report?.member_id;
    if (
        !report ||
        (String(ownerId) !== String(userId.value) && !isAdmin.value)
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

/** 고른 기간에 내가 낸 일일보고만 조회해 선택 가능한 날짜를 정한다. */
const loadMyWeek = async () => {
    myDays.value = {};
    if (!rangeStart.value || !rangeEnd.value || !userId.value) return;
    try {
        const rows = await getUserActivities(
            Number(rangeStart.value.slice(0, 4)),
            Number(rangeStart.value.slice(5, 7)),
            rangeStart.value,
            rangeEnd.value,
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
        <header class="week-head">
            <div class="week-head-text">
                <h1>{{ headerTitle }}</h1>
                <p>{{ headerSubtitle }}</p>
            </div>
            <div class="week-nav">
                <button
                    v-if="!isThisWeek"
                    type="button"
                    class="btn btn-small"
                    @click="resetThisWeek"
                    :disabled="isLoading"
                >
                    이번 주로
                </button>
                <div class="week-nav-arrows">
                    <button type="button" class="icon-btn" aria-label="이전 주" @click="prevWeek" :disabled="isLoading">
                        <ChevronLeft :size="16" />
                    </button>
                    <button type="button" class="icon-btn" aria-label="다음 주" @click="nextWeek" :disabled="isLoading">
                        <ChevronRight :size="16" />
                    </button>
                </div>
            </div>
        </header>

        <div class="week-range">
            <label>
                <span>주 시작</span>
                <input
                    class="input"
                    type="date"
                    :value="rangeStart"
                    :disabled="isLoading"
                    @change="pickStart($event.target.value)"
                />
            </label>
            <label>
                <span>주 끝</span>
                <input
                    class="input"
                    type="date"
                    :value="rangeEnd"
                    :disabled="isLoading"
                    @change="pickEnd($event.target.value)"
                />
            </label>
        </div>

        <section class="card" aria-label="주간보고에 넣을 날">
            <div class="section-head">
                <h2>주간보고에 넣을 날</h2>
            </div>
            <div class="week-folds">
                <div v-for="group in weekGroups" :key="group.key" class="week-fold">
                    <button
                        v-if="foldWeeks"
                        type="button"
                        class="week-fold-head"
                        :aria-expanded="openWeek === group.key"
                        @click="openWeek = openWeek === group.key ? '' : group.key"
                    >
                        <span>{{ group.label }}</span>
                        <span class="week-fold-meta">{{ group.summary }}</span>
                        <ChevronDown :size="16" :class="{ 'is-open': openWeek === group.key }" />
                    </button>
                    <div
                        v-if="!foldWeeks || openWeek === group.key"
                        class="day-chips"
                        role="group"
                        :aria-label="group.label"
                    >
                        <button
                            v-for="dayDate in group.days"
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
                            <span class="day-chip-name">{{ weekdayName(dayDate) }}</span>
                            <span class="day-chip-date">{{ shortDay(dayDate) }}</span>
                            <span class="day-chip-state">{{ dayState(dayDate) }}</span>
                        </button>
                    </div>
                </div>
            </div>
            <button
                type="button"
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
            </div>
            <div v-if="weeklyGroups.length === 0" class="empty-state">
                아직 만든 주간 보고서가 없습니다
            </div>
            <ul v-else class="report-list">
                <li v-for="group in weeklyGroups" :key="group.key" class="report-row">
                    <div class="report-top">
                        <button type="button" class="report-main" :disabled="isLoading" @click="viewReport(group.latest)">
                            <strong>{{ group.label }}</strong>
                            <span v-if="projectNamesOf(group.latest).length">
                                {{ projectNamesOf(group.latest).join(" · ") }}
                            </span>
                        </button>
                        <button
                            type="button"
                            class="btn btn-small btn-danger row-delete"
                            @click="deleteWeekly(group.latest.id)"
                            :disabled="isLoading"
                        >
                            삭제
                        </button>
                    </div>
                    <div class="report-row-actions">
                        <button
                            v-if="group.older.length"
                            type="button"
                            class="btn btn-small cleanup-btn"
                            :disabled="isLoading"
                            @click="cleanupOlder(group)"
                        >
                            정리
                        </button>
                        <button type="button" class="btn btn-small" @click="downloadReport(group.latest)" :disabled="isLoading">
                            Word
                        </button>
                        <button type="button" class="btn btn-small" @click="downloadPptx(group.latest)" :disabled="isLoading">
                            PPT
                        </button>
                    </div>
                </li>
            </ul>
        </section>
    </div>
</template>

<style scoped>
/* 머리: 기간 제목 + 주 이동. 다른 화면의 page-header와 같은 리듬(제목 24 / 보조 14). */
.week-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3) var(--space-4);
}

.week-head-text {
    flex: 1;
    min-width: 0;
}

.week-head h1 {
    margin: 0;
    font-size: var(--fs-24);
    line-height: var(--lh-tight);
    white-space: nowrap;
}

.week-head p {
    margin: var(--space-1) 0 0;
    font-size: var(--fs-14);
    line-height: var(--lh-base);
    color: var(--text-muted);
}

.week-nav {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    gap: var(--space-2);
}

.week-nav-arrows {
    display: flex;
    align-items: center;
    gap: var(--space-1);
}

.icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: var(--control-h-sm);
    height: var(--control-h-sm);
    padding: 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
    transition:
        background var(--dur-fast) var(--ease),
        border-color var(--dur-fast) var(--ease),
        color var(--dur-fast) var(--ease);
}

.icon-btn:hover {
    background: var(--surface-soft);
    border-color: var(--border-strong);
    color: var(--text-strong);
}

.icon-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.icon-btn:disabled:hover {
    background: var(--surface);
    border-color: var(--border);
    color: var(--text);
}

/* 커스텀 컨트롤의 포커스는 하드 아웃라인 대신 공용 포커스 링을 쓴다. */
.icon-btn:focus-visible,
.day-chip:focus-visible,
.week-fold-head:focus-visible,
.report-main:focus-visible {
    outline: none;
    border-color: var(--accent);
    box-shadow: var(--focus-ring);
}

/* 기간 입력: 두 날짜 필드를 제목 아래 왼쪽에 모아 둔다. */
.week-range {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 200px));
    gap: var(--space-3);
}

.week-range label {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-width: 0;
}

.week-range span {
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    color: var(--text-strong);
}

.week-range .input {
    min-width: 0;
    height: var(--control-h);
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
    line-height: var(--lh-tight);
}

/* 주 단위 묶음. 데스크톱은 간격만, 좁은 화면(접힘)은 헤어라인으로 나눈다. */
.week-folds {
    display: grid;
    gap: var(--space-3);
}

.week-fold-head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    min-height: var(--control-h-touch);
    margin: 0;
    padding: var(--space-2) 0;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-strong);
    font: inherit;
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
    text-align: left;
    word-break: keep-all;
    cursor: pointer;
}

.week-fold-meta {
    margin-left: auto;
    font-size: var(--fs-13);
    font-weight: normal;
    color: var(--text-muted);
}

.week-fold-head svg {
    flex: none;
    color: var(--text-muted);
    transition: transform var(--dur-fast) var(--ease);
}

.week-fold-head svg.is-open {
    transform: rotate(180deg);
}

.week-fold-head + .day-chips {
    margin-bottom: var(--space-3);
}

/* 날짜 타일: select-card와 같은 문법. hover는 accent-border, 선택은 accent 보더. */
.day-chips {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: var(--space-2);
}

.day-chip {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-1);
    margin: 0;
    padding: var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--text);
    font: inherit;
    line-height: var(--lh-tight);
    text-align: left;
    word-break: keep-all;
    cursor: pointer;
    transition:
        border-color var(--dur-fast) var(--ease),
        background var(--dur-fast) var(--ease);
}

.day-chip:not(:disabled):not(.on):hover {
    border-color: var(--accent-border);
    background: var(--accent-soft);
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

.day-chip.on .day-chip-name {
    color: var(--accent-hover);
}

.day-chip-date {
    font-size: var(--fs-12);
    color: var(--text-muted);
}

.day-chip-state {
    font-size: var(--fs-12);
    font-weight: var(--fw-medium);
    color: var(--success-fg);
}

/* 일일보고가 없는 날은 고를 수 없다. 옅은 면으로 눕혀 둔다. */
.day-chip.is-blank {
    background: var(--surface-soft);
    cursor: not-allowed;
}

.day-chip.is-blank .day-chip-name,
.day-chip.is-blank .day-chip-date,
.day-chip.is-blank .day-chip-state {
    color: var(--text-muted);
}

/* 아직 오지 않은 날. 켤 수는 있지만 끝난 날처럼 보이지 않게 흐리게 둔다. */
.day-chip.is-future:not(.on) .day-chip-name {
    color: var(--text-muted);
}

.day-chip.is-future .day-chip-state {
    color: var(--text);
}

.create-week-btn {
    display: flex;
    width: fit-content;
    margin: var(--space-4) 0 0 auto;
}

/* 만든 보고서 목록: 카드 안에서 헤어라인으로만 행을 나눈다. */
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
    padding-top: 0;
    border-top: 0;
}

.report-row:last-child {
    padding-bottom: 0;
}

/* 데스크톱은 제목 · 내려받기 · 삭제 순으로 한 줄. 좁은 화면에서 다시 감싼다. */
.report-top {
    display: contents;
}

.report-main {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
    margin: 0 0 0 calc(-1 * var(--space-2));
    padding: var(--space-1) var(--space-2);
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text);
    font: inherit;
    line-height: var(--lh-base);
    text-align: left;
    word-break: keep-all;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease);
}

.report-main:not(:disabled):hover {
    background: var(--surface-soft);
}

.report-main strong {
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
}

.report-main span {
    overflow: hidden;
    font-size: var(--fs-13);
    color: var(--text-muted);
    text-overflow: ellipsis;
    white-space: nowrap;
}

.report-row-actions {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    order: 1;
    gap: var(--space-2);
}

/* 삭제는 ghost. 쉬고 있을 땐 조용히, hover에서만 danger로. */
.row-delete {
    order: 2;
    color: var(--text-muted);
}

.row-delete:hover {
    color: var(--danger-fg);
}

@media (max-width: 860px) {
    .week-head h1 {
        font-size: var(--fs-20);
    }

    .week-nav {
        width: 100%;
    }

    .week-nav-arrows {
        margin-left: auto;
    }

    .week-nav .btn {
        min-height: var(--control-h-touch);
    }

    .icon-btn {
        width: var(--control-h-touch);
        height: var(--control-h-touch);
    }

    .week-range {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: var(--space-2);
    }

    .week-range .input {
        height: var(--control-h-touch);
        font-size: var(--fs-16);
    }

    .week-folds {
        gap: 0;
    }

    .week-fold + .week-fold {
        border-top: 1px solid var(--border);
    }

    .day-chips {
        grid-template-columns: minmax(0, 1fr);
    }

    .day-chip {
        flex-direction: row;
        align-items: center;
        gap: var(--space-3);
        min-height: var(--control-h-touch);
        padding: var(--space-2) var(--space-3);
    }

    .day-chip-date {
        font-size: var(--fs-14);
        color: var(--text);
    }

    .day-chip-state {
        margin-left: auto;
        font-size: var(--fs-13);
    }

    .create-week-btn {
        width: 100%;
        min-height: var(--control-h-touch);
    }

    .report-row {
        flex-direction: column;
        align-items: stretch;
        gap: var(--space-2);
        padding: var(--space-3) 0;
    }

    .report-top {
        display: flex;
        align-items: center;
        gap: var(--space-2);
    }

    .report-main {
        min-height: var(--control-h-touch);
        margin-left: 0;
        padding: var(--space-2) 0;
    }

    .report-main:not(:disabled):hover {
        background: transparent;
    }

    .row-delete {
        min-height: var(--control-h-touch);
    }

    .report-row-actions {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        width: 100%;
        gap: var(--space-2);
    }

    .cleanup-btn {
        grid-column: 1 / -1;
    }

    .report-row-actions .btn {
        width: 100%;
        min-height: var(--control-h-touch);
    }
}
</style>
