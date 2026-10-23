<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import useApi from "../composables/useApi";
import { selectedUserId } from "../composables/useSelectedUser";
import { isAdmin, leaderTeamId } from "../composables/useSession";
import { useDialog } from "../composables/useDialog";
import { saveAs } from "file-saver";
import { Check, ChevronDown, ChevronLeft, ChevronRight, Download, Trash2 } from "lucide-vue-next";
import { useRouter } from "vue-router";
import { projectsFromDeck, toWeeklyDeck } from "../lib/weeklyDeck";
import { useSidebar } from "../composables/useSidebar";
import WeeklyCollection from "./weekly-collection.vue";
import WeekDots from "./ui/WeekDots.vue";
import {
    isFutureDate,
    mondayOf,
    todayString,
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

/* ---- 상태 ------------------------------------------------------------ */
const selects = ref([]);
const weekDays = ref([]);
const userId = ref(selectedUserId.value || "");
const weeklyReport = ref(null);
const isLoading = ref(false);
const myDays = ref({});
const weekLoading = ref(false);
const weekError = ref("");
const listError = ref("");
const showRange = ref(false);

/* ---- 날짜 도우미 ----------------------------------------------------- */
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

const shortDay = (dateStr) => {
    const parts = String(dateStr).split("-");
    if (parts.length < 3) return dateStr;
    return `${Number(parts[1])}.${Number(parts[2])}`;
};

/* ---- 기간 ------------------------------------------------------------ */
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

const prevWeek = () => shiftRange(-1);
const nextWeek = () => shiftRange(1);

const isThisWeek = computed(() => {
    const week = thisWorkWeek();
    return rangeStart.value === week.start && rangeEnd.value === week.end;
});

const headerTitle = computed(() => {
    if (!rangeStart.value || !rangeEnd.value) return "주간 보고서";
    return `${shortDay(rangeStart.value)} ~ ${shortDay(rangeEnd.value)}`;
});

/* ---- 날 고르기 ------------------------------------------------------- */
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

/** 내가 그 날 일일보고를 냈는지. 주간보고는 내 일일보고만으로 만든다. */
const hasMine = (dayDate) => (myDays.value[dayDate] || 0) > 0;

/** 아직 오지 않은 날. 월요일에 화~금이 기본으로 켜져 있으면 끝난 주처럼 보인다. */
const isFutureDay = (dayDate) => isFutureDate(dayDate);
const isToday = (dayDate) => dayDate === todayString();

const dayState = (dayDate) => {
    if (isFutureDay(dayDate)) return hasMine(dayDate) ? "예정 · 작성함" : "예정";
    if (hasMine(dayDate)) return "작성함";
    return isToday(dayDate) ? "오늘 아직" : "보고 없음";
};

const dayTitle = (dayDate) => {
    if (!hasMine(dayDate)) return "이 날 작성한 일일보고가 없습니다";
    return isFutureDay(dayDate) ? "아직 오지 않은 날입니다" : null;
};

/** 팀 목록과 같은 점 언어로 그 날의 상태 하나. */
const dotOf = (dayDate) => {
    let state = "missing";
    if (hasMine(dayDate)) state = isToday(dayDate) ? "today-done" : "done";
    else if (isFutureDay(dayDate)) state = "future";
    else if (isToday(dayDate)) state = "today";
    return { label: weekdayName(dayDate), state };
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
            dots: group.days.map(dotOf),
            label: `${shortDay(group.days[0])} ~ ${shortDay(group.days[group.days.length - 1])}`,
            summary: written ? `선택 ${picked}` : "보고 없음",
            picked,
        };
    });
});

const foldWeeks = computed(() => isNarrow.value && weekGroups.value.length > 1);
const showWeekHeads = computed(() => weekGroups.value.length > 1);
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

const writtenDayCount = computed(() => weekDays.value.filter((day) => hasMine(day)).length);

/** 지난 평일인데 일일보고가 없는 날. 초안에 '빠진 요일'로 적힌다. */
const missingDayCount = computed(
    () => weekDays.value.filter((day) => !hasMine(day) && !isFutureDay(day)).length,
);

const createSummary = computed(() => {
    const bits = [`선택 ${selects.value.length}일`];
    if (missingDayCount.value) bits.push(`미제출 ${missingDayCount.value}일은 초안에 표시돼요`);
    return bits.join(" · ");
});

/* ---- 초안 만들기 ----------------------------------------------------- */
/* 초안을 만드는 동안(AI 호출) 일일보고 추출과 같은 기다림 화면을 띄운다. 단계는 경과 시간으로만 넘긴다. */
const DRAFT_STAGES = ["일일보고를 모으고 있어요", "프로젝트별로 묶고 있어요", "주간 문장으로 다듬고 있어요"];
const draftWaiting = ref(false);
const draftElapsed = ref(0);
let draftTimer = null;
const draftStage = computed(() => (draftElapsed.value >= 25 ? 2 : draftElapsed.value >= 8 ? 1 : 0));
const draftElapsedLabel = computed(() => {
    const minutes = Math.floor(draftElapsed.value / 60);
    const seconds = draftElapsed.value % 60;
    return minutes > 0 ? `${minutes}분 ${seconds}초` : `${seconds}초`;
});
const startDraftWait = () => {
    draftElapsed.value = 0;
    draftWaiting.value = true;
    document.documentElement.classList.add("is-overlay-open");
    draftTimer = setInterval(() => {
        draftElapsed.value += 1;
    }, 1000);
};
const stopDraftWait = () => {
    if (draftTimer !== null) clearInterval(draftTimer);
    draftTimer = null;
    if (draftWaiting.value) document.documentElement.classList.remove("is-overlay-open");
    draftWaiting.value = false;
};
onUnmounted(stopDraftWait);

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
    startDraftWait();
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
        stopDraftWait();
        isLoading.value = false;
    }
};

/* ---- 조회 ------------------------------------------------------------ */
/** 고른 기간에 내가 낸 일일보고만 조회해 선택 가능한 날짜를 정한다. */
const loadMyWeek = async () => {
    myDays.value = {};
    weekError.value = "";
    if (!rangeStart.value || !rangeEnd.value || !userId.value) return;
    weekLoading.value = true;
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
        weekError.value = "이 기간의 내 일일보고를 불러오지 못했어요.";
    } finally {
        weekLoading.value = false;
    }
};

const fetchWeeklyReport = async () => {
    if (!userId.value) {
        weeklyReport.value = [];
        return;
    }
    isLoading.value = true;
    listError.value = "";
    try {
        weeklyReport.value = await getWeeklyReport(userId.value);
    } catch (error) {
        console.error("주간 보고서 조회 실패:", error);
        weeklyReport.value = [];
        listError.value = "내 주간 보고서 목록을 불러오지 못했어요.";
    } finally {
        isLoading.value = false;
    }
};

const viewReport = (report) => {
    router.push(`/weekly-detail/${report.id}`);
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

/* ---- 삭제 · 정리 ------------------------------------------------------ */
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

/* ---- 내려받기 -------------------------------------------------------- */
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

        // DOCX 도구(약 600KB)는 내려받을 때만 불러온다.
        const [{ default: PizZip }, { default: Docxtemplater }] = await Promise.all([
            import("pizzip"),
            import("docxtemplater"),
        ]);
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

        saveAs(out, `${fileBaseName(report)}.docx`);
    } catch (error) {
        console.error("보고서 다운로드 실패:", error);
        showAlert("Word 파일을 만들지 못했습니다. 페이지를 새로고침한 뒤 다시 받아 주세요.");
    } finally {
        isLoading.value = false;
    }
};

const downloadPptx = async (report) => {
    if (!report?.id) {
        showAlert("저장된 주간 보고서만 PPT로 받을 수 있습니다.");
        return;
    }
    isLoading.value = true;
    try {
        const blob = await downloadWeeklyPptx(report.id);
        saveAs(blob, `${fileBaseName(report)}.pptx`);
    } catch (error) {
        console.error("PPT 다운로드 실패:", error);
        showAlert("PPT 다운로드 중 오류가 발생했습니다.");
    } finally {
        isLoading.value = false;
    }
};

/* ---- 시작 ------------------------------------------------------------ */
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
    <div class="page weekly-page">
        <!-- 1. 초안 만들기. 이 화면의 초점: 기간 → 날 고르기 → 만들기 한 버튼. -->
        <section class="card board board-create" aria-labelledby="create-title">
            <header class="board-head">
                <h2 id="create-title">주간 초안 만들기</h2>
                <div class="board-tools">
                    <div class="stepper" role="group" aria-label="주 이동">
                        <button type="button" aria-label="이전 주" :disabled="isLoading" @click="prevWeek">
                            <ChevronLeft :size="16" />
                        </button>
                        <button type="button" class="stepper-reset" :disabled="isLoading || isThisWeek" @click="resetThisWeek">
                            이번 주
                        </button>
                        <button type="button" aria-label="다음 주" :disabled="isLoading" @click="nextWeek">
                            <ChevronRight :size="16" />
                        </button>
                    </div>
                    <button
                        type="button"
                        class="btn btn-ghost"
                        :class="{ 'is-active': showRange }"
                        :aria-expanded="showRange"
                        aria-controls="week-range"
                        @click="showRange = !showRange"
                    >
                        기간 지정
                    </button>
                </div>
            </header>

            <p class="view-period create-period">
                {{ headerTitle }}
                <span v-if="isThisWeek" class="chip is-accent">이번 주</span>
            </p>

            <div v-if="showRange" id="week-range" class="range-tray">
                <label>
                    시작
                    <input class="input" type="date" :value="rangeStart" :disabled="isLoading" @change="pickStart($event.target.value)" />
                </label>
                <label>
                    끝
                    <input class="input" type="date" :value="rangeEnd" :disabled="isLoading" @change="pickEnd($event.target.value)" />
                </label>
            </div>

            <div v-if="weekError" class="board-error" role="alert">
                <span>{{ weekError }}</span>
                <button type="button" class="btn btn-small" :disabled="weekLoading" @click="loadMyWeek">다시 시도</button>
            </div>

            <div v-else-if="weekLoading" class="day-tiles is-skeleton" role="status" aria-label="내 일일보고를 불러오는 중">
                <span v-for="n in 5" :key="n" class="day-tile is-placeholder" aria-hidden="true">
                    <span class="skel skel-short"></span>
                    <span class="skel skel-wide"></span>
                    <span class="skel skel-short"></span>
                </span>
            </div>

            <div v-else class="weeks">
                <div v-for="group in weekGroups" :key="group.key" class="week">
                    <button
                        v-if="foldWeeks"
                        type="button"
                        class="week-head"
                        :aria-expanded="openWeek === group.key"
                        @click="openWeek = openWeek === group.key ? '' : group.key"
                    >
                        <span>{{ group.label }}</span>
                        <WeekDots :days="group.dots" />
                        <span class="week-head-meta">{{ group.summary }}</span>
                        <ChevronDown :size="16" :class="{ 'is-open': openWeek === group.key }" />
                    </button>
                    <div v-else-if="showWeekHeads" class="week-head">
                        <span>{{ group.label }}</span>
                        <WeekDots :days="group.dots" />
                        <span class="week-head-meta">{{ group.summary }}</span>
                    </div>
                    <div
                        v-if="!foldWeeks || openWeek === group.key"
                        class="day-tiles"
                        role="group"
                        :aria-label="group.label"
                    >
                        <button
                            v-for="(dayDate, index) in group.days"
                            :key="dayDate"
                            type="button"
                            class="day-tile"
                            :class="{
                                'is-on': isDayOn(dayDate),
                                'is-written': hasMine(dayDate),
                                'is-future': isFutureDay(dayDate),
                            }"
                            :aria-pressed="isDayOn(dayDate)"
                            :disabled="!hasMine(dayDate)"
                            :title="dayTitle(dayDate)"
                            @click="toggleSelectDay(dayDate)"
                        >
                            <span class="tile-day">{{ weekdayName(dayDate) }}</span>
                            <span class="tile-date">{{ shortDay(dayDate) }}</span>
                            <span class="tile-state">
                                <span aria-hidden="true"><WeekDots :days="[group.dots[index]]" /></span>
                                {{ dayState(dayDate) }}
                            </span>
                            <span v-if="isDayOn(dayDate)" class="tile-check" aria-hidden="true">
                                <Check :size="13" :stroke-width="3" />
                            </span>
                        </button>
                    </div>
                </div>
                <p v-if="!writtenDayCount" class="board-note">
                    이 기간에 쓴 일일보고가 없어요. 오늘 보고를 쓰면 여기서 고를 수 있어요.
                    <router-link class="btn btn-ghost btn-small" to="/">오늘 보고 쓰기</router-link>
                </p>
            </div>

            <!-- 같은 주 보고가 이미 있으면 그걸 여는 게 먼저다. 새로 만들기는 보조 버튼으로 내린다. -->
            <div v-if="existingWeekly" class="callout is-warning existing-callout" role="status">
                <div class="callout-text">
                    <p class="callout-title">이 주의 주간보고가 이미 있어요</p>
                    <p class="callout-body">새 초안을 만들면 지금 있는 주간보고가 새 내용으로 바뀌어요.</p>
                </div>
                <button type="button" class="btn btn-primary" :disabled="isLoading" @click="viewReport(existingWeekly.latest)">
                    기존 보고 열기
                </button>
            </div>

            <footer class="board-foot">
                <p class="create-summary">{{ createSummary }}</p>
                <button
                    type="button"
                    class="btn create-btn"
                    :class="{ 'btn-primary': !existingWeekly }"
                    :disabled="isLoading || selects.length === 0"
                    @click="sendDates()"
                >
                    {{ isLoading ? "만드는 중..." : existingWeekly ? "새 초안으로 다시 만들기" : "주간 초안 만들기" }}
                </button>
            </footer>
        </section>

        <!-- 2. 만든 보고서: 주마다 한 줄. 열기는 줄, 내려받기는 줄 안의 버튼. -->
        <section class="card board board-made" aria-labelledby="made-title">
            <header class="board-head">
                <h2 id="made-title">내가 만든 주간 보고서</h2>
                <span v-if="weeklyGroups.length" class="board-meta">{{ weeklyGroups.length }}건</span>
            </header>

            <div v-if="listError" class="board-error" role="alert">
                <span>{{ listError }}</span>
                <button type="button" class="btn btn-small" :disabled="isLoading" @click="fetchWeeklyReport">다시 시도</button>
            </div>

            <div v-else-if="weeklyReport === null" class="board-list" role="status" aria-label="주간 보고서 목록을 불러오는 중">
                <div v-for="n in 2" :key="n" class="skel-row" aria-hidden="true">
                    <span class="skel skel-wide"></span>
                    <span class="skel skel-short"></span>
                </div>
            </div>

            <p v-else-if="weeklyGroups.length === 0" class="board-note">
                아직 만든 주간 보고서가 없어요. 날을 고르고 초안을 만들면 여기에 쌓여요.
            </p>

            <div v-else class="board-list">
                <div
                    v-for="group in weeklyGroups"
                    :key="group.key"
                    class="row made-row"
                    :class="{ 'is-current': existingWeekly && group.key === existingWeekly.key }"
                    role="link"
                    tabindex="0"
                    @click="!isLoading && viewReport(group.latest)"
                    @keydown.enter="!isLoading && viewReport(group.latest)"
                >
                    <span class="row-main">
                        <span class="row-title">{{ group.label }}</span>
                        <span class="row-sub">{{ projectNamesOf(group.latest).join(" · ") || "프로젝트 없음" }}</span>
                    </span>
                    <ChevronRight :size="16" class="row-chevron" aria-hidden="true" />
                    <span class="made-actions" @click.stop @keydown.stop>
                        <button type="button" class="btn btn-small" :disabled="isLoading" @click="downloadReport(group.latest)">
                            <Download :size="14" />
                            Word
                        </button>
                        <button v-if="!isNarrow" type="button" class="btn btn-small" :disabled="isLoading" @click="downloadPptx(group.latest)">
                            <Download :size="14" />
                            PPT
                        </button>
                        <button
                            v-if="group.older.length"
                            type="button"
                            class="btn btn-ghost btn-small"
                            :disabled="isLoading"
                            :title="`같은 주 이전 초안 ${group.older.length}개 지우기`"
                            @click="cleanupOlder(group)"
                        >
                            이전 초안 {{ group.older.length }}개 정리
                        </button>
                        <button
                            type="button"
                            class="row-icon-btn made-delete"
                            :aria-label="`${group.label} 삭제`"
                            title="삭제"
                            :disabled="isLoading"
                            @click="deleteWeekly(group.latest.id)"
                        >
                            <Trash2 :size="16" />
                        </button>
                    </span>
                </div>
            </div>
        </section>

        <!-- 3. 취합: 관리자는 전 부서, 팀장은 자기 부서를 한 PPT로. 팀원에게는 없다. -->
        <WeeklyCollection v-if="isAdmin || leaderTeamId" class="card board board-collect" />
    </div>

    <Teleport to="body">
        <div v-if="draftWaiting" class="submit-wait" role="status" aria-live="polite">
            <div class="submit-wait-card">
                <p class="submit-wait-date">{{ headerTitle }} 주간 초안 · {{ selects.length }}일</p>
                <h2>{{ DRAFT_STAGES[draftStage] }}</h2>
                <div class="submit-meter" aria-hidden="true">
                    <span :style="{ width: ['18%', '52%', '78%'][draftStage] }"></span>
                </div>
                <ol class="submit-steps">
                    <li
                        v-for="(stage, index) in DRAFT_STAGES"
                        :key="stage"
                        :class="{ 'is-done': index < draftStage, 'is-on': index === draftStage }"
                    >
                        {{ stage }}
                    </li>
                </ol>
                <p class="submit-wait-time">{{ draftElapsedLabel }} 지났어요 · 끝나면 초안 화면으로 넘어가요</p>
            </div>
        </div>
    </Teleport>
</template>

<style scoped src="../styles/components/weekly-report.css"></style>
