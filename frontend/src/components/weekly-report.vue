<script setup>
import { computed, onMounted, ref, watch } from "vue";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { isAdmin } from "../composables/useSession";
import { useDialog } from "../composables/useDialog";
import PizZip from "pizzip";
import Docxtemplater from "docxtemplater";
import { saveAs } from "file-saver";
import { ChevronDown, ChevronLeft, ChevronRight, Trash2 } from "lucide-vue-next";
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

/** 고른 날들과 같은 주에 이미 만든 주간보고. 새로 만들면 덮어쓰게 되니 미리 알린다. */
const existingWeekly = computed(() => {
    const key = weekKeyOfDates(selects.value.length ? selects.value : weekDays.value);
    if (!key) return null;
    return weeklyGroups.value.find((group) => group.key === key) || null;
});

/** 지난 평일인데 일일보고가 없는 날. 초안에 '빠진 요일'로 적힌다. */
const missingDayCount = computed(
    () => weekDays.value.filter((day) => !hasMine(day) && !isFutureDay(day)).length,
);

const createSummary = computed(() => {
    const bits = [`선택 ${selects.value.length}일`];
    if (missingDayCount.value) bits.push(`빠진 날 ${missingDayCount.value}일은 초안에 표시돼요`);
    return bits.join(" · ");
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
        <header class="page-intro">
            <div class="page-intro-text">
                <h1>{{ headerTitle }}</h1>
                <p>{{ isThisWeek ? "이번 주" : "지난 기간" }} · 일일보고를 골라 주간 초안을 만들어요</p>
            </div>
            <div class="page-intro-actions week-nav">
                <div class="week-stepper" role="group" aria-label="주 이동">
                    <button type="button" aria-label="이전 주" @click="prevWeek" :disabled="isLoading">
                        <ChevronLeft :size="16" />
                    </button>
                    <button type="button" class="week-today" @click="resetThisWeek" :disabled="isLoading || isThisWeek">
                        이번 주
                    </button>
                    <button type="button" aria-label="다음 주" @click="nextWeek" :disabled="isLoading">
                        <ChevronRight :size="16" />
                    </button>
                </div>
            </div>
        </header>

        <details class="range-fold">
            <summary>기간 직접 지정</summary>
            <div class="week-range">
                <label>
                    <span>시작</span>
                    <input
                        class="input"
                        type="date"
                        :value="rangeStart"
                        :disabled="isLoading"
                        @change="pickStart($event.target.value)"
                    />
                </label>
                <label>
                    <span>끝</span>
                    <input
                        class="input"
                        type="date"
                        :value="rangeEnd"
                        :disabled="isLoading"
                        @change="pickEnd($event.target.value)"
                    />
                </label>
            </div>
        </details>

        <section class="card pick-card" aria-label="주간보고에 넣을 날">
            <div class="section-head">
                <h2>넣을 날 고르기</h2>
                <span class="section-meta">일일보고가 있는 날만 고를 수 있어요</span>
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
            <div class="pick-foot">
            <p class="create-summary">{{ createSummary }}</p>
            <div v-if="existingWeekly" class="overwrite-notice" role="status">
                <span>
                    <b>이 주의 주간보고가 이미 있어요.</b>
                </span>
                <button
                    type="button"
                    class="btn btn-small"
                    :disabled="isLoading"
                    @click="viewReport(existingWeekly.latest)"
                >
                    기존 보고 열기
                </button>
            </div>
            <button
                type="button"
                class="btn btn-primary create-week-btn"
                @click="sendDates()"
                :disabled="isLoading || selects.length === 0"
            >
                {{ isLoading ? "만드는 중..." : existingWeekly ? "새 초안 만들기" : "주간 초안 만들기" }}
            </button>
            </div>
        </section>

        <section class="group-block" aria-labelledby="made-title">
            <div class="group-head">
                <h2 id="made-title">내가 만든 주간 보고서</h2>
                <span v-if="weeklyGroups.length" class="group-meta">{{ weeklyGroups.length }}건</span>
            </div>
            <div class="group">
                <p v-if="weeklyGroups.length === 0" class="group-empty">
                    아직 만든 주간 보고서가 없어요. 위에서 날을 고르고 초안을 만들어 보세요.
                </p>
                <div
                    v-for="group in weeklyGroups"
                    :key="group.key"
                    class="row made-row"
                    role="link"
                    tabindex="0"
                    @click="!isLoading && viewReport(group.latest)"
                    @keydown.enter="!isLoading && viewReport(group.latest)"
                >
                    <span class="row-main">
                        <span class="row-title">{{ group.label }}</span>
                        <span class="row-sub">
                            {{ projectNamesOf(group.latest).join(" · ") || "프로젝트 없음" }}
                        </span>
                    </span>
                    <span class="row-end made-actions" @click.stop @keydown.stop>
                        <button
                            v-if="group.older.length"
                            type="button"
                            class="btn btn-small"
                            :disabled="isLoading"
                            :title="`같은 주 이전 초안 ${group.older.length}개 지우기`"
                            @click="cleanupOlder(group)"
                        >
                            이전 초안 {{ group.older.length }} 정리
                        </button>
                        <button type="button" class="btn btn-small" @click="downloadReport(group.latest)" :disabled="isLoading">
                            Word
                        </button>
                        <button
                            v-if="!isNarrow"
                            type="button"
                            class="btn btn-small"
                            @click="downloadPptx(group.latest)"
                            :disabled="isLoading"
                        >
                            PPT
                        </button>
                        <button
                            type="button"
                            class="row-icon-btn"
                            :aria-label="`${group.label} 삭제`"
                            title="삭제"
                            @click="deleteWeekly(group.latest.id)"
                            :disabled="isLoading"
                        >
                            <Trash2 :size="16" />
                        </button>
                    </span>
                    <ChevronRight :size="16" class="row-chevron" />
                </div>
            </div>
        </section>
    </div>
</template>

<style scoped>
.create-summary {
    margin: var(--space-3) 0 0;
    font-size: var(--fs-13);
    color: var(--text-muted);
}

.overwrite-notice {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2) var(--space-3);
    margin-top: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--warning-border);
    border-radius: var(--radius-sm);
    background: var(--warning-bg);
    font-size: var(--fs-13);
    line-height: var(--lh-base);
    color: var(--warning-fg);
}

.overwrite-notice b {
    font-weight: var(--fw-semibold);
}

.week-stepper {
    display: inline-flex;
    align-items: center;
    overflow: hidden;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
}

.week-stepper button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: var(--control-h);
    height: var(--control-h);
    padding: 0 var(--space-2);
    border: 0;
    background: transparent;
    color: var(--text);
    font: inherit;
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    cursor: pointer;
}

.week-stepper .week-today {
    padding: 0 var(--space-3);
    border-left: 1px solid var(--border);
    border-right: 1px solid var(--border);
}

.week-stepper button:hover:not(:disabled) {
    background: var(--surface-soft);
    color: var(--text-strong);
}

.week-stepper button:disabled {
    color: var(--text-muted);
    cursor: default;
}

.week-stepper button:focus-visible,
.day-chip:focus-visible,
.week-fold-head:focus-visible {
    outline: none;
    box-shadow: var(--focus-ring);
}

.range-fold summary {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    color: var(--accent);
    cursor: pointer;
    list-style: none;
}

.range-fold summary::-webkit-details-marker {
    display: none;
}

.range-fold summary::after {
    content: "›";
    transition: transform var(--dur-fast) var(--ease);
}

.range-fold[open] summary::after {
    transform: rotate(90deg);
}

.range-fold[open] .week-range {
    margin-top: var(--space-3);
}

/* 기간 입력: 접힌 칸을 열면 두 날짜 필드가 나온다. */
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

.section-meta {
    font-size: var(--fs-13);
    color: var(--text-muted);
}

.pick-foot {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3);
    margin-top: var(--space-4);
    padding-top: var(--space-4);
    border-top: 1px solid var(--border);
}

.pick-foot .create-summary {
    flex: 1;
    margin: 0;
}

.pick-foot .overwrite-notice {
    flex-basis: 100%;
    order: -1;
    margin-top: 0;
}

.made-actions .btn-small {
    height: 28px;
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
    overflow: hidden;
    border: 1px solid var(--border);
    border-radius: var(--radius);
}

/* 한 틀 안의 달력 칸. 선택하면 칸 전체가 옅은 세이지로 차고 체크가 붙는다. */
.day-chip {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-1);
    margin: 0;
    padding: var(--space-3) var(--space-4);
    border: 0;
    border-radius: 0;
    background: var(--surface);
    color: var(--text);
    font: inherit;
    line-height: var(--lh-tight);
    text-align: left;
    word-break: keep-all;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease);
}

.day-chip + .day-chip {
    border-left: 1px solid var(--border);
}

.day-chip.on::after {
    content: "";
    position: absolute;
    top: var(--space-3);
    right: var(--space-3);
    width: 16px;
    height: 16px;
    border-radius: var(--radius-xs);
    background: var(--accent) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 12.5 4 4 8-9'/%3E%3C/svg%3E") center / 12px no-repeat;
}

.day-chip:not(:disabled):not(.on):hover {
    background: var(--bg);
}

.day-chip.on {
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
    flex-shrink: 0;
}

@media (max-width: 860px) {
    .week-nav {
        width: auto;
    }

    .week-stepper button {
        min-width: var(--control-h-touch);
        height: var(--control-h-touch);
    }

    .week-range {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: var(--space-2);
    }

    .week-range .input {
        width: 100%;
        min-width: 0;
        max-width: 100%;
        height: var(--control-h-touch);
        font-size: var(--fs-16);
        overflow: hidden;
    }

    .section-head {
        flex-direction: column;
        gap: var(--space-1);
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

    .day-chip + .day-chip {
        border-left: 0;
        border-top: 1px solid var(--border);
    }

    .day-chip.on::after {
        position: static;
        order: 3;
        flex-shrink: 0;
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

    /* 행 버튼은 이름 아래 한 줄로 내린다. */
    .made-row {
        flex-wrap: wrap;
        row-gap: var(--space-2);
    }

    .made-row .row-chevron {
        display: none;
    }

    .made-actions {
        width: 100%;
    }

    .made-actions .btn-small {
        height: var(--control-h);
    }

    .made-actions .row-icon-btn {
        margin-left: auto;
        width: var(--control-h);
        height: var(--control-h);
    }
}
</style>
