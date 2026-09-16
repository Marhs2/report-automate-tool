# UI 대규모 개선 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 베이지·올리브 톤을 유지하면서 디자인 토큰 레이어를 도입하고, 앱 셸(사이드바 접기·탑바 경로·페이지 헤더·오버레이 드로어)을 재구성한다.

**Architecture:** `frontend/src/styles/` 아래에 토큰·기반·셸·공통 컴포넌트·문서형 스타일을 분리하고 `style.css`는 import 진입점으로만 남긴다. 화면 제목·액션·활성 내비게이션 판정은 `router/index.js`의 라우트 `meta`로 옮겨 `App.vue`의 경로 정규식 분기를 제거한다. 개별 화면은 페이지 헤더 마크업만 교체하고 scoped CSS의 값을 토큰으로 치환한다.

**Tech Stack:** Vue 3.5 (SFC, `<script setup>`), Vue Router 5, Vite 8, lucide-vue-next 아이콘, 순수 CSS(프레임워크 없음)

## Global Constraints

- 색 톤 유지: 페이지 배경은 `#f7f2eb` 계열, 액센트는 올리브 `#8b9a6e` / 호버 `#738056`를 기준으로 한다.
- **그림자를 도입하지 않는다.** 표면 구분은 배경 밝기 차이와 테두리 2단계로만 처리한다. 기존 `--shadow`, `--shadow-raised` 토큰은 최종적으로 제거한다.
- `font-weight`는 500·600·700만 사용한다. 기존 `650`은 모두 `600`으로, `400`은 본문 기본값이므로 선언을 제거한다.
- 간격은 `--space-*` 스케일(4·8·12·16·20·24·32·48px)만 사용한다. 기존 6px→8px, 10px→8px 또는 12px, 14px→12px 또는 16px, 18px→16px, 28px→24px 또는 32px로 흡수한다. 1·2·3·5px 같은 미세 값(테두리 보정, 아이콘 정렬)은 예외로 허용한다.
- 버튼은 `--radius-pill`을 유지하고, 입력 필드(`.input`, `select`, `textarea`)는 `--radius`(12px)를 쓴다.
- 한국어 가독성을 위해 기존 `word-break: keep-all`은 제거하지 않는다.
- `prefers-reduced-motion: reduce` 블록은 유지한다.
- 화면의 기능 로직(스크립트 블록, 조건부 렌더링, API 호출)은 변경하지 않는다. 예외는 Task 3·4·5의 `App.vue`와 `router/index.js`다.
- 백엔드(`backend/`)는 건드리지 않는다.
- 작업 브랜치는 `ui-redesign`이다. 복귀 지점은 `main`의 `58a06a5` 커밋이다.
- 테스트 프레임워크가 없는 프로젝트이므로 각 태스크의 검증은 `npm run build` 성공과 브라우저 육안·콘솔 확인으로 한다.

---

## 사전 확인 (모든 태스크 공통)

작업 디렉터리는 `frontend/`다. 명령은 다음 위치에서 실행한다.

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool/frontend
```

빌드 검증 명령과 기대 결과:

```bash
npm run build
```

기대: `vite v8.x building for production...` 이후 `✓ built in ...` 출력, 종료 코드 0. CSS 문법 오류나 해결되지 않은 import가 있으면 여기서 실패한다.

브라우저 검증이 필요한 태스크에서는 개발 서버를 띄운다.

```bash
npm run dev
```

기대: `Local: http://localhost:5173/` 출력. 확인할 경로는 다음 10개다.

| 경로 | 화면 |
| --- | --- |
| `/users` | 사용자 선택 |
| `/` | 일일보고 목록 |
| `/report` | 보고서 작성 |
| `/report-result` | 분석 결과 |
| `/weekly` | 주간 보고서 |
| `/weekly-detail/1` | 주간 상세 |
| `/activities` | 사용자 활동 |
| `/project-timeline` | 프로젝트 흐름 |
| `/project-name` | 프로젝트명 관리 |
| `/team-select` | 팀 선택 |

백엔드가 꺼져 있으면 목록이 비어 있는 것은 정상이다. 확인 대상은 레이아웃이 깨지지 않는지와 콘솔에 Vue 경고·에러가 없는지다.

---

## File Structure

**생성**

| 파일 | 책임 |
| --- | --- |
| `frontend/src/styles/tokens.css` | CSS 커스텀 프로퍼티 정의만 |
| `frontend/src/styles/base.css` | 리셋, 요소 기본 타이포, 스크롤바, 선택 영역, 포커스 링, reduced-motion |
| `frontend/src/styles/shell.css` | `#app`, 사이드바, 내일 할 일 카드, 사이드바 푸터, 탑바, 드로어, `.page` 컨테이너 |
| `frontend/src/styles/components.css` | 버튼, 입력·필드, 카드, 툴바, 칩, 상태 배너, 빈 상태, 토스트, 모달, 공용 목록·필터 패턴 |
| `frontend/src/styles/report-doc.css` | `.report-doc` 문서형 화면 공용 스타일 |
| `frontend/src/components/ui/AppPageHeader.vue` | 제목·설명·필터·액션 4자리 페이지 헤더 |
| `frontend/src/composables/useSidebar.js` | 사이드바 접힘·드로어 상태와 `localStorage` 영속화 |

**수정**

| 파일 | 변경 내용 |
| --- | --- |
| `frontend/src/style.css` | 1,247줄을 위 5개 파일로 이전하고 import 진입점만 남김 |
| `frontend/src/router/index.js` | 각 라우트에 `meta` 추가 |
| `frontend/src/App.vue` | `pageMeta`·`isNavActive` 메타 기반 교체, 사이드바 토글·드로어 마크업 추가 |
| `frontend/src/components/*.vue` (10개) | 페이지 헤더 마크업 교체, scoped CSS 토큰화 |

---

## Task 1: 토큰 정의와 CSS 파일 분리

이 태스크는 **시각적 변화를 만들지 않는다.** 파일만 나누고 토큰을 추가하며, 기존 토큰 이름은 별칭으로 남겨 어떤 선택자도 깨지지 않게 한다. 실제 스타일 변경은 Task 2부터다.

**Files:**
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/styles/base.css`
- Create: `frontend/src/styles/shell.css`
- Create: `frontend/src/styles/components.css`
- Create: `frontend/src/styles/report-doc.css`
- Modify: `frontend/src/style.css` (전체 교체)

**Interfaces:**
- Produces: 이후 모든 태스크가 사용하는 토큰 이름 — `--bg`, `--surface`, `--surface-soft`, `--border`, `--border-strong`, `--text-strong`, `--text`, `--text-muted`, `--accent`, `--accent-hover`, `--accent-soft`, `--accent-border`, `--success-fg|bg|border`, `--warning-fg|bg|border`, `--danger-fg|bg|border`, `--info-fg|bg|border`, `--space-1`~`--space-8`, `--fs-11`~`--fs-30`, `--lh-tight`, `--lh-base`, `--lh-relaxed`, `--fw-medium`, `--fw-semibold`, `--fw-bold`, `--radius-sm`, `--radius`, `--radius-lg`, `--radius-pill`, `--dur-fast`, `--dur`, `--ease`, `--sidebar-width`, `--sidebar-width-collapsed`, `--topbar-height`, `--content-max`, `--content-max-wide`

- [ ] **Step 1: `tokens.css` 작성**

```css
:root {
    /* 표면 */
    --bg: #f7f2eb;
    --surface: #fffdf8;
    --surface-soft: #f2ece3;

    /* 테두리 */
    --border: #e6ddcf;
    --border-strong: #d6c9b4;

    /* 텍스트 */
    --text-strong: #1f1d18;
    --text: #6b655a;
    --text-muted: #8f887b;

    /* 액센트 */
    --accent: #8b9a6e;
    --accent-hover: #738056;
    --accent-soft: #eef1e5;
    --accent-border: #c3ccae;

    /* 상태 */
    --success-fg: #5f7a3f;
    --success-bg: #eef2e4;
    --success-border: #c9d5ad;
    --warning-fg: #9a6a1b;
    --warning-bg: #faf0dd;
    --warning-border: #e6cfa3;
    --danger-fg: #b3382f;
    --danger-bg: #fbeae8;
    --danger-border: #eec4bf;
    --info-fg: #4a6b7c;
    --info-bg: #e9f0f3;
    --info-border: #bdd2db;

    /* 간격 */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 20px;
    --space-6: 24px;
    --space-7: 32px;
    --space-8: 48px;

    /* 타이포 */
    --sans: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", ui-sans-serif, system-ui, sans-serif;
    --heading: "SF Pro Rounded", ui-rounded, "Hiragino Sans", var(--sans);
    --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    --fs-11: 11px;
    --fs-12: 12px;
    --fs-13: 13px;
    --fs-14: 14px;
    --fs-16: 16px;
    --fs-20: 20px;
    --fs-24: 24px;
    --fs-30: 30px;
    --lh-tight: 1.25;
    --lh-base: 1.5;
    --lh-relaxed: 1.65;
    --fw-medium: 500;
    --fw-semibold: 600;
    --fw-bold: 700;

    /* 형태 */
    --radius-sm: 8px;
    --radius: 12px;
    --radius-lg: 16px;
    --radius-pill: 9999px;

    /* 모션 */
    --dur-fast: 0.12s;
    --dur: 0.2s;
    --ease: cubic-bezier(0.2, 0.6, 0.3, 1);

    /* 레이아웃 */
    --sidebar-width: 272px;
    --sidebar-width-collapsed: 64px;
    --topbar-height: 56px;
    --content-max: 1120px;
    --content-max-wide: 1280px;

    /* 스크롤바 */
    --scrollbar-thumb: rgba(139, 154, 110, 0.35);

    /* --- 마이그레이션 별칭: Task 7에서 제거한다 --- */
    --text-h: var(--text-strong);
    --bg-elevated: var(--surface);
    --bg-soft: var(--surface-soft);
    --code-bg: var(--surface-soft);
    --social-bg: var(--surface-soft);
    --accent-bg: var(--accent-soft);
    --danger: var(--danger-fg);
    --success: var(--success-fg);
    --warning: var(--warning-fg);
    --shadow: none;
    --shadow-raised: none;
}
```

- [ ] **Step 2: 기존 `style.css`를 주제별로 5개 파일에 분배**

원본 `frontend/src/style.css`의 현재 내용을 다음 경계로 잘라 옮긴다. 선택자와 선언은 **한 글자도 바꾸지 않고** 그대로 이동시킨다(값 변경은 Task 2 이후).

- `base.css` ← 원본 42~144행 영역: `*, *::before, *::after`, `body`, `::selection`, `:focus-visible`, 스크롤바 규칙, `@media (prefers-reduced-motion)`, `h1`~`h4`, `p`, `code`
- `shell.css` ← 원본 146~275행(`#app`, `.sidebar`, `.nav-*`, `.main-content`, `.topbar`, `.topbar-title`, `.main-body`), 277~584행(`.tomorrow-*`, `.sidebar-footer`, `.sidebar-user*`, `.sidebar-avatar`, `.sidebar-logout`), 586~622행(`.page`, `.page-header`, `.page-subtitle`), 858~967행의 `@media (max-width: 860px)` 중 셸 관련 규칙
- `components.css` ← 원본 624~856행(`.card`, `.toolbar`, `.field`, `.input`/`.textarea` 및 관련 hover·focus, `::placeholder`, `select`, `input[type=date]`, `input[type=file]`, `.btn` 계열, `.empty-state`), 969~1084행(`.toast*`, `.app-dialog*`, `.status-banner`, `.status-chip`), 858~967행 미디어쿼리 중 `.page`·`h1` 관련 규칙
- `report-doc.css` ← 원본 1086~1248행 전체(`.report-doc` 이하 및 해당 미디어쿼리)
- `:root` 블록(원본 1~41행)은 `tokens.css`로 대체되었으므로 옮기지 않는다. 단 원본 `:root`에 있던 `font`, `letter-spacing`, `color-scheme`, `accent-color`, `color`, `background`, `font-synthesis`, `text-rendering`, 폰트 스무딩 선언은 `base.css` 최상단의 `:root` 블록으로 옮긴다.

```css
/* base.css 최상단 */
:root {
    font: var(--fs-16) / var(--lh-base) var(--sans);
    letter-spacing: 0;
    color-scheme: light;
    accent-color: var(--accent);
    color: var(--text);
    background: var(--bg);
    font-synthesis: none;
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
```

- [ ] **Step 3: `style.css`를 진입점으로 교체**

```css
@import "./styles/tokens.css";
@import "./styles/base.css";
@import "./styles/shell.css";
@import "./styles/components.css";
@import "./styles/report-doc.css";
```

`main.js`는 이미 `./style.css`를 불러오므로 수정할 필요가 없다.

- [ ] **Step 4: 원본과 선택자 누락이 없는지 확인**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool/frontend
git show main:frontend/src/style.css | grep -c "^[.#*a-zA-Z:@]"
cat src/styles/*.css | grep -c "^[.#*a-zA-Z:@]"
```

기대: 두 숫자가 비슷해야 한다(`:root` 재구성으로 몇 줄 차이는 정상). 크게 줄었다면 블록을 통째로 빠뜨린 것이다. 의심되면 원본의 각 선택자 이름이 새 파일 어딘가에 있는지 확인한다.

```bash
git show main:frontend/src/style.css | grep -o "^\.[a-z-]*" | sort -u > /tmp/old-selectors.txt
cat src/styles/*.css | grep -o "^\.[a-z-]*" | sort -u > /tmp/new-selectors.txt
diff /tmp/old-selectors.txt /tmp/new-selectors.txt
```

기대: 출력 없음(차이 없음).

- [ ] **Step 5: 빌드 검증**

```bash
npm run build
```

기대: 성공, 종료 코드 0.

- [ ] **Step 6: 브라우저에서 시각적 회귀가 없는지 확인**

`npm run dev` 후 `/`, `/report`, `/weekly`를 열어 이 태스크 이전과 화면이 동일한지 본다. 기대: 변화 없음. 무언가 무너졌다면 옮기다 빠뜨린 블록이 있다.

- [ ] **Step 7: 커밋**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool
git add frontend/src/style.css frontend/src/styles
git commit -m "style: extract design tokens and split global CSS"
```

---

## Task 2: 공통 컴포넌트 스타일 재조정

**Files:**
- Modify: `frontend/src/styles/components.css`
- Modify: `frontend/src/styles/base.css`

**Interfaces:**
- Consumes: Task 1의 토큰 전체
- Produces: 이후 화면들이 기대하는 공용 클래스 동작 — `.btn`(pill), `.btn-primary`, `.btn-small`, `.btn-danger`, `.input`/`.textarea`(반경 12px), `.card`(`--surface` 배경), `.chip`(신규, 중립 칩), `.count-chip`(전역으로 승격), `.status-chip.is-saved|is-draft`, `.empty-state`, `.toast-success|error`, `.app-dialog`

- [ ] **Step 1: 표면과 테두리 적용**

`.card`의 배경을 `var(--bg)`에서 `var(--surface)`로 바꾼다. `box-shadow: none` 선언은 삭제한다(기본값이며 그림자를 쓰지 않으므로 불필요하다). 패딩은 `var(--space-5)`로 한다.

```css
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: var(--space-5);
}
```

- [ ] **Step 2: 입력 필드 반경과 간격 토큰화**

`.input`, `.textarea`, `.field > input/select/textarea` 공용 규칙의 `border-radius`를 `var(--radius-pill)`에서 `var(--radius)`로 바꾸고, 패딩을 `var(--space-2) var(--space-3)`으로, 배경을 `var(--surface)`로 바꾼다. hover는 `--border-strong`, focus는 `--accent-border` + `--accent`를 쓴다.

```css
.input,
.textarea,
.field > input:not([type="checkbox"]):not([type="radio"]),
.field > select,
.field > textarea {
    width: 100%;
    font: inherit;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--text-strong);
    outline: none;
    transition: border-color var(--dur-fast) var(--ease);
}
```

hover 셀렉터 그룹은 `border-color: var(--border-strong)`, focus 셀렉터 그룹은 `border-color: var(--accent)`로 바꾼다. `.textarea`의 `border-radius: var(--radius)` 재선언은 이제 중복이므로 삭제하고 `min-height: 200px`과 `line-height: var(--lh-relaxed)`만 남긴다.

- [ ] **Step 3: 버튼 정리**

`.btn`은 pill을 유지한다. `box-shadow: none`과 `.btn-primary`의 `box-shadow: none`을 삭제한다. 패딩은 `var(--space-2) var(--space-5)`, `font-weight`는 `var(--fw-medium)`, transition은 `var(--dur-fast) var(--ease)`를 쓴다. `.btn-small`은 `var(--space-1) var(--space-3)`과 높이 32px을 유지한다. `.btn-danger`는 `color: var(--danger-fg)`, hover 배경 `var(--danger-bg)`를 쓴다. `.btn:hover` 배경은 `var(--surface-soft)`, 기본 배경은 `var(--surface)`로 한다.

- [ ] **Step 4: 칩 패턴 전역 승격**

`project-name.vue`(561행)와 `projects-list.vue`(536행)에 각각 정의된 `.count-chip`을 `components.css`로 올린다. 중립 칩 `.chip`도 함께 정의해 이후 화면들이 재사용하게 한다.

```css
.chip,
.count-chip {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 2px var(--space-2);
    border-radius: var(--radius-pill);
    background: var(--surface-soft);
    color: var(--text);
    font-size: var(--fs-12);
    font-weight: var(--fw-semibold);
    line-height: var(--lh-tight);
    white-space: nowrap;
}

.chip.is-accent,
.count-chip {
    background: var(--accent-soft);
    color: var(--accent-hover);
}
```

- [ ] **Step 5: 상태 색을 새 토큰으로 교체**

`.status-chip.is-saved`, `.status-chip.is-draft`, `.toast-success`, `.toast-error`의 `color-mix(...)` 표현식을 상태 토큰으로 바꾼다.

```css
.status-chip.is-saved {
    background: var(--success-bg);
    border: 1px solid var(--success-border);
    color: var(--success-fg);
}

.status-chip.is-draft {
    background: var(--warning-bg);
    border: 1px solid var(--warning-border);
    color: var(--warning-fg);
}

.toast-success {
    background: var(--success-bg);
    border-color: var(--success-border);
    color: var(--success-fg);
}

.toast-error {
    background: var(--danger-bg);
    border-color: var(--danger-border);
    color: var(--danger-fg);
}
```

`.toast`의 `box-shadow: none`은 삭제하고 배경을 `var(--surface)`로 한다. 그림자를 쓰지 않으므로 토스트는 `border: 1px solid var(--border-strong)`로 떠 있는 느낌을 준다.

- [ ] **Step 6: 모달과 빈 상태**

`.app-dialog-overlay` 배경은 `rgba(38, 37, 30, 0.28)`을 유지한다. `.app-dialog-kicker`의 `font-weight: 650`을 `var(--fw-semibold)`로 바꾼다. `.empty-state`는 배경 `var(--surface)`, 패딩 `var(--space-8) var(--space-6)`, 색 `var(--text-muted)`로 조정한다.

- [ ] **Step 7: 남은 `650`과 하드코딩 값 제거**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool/frontend
grep -rn "font-weight: 650" src/styles/
```

기대: 출력 없음. 남아 있으면 `var(--fw-semibold)`로 바꾼다. `base.css`의 `h1`~`h4`도 `font-weight: var(--fw-medium)`과 `--fs-*` 토큰을 쓰도록 바꾸고, `code`는 `background: var(--surface-soft)`를 쓴다.

- [ ] **Step 8: 빌드와 브라우저 확인**

```bash
npm run build
```

기대: 성공. `npm run dev` 후 `/report`(입력·버튼·상태 배너), `/weekly`(카드·칩), `/project-name`(카운트 칩)을 열어 입력 필드가 12px 반경으로 바뀌고 카드가 배경과 구분되는지 확인한다.

- [ ] **Step 9: 커밋**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool
git add frontend/src/styles
git commit -m "style: retune shared component styles on tokens"
```

---

## Task 3: 라우터 메타와 탑바 경로 표시

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/App.vue:64-89` (`pageMeta`, `isNavActive`), `frontend/src/App.vue:377-383` (탑바 마크업)
- Modify: `frontend/src/styles/shell.css` (`.topbar*`)

**Interfaces:**
- Consumes: Task 1 토큰
- Produces: 라우트 `meta` 형태 `{ title: string, navKey?: string, parent?: { to: string, label: string }, action?: { to: string, label: string } }`. Task 4·5·6이 `route.meta`를 읽는다.

- [ ] **Step 1: 라우트에 `meta` 추가**

`frontend/src/router/index.js`의 각 컴포넌트 라우트에 `meta`를 넣는다. 리다이렉트 전용 라우트(`/weekly-report`, `/report/:id`)는 그대로 둔다.

```js
const routes = [
  {
    path: "/",
    name: "",
    component: projectList,
    meta: {
      title: "일일보고",
      navKey: "/",
      action: { to: "/report", label: "보고서 작성" },
    },
  },
  {
    path: "/report",
    name: "report",
    component: report,
    meta: { title: "보고서 작성", navKey: "/report" },
  },
  {
    path: "/report-result/:id?",
    name: "report-result",
    component: reportResult,
    meta: {
      title: "분석 결과",
      navKey: "/",
      parent: { to: "/", label: "일일보고" },
    },
  },
  {
    path: "/activities",
    name: "activities",
    component: activities,
    meta: {
      title: "사용자 활동",
      navKey: "/activities",
      action: { to: "/report", label: "보고서 작성" },
    },
  },
  {
    path: "/weekly",
    name: "weekly",
    component: weekly,
    meta: { title: "주간 보고서", navKey: "/weekly" },
  },
  { path: "/weekly-report", redirect: "/weekly" },
  {
    path: "/users",
    name: "users",
    component: users,
    meta: { title: "사용자 선택", navKey: "/users" },
  },
  {
    path: "/weekly-detail/:id",
    name: "weekly-detail",
    component: weeklyDetail,
    meta: {
      title: "주간 상세",
      navKey: "/weekly",
      parent: { to: "/weekly", label: "주간 보고서" },
    },
  },
  {
    path: "/report/:id",
    redirect: (to) => ({ name: "report-result", params: { id: to.params.id } }),
  },
  {
    path: "/project-timeline",
    name: "project-timeline",
    component: projectTimeline,
    meta: { title: "프로젝트 흐름", navKey: "/project-timeline" },
  },
  {
    path: "/project-name",
    name: "project-name",
    component: projectName,
    meta: { title: "프로젝트명 관리", navKey: "/project-name" },
  },
  {
    path: "/team-select",
    name: "team-select",
    component: teamSelect,
    meta: { title: "팀 선택", navKey: "/team-select" },
  },
];
```

- [ ] **Step 2: `App.vue`의 `pageMeta`와 `isNavActive` 교체**

기존 `pageMeta` 계산 속성(64~80행)과 `isNavActive`(82~89행)를 삭제하고 다음으로 대체한다.

```js
const pageMeta = computed(() => ({
    title: route.meta.title || "일일보고",
    parent: route.meta.parent || null,
    action: route.meta.action || null,
}));

const isNavActive = (to) => route.meta.navKey === to;
```

- [ ] **Step 3: 탑바 마크업 교체**

`App.vue`의 `<header class="topbar">` 블록을 다음으로 바꾼다. `Menu` 아이콘은 Task 5에서 쓰므로 여기서는 넣지 않는다.

```html
<header class="topbar">
    <nav class="topbar-crumbs" aria-label="현재 위치">
        <router-link v-if="pageMeta.parent" class="topbar-crumb" :to="pageMeta.parent.to">
            {{ pageMeta.parent.label }}
        </router-link>
        <span v-if="pageMeta.parent" class="topbar-crumb-sep" aria-hidden="true">›</span>
        <span class="topbar-title" aria-current="page">{{ pageMeta.title }}</span>
    </nav>
    <router-link v-if="pageMeta.action" class="btn btn-primary btn-small" :to="pageMeta.action.to">
        {{ pageMeta.action.label }}
    </router-link>
</header>
```

- [ ] **Step 4: 탑바 스타일 추가**

`shell.css`의 `.topbar` 규칙에 이어 다음을 넣는다. `.topbar`의 `min-height: 56px`은 `var(--topbar-height)`로, 패딩은 `0 var(--space-7)`로 바꾸고 배경은 `var(--bg)`를 유지한다.

```css
.topbar-crumbs {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
}

.topbar-crumb {
    color: var(--text-muted);
    text-decoration: none;
    font-size: var(--fs-13);
    font-weight: var(--fw-medium);
    white-space: nowrap;
}

.topbar-crumb:hover {
    color: var(--text-strong);
}

.topbar-crumb-sep {
    color: var(--text-muted);
    font-size: var(--fs-13);
}

.topbar-title {
    margin: 0;
    font-family: var(--heading);
    font-size: var(--fs-16);
    font-weight: var(--fw-medium);
    line-height: var(--lh-tight);
    color: var(--text-strong);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
```

- [ ] **Step 5: 브라우저 확인**

`npm run dev` 후 확인한다.

- `/` → 탑바에 "일일보고"와 우측 "보고서 작성" 버튼
- `/report-result/1` → "일일보고 › 분석 결과", 상위 링크 클릭 시 목록으로 이동
- `/weekly-detail/1` → "주간 보고서 › 주간 상세"
- `/weekly-detail/1`에서 사이드바의 "주간 보고서" 항목이 활성 상태로 표시(이전에는 `navKey` 없이 경로 접두어로 판정했다)
- 콘솔 에러 없음

- [ ] **Step 6: 빌드와 커밋**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool/frontend && npm run build
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool
git add frontend/src/router/index.js frontend/src/App.vue frontend/src/styles/shell.css
git commit -m "feat: drive page title and nav state from route meta"
```

---

## Task 4: 사이드바 접기

**Files:**
- Create: `frontend/src/composables/useSidebar.js`
- Modify: `frontend/src/App.vue` (사이드바 상단 브랜드·토글 영역 추가, 295행 부근의 빈 공간)
- Modify: `frontend/src/styles/shell.css` (`.sidebar`, `.nav-*`, `.tomorrow-card`, `.sidebar-footer`)

**Interfaces:**
- Consumes: Task 1 토큰, Task 3의 `route.meta`
- Produces: `useSidebar()` — `{ collapsed: Ref<boolean>, toggleCollapsed: () => void, drawerOpen: Ref<boolean>, openDrawer: () => void, closeDrawer: () => void }`. Task 5가 `drawerOpen`·`openDrawer`·`closeDrawer`를 사용한다.

- [ ] **Step 1: `useSidebar.js` 작성**

기존 `composables/useSelectedUser.js` 패턴(모듈 스코프 `ref` 공유)을 따른다.

```js
import { ref, watch } from "vue";

const STORAGE_KEY = "sidebarCollapsed";

const readCollapsed = () => {
    try {
        return localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
        return false;
    }
};

const collapsed = ref(readCollapsed());
const drawerOpen = ref(false);

watch(collapsed, (value) => {
    try {
        localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
    } catch {
        /* 저장 실패는 무시한다 */
    }
});

export function useSidebar() {
    return {
        collapsed,
        toggleCollapsed: () => {
            collapsed.value = !collapsed.value;
        },
        drawerOpen,
        openDrawer: () => {
            drawerOpen.value = true;
        },
        closeDrawer: () => {
            drawerOpen.value = false;
        },
    };
}

export default useSidebar;
```

- [ ] **Step 2: `App.vue`에 브랜드·토글 영역 추가**

`PanelLeftClose`, `PanelLeftOpen` 아이콘을 `lucide-vue-next` import에 추가하고 `useSidebar`를 불러온다.

```js
import { PanelLeftClose, PanelLeftOpen } from "lucide-vue-next";
import { useSidebar } from "./composables/useSidebar";

const { collapsed, toggleCollapsed, drawerOpen, openDrawer, closeDrawer } = useSidebar();
```

`<aside class="sidebar">`에 상태 클래스를 붙이고, 현재 비어 있는 상단(297행 부근)에 브랜드 행을 넣는다.

```html
<aside class="sidebar" :class="{ 'is-collapsed': collapsed }">
    <div class="sidebar-brand">
        <span v-if="!collapsed" class="sidebar-brand-name">일일보고</span>
        <button
            type="button"
            class="sidebar-collapse-btn"
            :aria-label="collapsed ? '사이드바 펼치기' : '사이드바 접기'"
            :title="collapsed ? '사이드바 펼치기' : '사이드바 접기'"
            @click="toggleCollapsed"
        >
            <PanelLeftOpen v-if="collapsed" :size="16" />
            <PanelLeftClose v-else :size="16" />
        </button>
    </div>
    ...
```

내비게이션 링크에 접힌 상태용 툴팁과 라벨 조건을 넣는다.

```html
<router-link
    v-for="item in group.items"
    :key="item.to"
    :to="item.to"
    class="nav-link"
    :class="{ 'router-link-exact-active': isNavActive(item.to) }"
    :title="collapsed ? item.label : null"
>
    <component :is="item.icon" :size="16" />
    <span v-if="!collapsed" class="nav-link-label">{{ item.label }}</span>
</router-link>
```

- [ ] **Step 3: 접힘 상태 스타일**

`shell.css`에 추가한다. `.sidebar`의 `flex: 0 0 var(--sidebar-width)`는 유지하고 전환을 넣는다.

```css
.sidebar {
    transition: flex-basis var(--dur) var(--ease);
}

.sidebar.is-collapsed {
    flex-basis: var(--sidebar-width-collapsed);
    padding-left: var(--space-2);
    padding-right: var(--space-2);
}

.sidebar-brand {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    min-height: 32px;
    padding: 0 var(--space-1) 0 var(--space-3);
}

.sidebar.is-collapsed .sidebar-brand {
    justify-content: center;
    padding: 0;
}

.sidebar-brand-name {
    font-family: var(--heading);
    font-size: var(--fs-14);
    font-weight: var(--fw-semibold);
    color: var(--text-strong);
    white-space: nowrap;
}

.sidebar-collapse-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
}

.sidebar-collapse-btn:hover {
    background: var(--surface-soft);
    color: var(--text-strong);
}

.sidebar.is-collapsed .nav-link {
    justify-content: center;
    padding: var(--space-2);
}

.sidebar.is-collapsed .nav-group-label,
.sidebar.is-collapsed .tomorrow-card,
.sidebar.is-collapsed .sidebar-user-meta {
    display: none;
}

.sidebar.is-collapsed .sidebar-user {
    justify-content: center;
    padding: var(--space-2) 0;
}

.sidebar.is-collapsed .sidebar-logout {
    justify-content: center;
    padding: var(--space-2);
}

.sidebar.is-collapsed .sidebar-logout span {
    display: none;
}
```

`App.vue`의 `.sidebar-logout` 내부 텍스트 "사용자 변경"을 `<span>사용자 변경</span>`으로 감싸 위 규칙이 적용되게 한다. 접힌 상태에서는 `:title="collapsed ? '사용자 변경' : null"`을 준다.

- [ ] **Step 4: 브라우저 확인**

`npm run dev` 후 확인한다.

- 토글 버튼으로 272px ↔ 64px 전환
- 접힌 상태에서 아이콘 위에 마우스를 올리면 라벨 툴팁이 뜬다
- 접힌 상태에서 "내일 할 일" 카드와 사용자 이름·팀이 숨는다
- 새로고침(F5) 후에도 접힘 상태가 유지된다
- 콘솔 에러 없음

- [ ] **Step 5: 빌드와 커밋**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool/frontend && npm run build
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool
git add frontend/src/composables/useSidebar.js frontend/src/App.vue frontend/src/styles/shell.css
git commit -m "feat: add collapsible sidebar with persisted state"
```

---

## Task 5: 좁은 화면 오버레이 드로어

**Files:**
- Modify: `frontend/src/App.vue` (햄버거 버튼, 오버레이, 라우트 변화 감지, `Escape` 처리)
- Modify: `frontend/src/styles/shell.css` (`@media (max-width: 860px)` 블록 재작성)

**Interfaces:**
- Consumes: Task 4의 `useSidebar()`의 `drawerOpen`, `openDrawer`, `closeDrawer`

- [ ] **Step 1: 탑바에 햄버거 버튼 추가**

`Menu` 아이콘을 import하고 Task 3에서 만든 `.topbar` 안, `.topbar-crumbs` 앞에 넣는다.

```html
<button
    type="button"
    class="topbar-drawer-btn"
    aria-label="메뉴 열기"
    @click="openDrawer"
>
    <Menu :size="18" />
</button>
```

- [ ] **Step 2: 오버레이와 상태 클래스**

`<aside class="sidebar">`의 클래스 바인딩에 드로어 상태를 추가한다.

```html
<aside class="sidebar" :class="{ 'is-collapsed': collapsed, 'is-drawer-open': drawerOpen }">
```

`</aside>` 바로 뒤에 오버레이를 넣는다.

```html
<div v-if="drawerOpen" class="sidebar-overlay" @click="closeDrawer" />
```

- [ ] **Step 3: 라우트 이동과 `Escape`로 닫기**

`App.vue`의 기존 `watch(() => route.path, ...)`(249~252행)에 드로어 닫기를 추가한다.

```js
watch(
    () => route.path,
    () => {
        loadTomorrowPlans(selectedUserId.value);
        closeDrawer();
    },
);
```

기존 `onDialogKeydown`은 다이얼로그 전용이므로 건드리지 않고, 드로어용 처리를 분리해 같은 리스너 안에서 먼저 처리한다. `onDialogKeydown` 함수 본문 첫 줄에 다음을 넣는다.

```js
if (event.key === "Escape" && drawerOpen.value) {
    event.preventDefault();
    closeDrawer();
    return;
}
```

- [ ] **Step 4: 미디어쿼리 재작성**

`shell.css`의 `@media (max-width: 860px)` 블록에서 사이드바를 가로 탭 줄로 바꾸던 규칙(`flex-direction: row`, `.nav-links { flex-direction: row; overflow-x: auto }`, `.nav-group { flex-direction: row }`, `.nav-group-label { display: none }`, `.tomorrow-card { display: none }`, `.sidebar-footer` 가로 배치, `.sidebar-user-name/-team { display: none }`)을 모두 삭제하고 다음으로 대체한다.

```css
@media (max-width: 860px) {
    #app {
        display: block;
    }

    .sidebar {
        position: fixed;
        top: 0;
        left: 0;
        z-index: 60;
        width: var(--sidebar-width);
        max-width: 84vw;
        height: 100vh;
        flex-basis: auto;
        border-right: 1px solid var(--border);
        transform: translateX(-100%);
        transition: transform var(--dur) var(--ease);
    }

    .sidebar.is-drawer-open {
        transform: translateX(0);
    }

    /* 좁은 화면에서는 접힘 상태를 무시하고 항상 전체 메뉴를 보여준다 */
    .sidebar.is-collapsed {
        flex-basis: auto;
        padding-left: var(--space-3);
        padding-right: var(--space-3);
    }

    .sidebar.is-collapsed .nav-group-label,
    .sidebar.is-collapsed .tomorrow-card,
    .sidebar.is-collapsed .sidebar-user-meta {
        display: revert;
    }

    .sidebar.is-collapsed .nav-link,
    .sidebar.is-collapsed .sidebar-logout {
        justify-content: flex-start;
        padding: var(--space-2) var(--space-3);
    }

    .sidebar.is-collapsed .sidebar-logout span {
        display: revert;
    }

    .sidebar-collapse-btn {
        display: none;
    }

    .sidebar-overlay {
        position: fixed;
        inset: 0;
        z-index: 50;
        background: rgba(38, 37, 30, 0.28);
    }

    .topbar-drawer-btn {
        display: inline-flex;
    }

    .main-content {
        height: auto;
        overflow: visible;
    }

    .main-body {
        overflow: visible;
    }

    .topbar {
        padding: 0 var(--space-4);
    }

    .page {
        padding: var(--space-5) var(--space-4) var(--space-8);
    }
}
```

햄버거 버튼은 넓은 화면에서 숨긴다.

```css
.topbar-drawer-btn {
    display: none;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    margin-right: var(--space-2);
    padding: 0;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text);
    cursor: pointer;
}

.topbar-drawer-btn:hover {
    background: var(--surface-soft);
    color: var(--text-strong);
}
```

- [ ] **Step 5: 브라우저 확인**

브라우저 창을 860px 이하로 좁히거나 개발자 도구의 반응형 모드로 확인한다.

- 탑바 좌측에 햄버거가 나타나고 사이드바는 화면에서 사라진다
- 햄버거 클릭 시 드로어가 왼쪽에서 슬라이드되어 열리고, 전체 내비게이션과 "내일 할 일" 카드가 보인다
- 오버레이 클릭, `Escape`, 메뉴 항목 클릭으로 드로어가 닫힌다
- 창을 다시 넓히면 사이드바가 원래 자리로 돌아오고 햄버거가 사라진다
- 콘솔 에러 없음

- [ ] **Step 6: 빌드와 커밋**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool/frontend && npm run build
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool
git add frontend/src/App.vue frontend/src/styles/shell.css
git commit -m "feat: replace mobile nav strip with overlay drawer"
```

---

## Task 6: 페이지 헤더 통일과 본문 폭

현재 `.page-header` 안의 `h1`은 전역 CSS에서 `display: none`이고, `.page-header` 자체도 `:has()` 셀렉터로 조건부 숨김 처리된다. 그래서 `report.vue`, `weekly-report.vue`, `project-timeline.vue`, `user-activities.vue`의 헤더는 화면에 아무것도 그리지 않는 빈 껍데기다. 이 태스크는 그 해킹을 걷어내고 필요한 화면만 명시적으로 헤더를 갖게 한다.

**Files:**
- Create: `frontend/src/components/ui/AppPageHeader.vue`
- Modify: `frontend/src/styles/shell.css` (`.page`, `.page-header`, `.page-subtitle`)
- Modify: `frontend/src/components/report.vue:171-178`
- Modify: `frontend/src/components/weekly-report.vue:363-370`
- Modify: `frontend/src/components/project-timeline.vue:318-324`
- Modify: `frontend/src/components/user-activities.vue:345-353`
- Modify: `frontend/src/components/report-result.vue:1-12`
- Modify: `frontend/src/components/weekly-detail.vue:1-12`
- Modify: `frontend/src/components/project-name.vue` (`.page` 클래스에 폭 변형 적용)
- Modify: `frontend/src/components/projects-list.vue:309`
- Modify: `frontend/src/components/team-select.vue:1-3`
- Modify: `frontend/src/components/user-select.vue:1-3`

**Interfaces:**
- Consumes: Task 1 토큰, Task 3의 탑바 제목(중복 제목을 피하기 위해 페이지 헤더는 부제·필터·액션 중심으로 쓴다)
- Produces: `AppPageHeader` 컴포넌트 — props `title?: string`, `subtitle?: string`; slots `filters`, `actions`

- [ ] **Step 1: `AppPageHeader.vue` 작성**

```vue
<script setup>
defineProps({
    title: { type: String, default: "" },
    subtitle: { type: String, default: "" },
});
</script>

<template>
    <header class="page-header">
        <div v-if="title || subtitle" class="page-header-text">
            <h1 v-if="title" class="page-title">{{ title }}</h1>
            <p v-if="subtitle" class="page-subtitle">{{ subtitle }}</p>
        </div>
        <div v-if="$slots.filters" class="page-header-filters">
            <slot name="filters" />
        </div>
        <div v-if="$slots.actions" class="page-header-actions">
            <slot name="actions" />
        </div>
    </header>
</template>
```

- [ ] **Step 2: 헤더·페이지 컨테이너 스타일 교체**

`shell.css`의 기존 `.page`, `.page-header`, `.page-header h1`, `.page-header h1.detail-title`, `:has()` 숨김 규칙, `.page-subtitle`을 모두 삭제하고 다음으로 대체한다.

```css
.page {
    max-width: var(--content-max);
    margin: 0 auto;
    padding: var(--space-6) var(--space-7) var(--space-8);
}

.page.is-wide {
    max-width: var(--content-max-wide);
}

.page-header {
    display: flex;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: var(--space-3) var(--space-4);
    margin-bottom: var(--space-5);
}

.page-header-text {
    min-width: 0;
    margin-right: auto;
}

.page-title {
    margin: 0;
    font-size: var(--fs-24);
    line-height: var(--lh-tight);
    color: var(--text-strong);
}

.page-subtitle {
    margin: var(--space-1) 0 0;
    font-size: var(--fs-14);
    line-height: var(--lh-base);
    color: var(--text-muted);
}

.page-header-filters,
.page-header-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2);
}
```

- [ ] **Step 3: 빈 헤더 4개 제거**

다음 화면에서 아무것도 렌더링하지 않는 `.page-header` 블록을 삭제한다. 제목은 탑바가 이미 보여준다.

- `report.vue:172-178`의 `<div class="page-header">...</div>` 전체
- `weekly-report.vue:363-370`의 동일 블록
- `project-timeline.vue:319-324`의 동일 블록

`user-activities.vue:345-353`은 `periodLabel`(예: "2026년 9월")을 제목으로 쓰고 있으므로 삭제하지 말고 `AppPageHeader`로 바꾼다.

```html
<AppPageHeader v-if="!embedded" :title="periodLabel" />
```

`user-activities.vue`의 `<script setup>`에 import를 추가한다.

```js
import AppPageHeader from "./ui/AppPageHeader.vue";
```

- [ ] **Step 4: 상세 화면 2개를 `AppPageHeader`로 전환**

`report-result.vue`의 헤더(1~12행 영역)를 다음으로 바꾼다. `goBack`이 없는 화면이므로 기존 마크업의 버튼 유무를 그대로 따른다.

```html
<AppPageHeader :title="userName || '분석 결과'" :subtitle="reportDate || '날짜 없음'" />
```

`weekly-detail.vue`의 헤더는 뒤로 가기 버튼이 있으므로 액션 슬롯을 쓴다.

```html
<AppPageHeader :title="userName || '주간 요약'" subtitle="주간 보고서">
    <template #actions>
        <button type="button" class="btn btn-small" @click="goBack">목록</button>
    </template>
</AppPageHeader>
```

두 파일 모두 `<script setup>`에 `AppPageHeader` import를 추가한다. 기존 `.detail-title`, `.back-btn` 관련 scoped 규칙과 `report-doc.css`의 `.report-doc .detail-title`, `.report-doc .back-btn` 규칙은 더 이상 쓰이지 않으므로 삭제한다.

- [ ] **Step 5: 본문 폭 지정**

2열 문서형 화면은 넓은 폭을 유지한다. 다음 파일의 루트 `div` 클래스에 `is-wide`를 추가한다.

- `report-result.vue`: `class="page report-doc is-wide"` (기존 클래스 구성에 `is-wide`만 덧붙인다)
- `weekly-detail.vue`: 동일
- `user-activities.vue`: 비임베드 분기의 `'page calendar-page'`를 `'page calendar-page is-wide'`로
- `project-timeline.vue`: `class="page is-wide"`

나머지(`projects-list.vue`, `report.vue`, `weekly-report.vue`, `project-name.vue`, `team-select.vue`, `user-select.vue`)는 기본 1120px을 쓰므로 변경하지 않는다.

- [ ] **Step 6: 목록·선택 화면에 헤더 부여**

현재 `projects-list.vue`(309행), `team-select.vue`, `user-select.vue`는 헤더 없이 바로 본문이 시작되고, 개수 정보가 본문 툴바에 흩어져 있다. 각각 `AppPageHeader`로 부제를 준다.

- `projects-list.vue`: `<AppPageHeader subtitle="팀의 일일보고 제출 현황" />`을 `.stat-grid` 앞에 넣는다.
- `team-select.vue`: `<AppPageHeader subtitle="보고서를 작성할 팀을 선택하세요" />`
- `user-select.vue`: `<AppPageHeader subtitle="보고서를 작성할 사용자를 선택하세요" />`

`project-name.vue`는 이미 `.section-head`에 제목과 카운트 칩이 있으므로 헤더를 추가하지 않는다.

각 파일에 `AppPageHeader` import를 추가한다.

- [ ] **Step 7: 남은 죽은 규칙 정리**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool/frontend
grep -rn "detail-title\|back-btn\|:has(" src/
```

기대: `AppPageHeader`로 옮긴 뒤 남은 참조가 없어야 한다. 남아 있으면 해당 scoped 규칙을 삭제한다.

- [ ] **Step 8: 브라우저 확인**

10개 화면을 모두 열어 확인한다.

- 제목이 탑바와 페이지 헤더에 중복 노출되지 않는다
- `/report-result/1`, `/weekly-detail/1`에 제목·부제가 보이고 목록 버튼이 우측에 있다
- `/activities`에 "2026년 9월" 같은 기간 제목이 보인다
- 목록·폼 화면의 본문 폭이 1120px로 제한되고, 2열 화면은 넓게 유지된다
- 콘솔 에러 없음

- [ ] **Step 9: 빌드와 커밋**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool/frontend && npm run build
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool
git add frontend/src/components frontend/src/styles
git commit -m "refactor: unify page headers and content width"
```

---

## Task 7: 화면별 scoped CSS 토큰화 (1/2 — 목록·작성 계열)

컴포넌트들은 이미 색을 CSS 변수로 쓰고 있다(하드코딩 hex는 `#fff` 2곳뿐). 이 태스크의 실제 작업은 간격 px 값과 `font-weight`, 폰트 크기를 토큰으로 바꾸고, 중복 패턴을 전역으로 올리는 것이다.

**Files:**
- Modify: `frontend/src/components/projects-list.vue:473-804` (scoped CSS)
- Modify: `frontend/src/components/report.vue:270-335`
- Modify: `frontend/src/components/weekly-report.vue:478-630`
- Modify: `frontend/src/components/weekly-detail.vue:354-369`
- Modify: `frontend/src/components/report-result.vue:497-501`
- Modify: `frontend/src/styles/components.css` (중복 패턴 승격)

**Interfaces:**
- Consumes: Task 1 토큰, Task 2의 `.chip`/`.count-chip`

- [ ] **Step 1: 치환 규칙 확인**

각 파일의 `<style scoped>` 안에서 다음 기계적 치환을 수행한다.

| 기존 | 치환 |
| --- | --- |
| `font-weight: 650` | `font-weight: var(--fw-semibold)` |
| `font-weight: 600` | `font-weight: var(--fw-semibold)` |
| `font-weight: 700` | `font-weight: var(--fw-bold)` |
| `font-weight: 500` | `font-weight: var(--fw-medium)` |
| `font-weight: 400` | 선언 삭제 |
| 간격 `4px` | `var(--space-1)` |
| 간격 `6px`, `8px`, `10px` | `var(--space-2)` (10px이 12px에 가깝게 보이는 밀집 영역은 `var(--space-3)`) |
| 간격 `12px`, `14px` | `var(--space-3)` |
| 간격 `16px`, `18px` | `var(--space-4)` |
| 간격 `20px` | `var(--space-5)` |
| 간격 `24px`, `28px` | `var(--space-6)` |
| `font-size: 11px|12px|13px|14px|16px|20px|24px` | 해당 `var(--fs-*)` |
| `var(--text-h)` | `var(--text-strong)` |
| `var(--bg-elevated)`, `var(--bg-soft)` | `var(--surface)` 또는 `var(--surface-soft)` (해당 요소가 카드 위인지 배경 위인지로 판단) |
| `var(--accent-bg)` | `var(--accent-soft)` |
| `var(--danger)`, `var(--success)`, `var(--warning)` | 각 `-fg` 토큰 |
| `#fff` | `var(--surface)` |
| `box-shadow: none` | 선언 삭제 |
| `transition: ... 0.15s` | `... var(--dur-fast) var(--ease)` |

`border-radius`는 pill인 버튼류를 제외하고 `--radius-sm`/`--radius`/`--radius-lg` 중 가장 가까운 값으로 바꾼다.

- [ ] **Step 2: `projects-list.vue` 치환**

332줄 scoped CSS에 위 규칙을 적용한다. `.count-chip`(536행) 정의는 Task 2에서 전역으로 올렸으므로 **삭제**한다. `.stat-card`는 배경을 `var(--surface)`, 테두리를 `var(--border)`로 하고 `is-active` 상태는 `var(--accent-soft)` 배경 + `var(--accent-border)` 테두리로 통일한다.

- [ ] **Step 3: `report.vue`, `weekly-report.vue`, `weekly-detail.vue`, `report-result.vue` 치환**

같은 규칙을 적용한다. `weekly-report.vue`의 `.day-chip`, `.day-status`는 상태 색 토큰(`--success-*`, `--warning-*`)을 쓰도록 바꾼다.

- [ ] **Step 4: 중복 패턴 승격**

이 네 파일에서 동일하게 반복되는 필터 바(`.filter-presets`, `.toolbar` 변형)와 목록 테이블 스타일이 있으면 `components.css`로 올리고 각 파일에서는 제거한다. 판단 기준: 두 개 이상 파일에 실질적으로 같은 선언 묶음이 있으면 승격한다.

- [ ] **Step 5: 남은 하드코딩 확인**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool/frontend
grep -n "font-weight: [0-9]\|#fff\|box-shadow: none\|--text-h\|--bg-elevated\|--bg-soft" \
  src/components/projects-list.vue src/components/report.vue \
  src/components/weekly-report.vue src/components/weekly-detail.vue \
  src/components/report-result.vue
```

기대: 출력 없음.

- [ ] **Step 6: 브라우저 확인과 커밋**

`/`, `/report`, `/weekly`, `/weekly-detail/1`, `/report-result/1`을 열어 레이아웃이 깨지지 않았는지 본다.

```bash
npm run build
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool
git add frontend/src/components frontend/src/styles
git commit -m "style: tokenize report and list screen styles"
```

---

## Task 8: 화면별 scoped CSS 토큰화 (2/2 — 관리·활동 계열)

**Files:**
- Modify: `frontend/src/components/project-name.vue:556-921`
- Modify: `frontend/src/components/user-activities.vue:480-842`
- Modify: `frontend/src/components/project-timeline.vue:501-769`
- Modify: `frontend/src/components/team-select.vue:154-264`
- Modify: `frontend/src/components/user-select.vue:133-243`
- Modify: `frontend/src/styles/tokens.css` (마이그레이션 별칭 제거)

**Interfaces:**
- Consumes: Task 7과 동일한 치환 규칙

- [ ] **Step 1: 다섯 파일에 Task 7 Step 1의 치환 규칙 적용**

`project-name.vue`의 `.count-chip`(561행) 정의는 전역으로 올렸으므로 삭제한다. `user-activities.vue`는 `rgba()`/`color-mix()`가 10곳 있으므로 각각 상태·액센트 토큰으로 바꾼다. 색 의미가 애매한 곳(달력 셀 강조 등)은 `var(--accent-soft)`와 `var(--surface-soft)` 중 대비가 유지되는 쪽을 쓴다.

`team-select.vue`와 `user-select.vue`의 `.team-card`/`.user-card`는 동일한 카드 그리드 패턴이므로 `components.css`에 `.select-grid`, `.select-card`로 승격하고 두 파일에서는 화면 특화 부분만 남긴다.

- [ ] **Step 2: 마이그레이션 별칭 제거**

전 파일에서 레거시 토큰 참조가 사라졌는지 확인한다.

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool/frontend
grep -rn "\-\-text-h\|--bg-elevated\|--bg-soft\|--code-bg\|--social-bg\|--accent-bg\|--shadow\|var(--danger)\|var(--success)\|var(--warning)" src/ --include=*.vue --include=*.css | grep -v "styles/tokens.css"
```

기대: 출력 없음. 남아 있으면 먼저 치환한다. 그 후 `tokens.css` 하단의 "마이그레이션 별칭" 블록 전체를 삭제한다.

- [ ] **Step 3: 빌드와 브라우저 확인**

```bash
npm run build
```

기대: 성공. `/project-name`, `/activities`, `/project-timeline`, `/team-select`, `/users`를 열어 레이아웃과 색 대비를 확인한다. 별칭 제거로 스타일이 빠진 요소가 있으면(글자가 흐리거나 배경이 사라짐) 해당 선택자를 찾아 새 토큰으로 고친다.

- [ ] **Step 4: 커밋**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool
git add frontend/src/components frontend/src/styles
git commit -m "style: tokenize management screens and drop legacy aliases"
```

---

## Task 9: 전체 검증과 스크린샷

**Files:** 없음(검증 전용). 발견된 문제는 해당 태스크의 파일에서 고친다.

- [ ] **Step 1: 클린 빌드**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool/frontend
rm -rf dist && npm run build
```

기대: 성공, 종료 코드 0.

- [ ] **Step 2: 10개 화면 순회**

`npm run dev` 후 사전 확인 표의 10개 경로를 모두 방문한다. 각 화면에서 확인할 것:

- 콘솔에 에러·Vue 경고 없음
- 텍스트가 잘리거나 겹치지 않음
- 카드가 배경과 구분됨
- 버튼·입력 모양이 화면 간 일관됨
- 스크린샷 저장

- [ ] **Step 3: 셸 동작 확인**

- 사이드바 접기·펼치기, 새로고침 후 상태 유지
- 탑바 경로 표시와 상위 링크 이동
- 860px 이하에서 드로어 열기·닫기(오버레이 클릭, `Escape`, 메뉴 선택)
- 사이드바 활성 항목이 상세 화면에서도 올바르게 표시

- [ ] **Step 4: 발견된 문제 수정 후 커밋**

```bash
cd /Users/dongrizheng/Documents/GitHub/report-automate-tool
git add -A
git commit -m "fix: resolve issues found in UI redesign verification"
```

문제가 없으면 커밋하지 않는다.

- [ ] **Step 5: 되돌리기 경로 확인**

```bash
git log --oneline main..ui-redesign
```

기대: Task 1~9의 커밋이 단계별로 나열된다. 전체 되돌리기는 `git switch main`, 부분 되돌리기는 해당 커밋의 `git revert <sha>`로 가능함을 사용자에게 안내한다.

---

## 되돌리기 요약

| 원하는 것 | 명령 |
| --- | --- |
| 전부 되돌리기 | `git switch main` |
| 다시 새 UI 보기 | `git switch ui-redesign` |
| 특정 단계만 취소 | `git revert <해당 커밋 sha>` |
| 새 UI 확정 | `git switch main && git merge ui-redesign` |
