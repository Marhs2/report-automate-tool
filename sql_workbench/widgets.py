"""재사용 UI 위젯 — 스크롤 폼, 라인넘버 에디터, 상태바 등."""

from __future__ import annotations

import re
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Any, Callable, Optional

from .theme import (
    MONO_FONT,
    MONO_FONT_LG,
    MONO_FONT_SM,
    Palette,
    UI_FONT,
)

# SQL 하이라이트 키워드
_SQL_KEYWORDS = {
    "SELECT",
    "FROM",
    "WHERE",
    "AND",
    "OR",
    "NOT",
    "IN",
    "IS",
    "NULL",
    "LIKE",
    "BETWEEN",
    "JOIN",
    "LEFT",
    "RIGHT",
    "INNER",
    "OUTER",
    "FULL",
    "CROSS",
    "ON",
    "AS",
    "ORDER",
    "BY",
    "GROUP",
    "HAVING",
    "LIMIT",
    "OFFSET",
    "INSERT",
    "INTO",
    "VALUES",
    "UPDATE",
    "SET",
    "DELETE",
    "CREATE",
    "TABLE",
    "VIEW",
    "INDEX",
    "DROP",
    "ALTER",
    "ADD",
    "COLUMN",
    "PRIMARY",
    "KEY",
    "FOREIGN",
    "REFERENCES",
    "UNIQUE",
    "CHECK",
    "DEFAULT",
    "CASCADE",
    "RESTRICT",
    "DISTINCT",
    "UNION",
    "ALL",
    "EXISTS",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "ASC",
    "DESC",
    "WITH",
    "RECURSIVE",
    "PRAGMA",
    "EXPLAIN",
    "ANALYZE",
    "ATTACH",
    "DETACH",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "TRANSACTION",
    "REPLACE",
    "RETURNING",
    "IF",
    "ELSEIF",
    "TRUE",
    "FALSE",
    "CAST",
    "COLLATE",
}

_KW_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")
_STR_RE = re.compile(r"('(?:''|[^'])*')")
_NUM_RE = re.compile(r"\b(\d+(?:\.\d+)?)\b")
_COMMENT_LINE_RE = re.compile(r"(--[^\n]*)")
_COMMENT_BLOCK_RE = re.compile(r"(/\*.*?\*/)", re.DOTALL)

# 자동완성용 SQLite 함수 (괄호 포함 삽입)
_SQL_FUNCTIONS = (
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "COALESCE",
    "IFNULL",
    "NULLIF",
    "LENGTH",
    "SUBSTR",
    "SUBSTRING",
    "TRIM",
    "LTRIM",
    "RTRIM",
    "UPPER",
    "LOWER",
    "REPLACE",
    "INSTR",
    "ROUND",
    "ABS",
    "TYPEOF",
    "CAST",
    "DATE",
    "TIME",
    "DATETIME",
    "JULIANDAY",
    "STRFTIME",
    "GROUP_CONCAT",
    "TOTAL",
    "HEX",
    "QUOTE",
    "PRINTF",
    "JSON_EXTRACT",
    "JSON_OBJECT",
    "JSON_ARRAY",
    "JSON_TYPE",
    "JSON_VALID",
    "RANDOM",
    "CHANGES",
    "LAST_INSERT_ROWID",
)

# 테이블/컬럼 우선 컨텍스트
_CTX_TABLE = frozenset(
    {"FROM", "JOIN", "INTO", "UPDATE", "TABLE", "VIEW", "INDEX", "REFERENCES", "ON"}
)
_CTX_COLUMN = frozenset(
    {
        "SELECT",
        "WHERE",
        "AND",
        "OR",
        "HAVING",
        "SET",
        "BY",
        "ON",
        "RETURNING",
        "WHEN",
        "THEN",
        "ELSE",
        "BETWEEN",
        "LIKE",
        "IN",
        "IS",
        "NOT",
    }
)

SchemaProvider = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class CompletionItem:
    label: str
    insert: str
    kind: str  # keyword | function | table | view | column
    detail: str = ""

    def display(self) -> str:
        tag = {
            "keyword": "키워드",
            "function": "함수",
            "table": "테이블",
            "view": "뷰",
            "column": "컬럼",
        }.get(self.kind, self.kind)
        extra = f"  ·  {self.detail}" if self.detail else ""
        return f"{self.label}    [{tag}]{extra}"


class SqlAutocomplete:
    """SQL 편집기 자동완성 팝업 (키워드 / 함수 / 테이블 / 컬럼)."""

    MAX_ITEMS = 40

    def __init__(
        self,
        editor: "SqlEditor",
        schema_provider: Optional[SchemaProvider] = None,
    ) -> None:
        self.editor = editor
        self.schema_provider = schema_provider
        self._popup: Optional[tk.Toplevel] = None
        self._listbox: Optional[tk.Listbox] = None
        self._items: list[CompletionItem] = []
        self._token_start: Optional[str] = None
        self._token_end: Optional[str] = None
        self._job: Optional[str] = None
        self._active = False

    def set_schema_provider(self, provider: Optional[SchemaProvider]) -> None:
        self.schema_provider = provider

    def destroy(self) -> None:
        self.hide()
        if self._job:
            try:
                self.editor.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def schedule(self, force: bool = False) -> None:
        if self._job:
            try:
                self.editor.after_cancel(self._job)
            except Exception:
                pass
        delay = 0 if force else 90
        self._job = self.editor.after(delay, lambda: self._trigger(force=force))

    def on_key_release(self, event: tk.Event) -> None:
        keysym = getattr(event, "keysym", "") or ""
        # 네비게이션/수정 키는 별도 처리
        if keysym in (
            "Up",
            "Down",
            "Return",
            "KP_Enter",
            "Tab",
            "Escape",
            "Left",
            "Right",
            "Home",
            "End",
            "Prior",
            "Next",
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
            "Alt_L",
            "Alt_R",
        ):
            return
        if event.state & 0x4:  # Control
            return
        ch = getattr(event, "char", "") or ""
        if ch and (ch.isalnum() or ch in "._"):
            self.schedule(force=False)
        elif keysym in ("BackSpace", "Delete"):
            self.schedule(force=False)
        elif self._active:
            # 공백/연산자 등이면 닫기
            self.hide()

    def force_complete(self, _event: Any = None) -> str:
        self.schedule(force=True)
        return "break"

    def hide(self) -> None:
        self._active = False
        self._items = []
        self._token_start = None
        self._token_end = None
        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
            self._listbox = None

    def is_active(self) -> bool:
        return self._active and self._popup is not None

    def navigate(self, delta: int) -> str:
        if not self.is_active() or not self._listbox:
            return ""
        size = self._listbox.size()
        if size <= 0:
            return "break"
        cur = self._listbox.curselection()
        idx = int(cur[0]) if cur else 0
        idx = max(0, min(size - 1, idx + delta))
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(idx)
        self._listbox.activate(idx)
        self._listbox.see(idx)
        return "break"

    def accept(self, _event: Any = None) -> str:
        if not self.is_active() or not self._listbox or not self._items:
            return ""
        sel = self._listbox.curselection()
        if not sel:
            return "break"
        item = self._items[int(sel[0])]
        self._apply(item)
        return "break"

    # ── core ─────────────────────────────────────────────────────

    def _trigger(self, force: bool = False) -> None:
        self._job = None
        text = self.editor.text
        try:
            if not text.winfo_exists():
                return
        except Exception:
            return

        # 문자열/주석 안에서는 자동 팝업 억제 (Ctrl+Space 는 허용)
        if not force and self._in_string_or_comment():
            self.hide()
            return

        ctx = self._parse_context()
        if ctx is None:
            self.hide()
            return

        prefix, table_ref, token_start, token_end, prev_kw = ctx
        if not force and not prefix and not table_ref:
            self.hide()
            return
        if not force and len(prefix) < 1 and not table_ref:
            self.hide()
            return

        items = self._build_items(prefix, table_ref, prev_kw)
        if not items:
            self.hide()
            return

        self._show(items, token_start=token_start, token_end=token_end)

    def _parse_context(
        self,
    ) -> Optional[tuple[str, Optional[str], str, str, Optional[str]]]:
        text = self.editor.text
        insert = text.index("insert")
        line_start = text.index(f"{insert} linestart")
        before = text.get(line_start, insert)

        # table.column 또는 부분 입력
        m = re.search(
            r"(?P<table>[A-Za-z_][A-Za-z0-9_]*)\.(?P<col>[A-Za-z_][A-Za-z0-9_]*)?$"
            r"|(?P<word>[A-Za-z_][A-Za-z0-9_]*)$",
            before,
        )
        if not m:
            # 빈 접두 + 강제 완성(Ctrl+Space)만 허용 — 커서 직전 비식별자
            return ("", None, insert, insert, self._prev_keyword(before))

        if m.group("table") is not None:
            table_ref = m.group("table")
            prefix = m.group("col") or ""
            # 컬럼 부분 시작 인덱스 (점 다음)
            dot_pos = before.rfind(".")
            col_start_off = dot_pos + 1
            token_start = f"{line_start}+{col_start_off}c"
            token_end = insert
            return (prefix, table_ref, token_start, token_end, self._prev_keyword(before))

        word = m.group("word") or ""
        start_off = len(before) - len(word)
        token_start = f"{line_start}+{start_off}c"
        token_end = insert
        return (word, None, token_start, token_end, self._prev_keyword(before[:start_off]))

    @staticmethod
    def _prev_keyword(before: str) -> Optional[str]:
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", before)
        for tok in reversed(tokens):
            up = tok.upper()
            if up in _SQL_KEYWORDS:
                return up
        return None

    def _in_string_or_comment(self) -> bool:
        text = self.editor.text
        insert = text.index("insert")
        # 현재 줄 기준 -- 주석
        line = text.get(f"{insert} linestart", insert)
        in_str = False
        i = 0
        while i < len(line):
            ch = line[i]
            if not in_str and ch == "-" and i + 1 < len(line) and line[i + 1] == "-":
                return True
            if ch == "'":
                if in_str and i + 1 < len(line) and line[i + 1] == "'":
                    i += 2
                    continue
                in_str = not in_str
            i += 1
        if in_str:
            return True
        # 블록 주석 (간단 스캔)
        content = text.get("1.0", insert)
        last_open = content.rfind("/*")
        last_close = content.rfind("*/")
        if last_open > last_close:
            return True
        return False

    def _schema(self) -> dict[str, Any]:
        if not self.schema_provider:
            return {"tables": [], "views": [], "columns": {}}
        try:
            data = self.schema_provider() or {}
        except Exception:
            return {"tables": [], "views": [], "columns": {}}
        return {
            "tables": list(data.get("tables") or []),
            "views": list(data.get("views") or []),
            "columns": dict(data.get("columns") or {}),
        }

    def _build_items(
        self,
        prefix: str,
        table_ref: Optional[str],
        prev_kw: Optional[str],
    ) -> list[CompletionItem]:
        schema = self._schema()
        tables = schema["tables"]
        views = schema["views"]
        columns_map: dict[str, list[str]] = schema["columns"]
        pl = prefix.lower()

        items: list[CompletionItem] = []

        def match(name: str) -> bool:
            if not pl:
                return True
            return name.lower().startswith(pl)

        # table.col → 해당 테이블 컬럼만
        if table_ref is not None:
            # 대소문자 무시 매칭
            resolved = None
            for t in list(tables) + list(views):
                if t.lower() == table_ref.lower():
                    resolved = t
                    break
            cols = columns_map.get(resolved or table_ref, [])
            if not cols and resolved is None:
                # 별칭/미확인 테이블: 모든 컬럼 후보
                seen: set[str] = set()
                for col_list in columns_map.values():
                    for c in col_list:
                        if c.lower() not in seen and match(c):
                            seen.add(c.lower())
                            items.append(
                                CompletionItem(c, c, "column", table_ref)
                            )
            else:
                for c in cols:
                    if match(c):
                        items.append(
                            CompletionItem(c, c, "column", resolved or table_ref)
                        )
            return self._rank_and_trim(items, prefix, prefer="column")

        prefer = "all"
        if prev_kw in _CTX_TABLE:
            prefer = "table"
        elif prev_kw in _CTX_COLUMN:
            prefer = "column"

        for t in tables:
            if match(t):
                items.append(CompletionItem(t, t, "table"))
        for v in views:
            if match(v):
                items.append(CompletionItem(v, v, "view"))

        # 컬럼: 테이블명.컬럼 형태로 detail 표시 (중복 컬럼은 여러 테이블 가능)
        col_seen: set[str] = set()
        for tname, cols in columns_map.items():
            for c in cols:
                key = c.lower()
                if key in col_seen:
                    # 이미 있으면 detail 만 확장하지 않고 스킵 (대표 1개)
                    continue
                if match(c):
                    col_seen.add(key)
                    items.append(CompletionItem(c, c, "column", tname))

        for kw in sorted(_SQL_KEYWORDS):
            if match(kw):
                items.append(CompletionItem(kw, kw, "keyword"))

        for fn in _SQL_FUNCTIONS:
            if match(fn):
                items.append(CompletionItem(fn, f"{fn}(", "function"))

        return self._rank_and_trim(items, prefix, prefer=prefer)

    def _rank_and_trim(
        self,
        items: list[CompletionItem],
        prefix: str,
        *,
        prefer: str,
    ) -> list[CompletionItem]:
        pl = prefix.lower()
        kind_weight = {
            "table": 0,
            "view": 1,
            "column": 2,
            "function": 3,
            "keyword": 4,
        }
        if prefer == "table":
            kind_weight = {
                "table": 0,
                "view": 1,
                "column": 4,
                "function": 3,
                "keyword": 2,
            }
        elif prefer == "column":
            kind_weight = {
                "column": 0,
                "table": 2,
                "view": 3,
                "function": 1,
                "keyword": 4,
            }

        def score(it: CompletionItem) -> tuple:
            name = it.label
            nl = name.lower()
            exact = 0 if nl == pl else 1
            starts = 0 if nl.startswith(pl) else 1
            # 대문자 키워드 vs 입력 대소문자 근접
            case_pen = 0 if (not prefix or name.startswith(prefix[0])) else 1
            return (
                exact,
                starts,
                kind_weight.get(it.kind, 9),
                case_pen,
                len(name),
                nl,
            )

        items = sorted(items, key=score)
        # 동일 label 중복 제거 (kind 우선순위 유지)
        out: list[CompletionItem] = []
        seen: set[str] = set()
        for it in items:
            key = f"{it.kind}:{it.label.lower()}"
            if key in seen:
                continue
            # label 중복이면 더 좋은 kind 만 (이미 정렬됨)
            label_key = it.label.lower()
            if any(x.label.lower() == label_key for x in out):
                # 테이블/컬럼 이름이 키워드와 겹치면 스키마 쪽 우선 유지
                continue
            seen.add(key)
            out.append(it)
            if len(out) >= self.MAX_ITEMS:
                break
        return out

    def _show(
        self,
        items: list[CompletionItem],
        *,
        token_start: str,
        token_end: str,
    ) -> None:
        self.hide()
        self._items = items
        self._token_start = token_start
        self._token_end = token_end
        self._active = True

        text = self.editor.text
        palette = self.editor.palette

        popup = tk.Toplevel(self.editor)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        try:
            popup.configure(bg=palette.border)
        except Exception:
            pass

        lb = tk.Listbox(
            popup,
            font=MONO_FONT_SM,
            height=min(12, len(items)),
            activestyle="dotbox",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=palette.accent,
            highlightcolor=palette.accent,
            bg=palette.surface2,
            fg=palette.text,
            selectbackground=palette.accent,
            selectforeground="#ffffff",
            exportselection=False,
        )
        for it in items:
            lb.insert("end", it.display())
        lb.selection_set(0)
        lb.activate(0)
        lb.pack(padx=1, pady=1)

        # 커서 위치 근처에 배치
        bbox = None
        try:
            bbox = text.bbox("insert")
            if bbox:
                x, y, _w, h = bbox
                abs_x = text.winfo_rootx() + x
                abs_y = text.winfo_rooty() + y + h + 2
            else:
                abs_x = text.winfo_rootx() + 20
                abs_y = text.winfo_rooty() + 20
        except Exception:
            abs_x = text.winfo_rootx() + 20
            abs_y = text.winfo_rooty() + 20

        # 폭 계산
        try:
            max_chars = max(len(it.display()) for it in items)
            width_px = min(520, max(280, max_chars * 8 + 24))
        except Exception:
            width_px = 320
        height_px = min(12, len(items)) * 18 + 8

        # 화면 밖으로 나가지 않게
        try:
            sw = popup.winfo_screenwidth()
            sh = popup.winfo_screenheight()
            if abs_x + width_px > sw - 8:
                abs_x = max(8, sw - width_px - 8)
            if abs_y + height_px > sh - 40:
                caret_y = bbox[1] if bbox else 0
                abs_y = max(8, text.winfo_rooty() + caret_y - height_px - 4)
        except Exception:
            pass

        popup.geometry(f"{width_px}x{height_px}+{abs_x}+{abs_y}")
        self._popup = popup
        self._listbox = lb

        lb.bind("<ButtonRelease-1>", self._on_click)
        lb.bind("<Double-Button-1>", self.accept)
        popup.bind("<FocusOut>", self._on_focus_out)

    def _on_click(self, _event: Any = None) -> None:
        # 단일 클릭은 선택만, 더블클릭/Enter 로 확정 — 단 클릭 후 포커스 유지
        if self._listbox:
            try:
                self.editor.text.focus_set()
            except Exception:
                pass

    def _on_focus_out(self, _event: Any = None) -> None:
        # 에디터로 포커스 돌아가면 유지, 다른 곳이면 닫기
        self.editor.after(80, self._maybe_hide_on_focus)

    def _maybe_hide_on_focus(self) -> None:
        if not self._popup:
            return
        try:
            focus = self.editor.focus_get()
        except Exception:
            self.hide()
            return
        if focus is self._listbox or focus is self.editor.text:
            return
        self.hide()

    def _apply(self, item: CompletionItem) -> None:
        text = self.editor.text
        start = self._token_start or text.index("insert")
        end = self._token_end or text.index("insert")
        text.delete(start, end)
        text.insert(start, item.insert)
        self.hide()
        self.editor._refresh_gutter()
        self.editor.highlight()
        text.focus_set()
        text.see("insert")


class ScrollableFrame(ttk.Frame):
    """세로 스크롤 컨테이너 (폼용)."""

    def __init__(self, parent: tk.Misc, palette: Optional[Palette] = None, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        canvas_kwargs: dict[str, Any] = {
            "highlightthickness": 0,
            "borderwidth": 0,
        }
        if palette:
            canvas_kwargs["bg"] = palette.surface
        canvas = tk.Canvas(self, **canvas_kwargs)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)

        self.inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self._window = canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_width(event: tk.Event) -> None:
            canvas.itemconfigure(self._window, width=event.width)

        canvas.bind("<Configure>", _on_width)
        self.canvas = canvas

        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))


class SqlEditor(ttk.Frame):
    """라인 번호 + SQL 하이라이트 + 자동완성 편집기."""

    def __init__(
        self,
        parent: tk.Misc,
        palette: Palette,
        on_change: Optional[Callable[[], None]] = None,
        schema_provider: Optional[SchemaProvider] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)
        self.palette = palette
        self._on_change = on_change
        self._hl_job: Optional[str] = None
        self._updating = False

        self.gutter = tk.Text(
            self,
            width=4,
            padx=6,
            pady=8,
            takefocus=0,
            borderwidth=0,
            highlightthickness=0,
            wrap="none",
            font=MONO_FONT_LG,
            bg=palette.editor_gutter,
            fg=palette.editor_gutter_fg,
            state="disabled",
            cursor="arrow",
        )
        self.text = tk.Text(
            self,
            wrap="none",
            font=MONO_FONT_LG,
            undo=True,
            maxundo=200,
            padx=10,
            pady=8,
            borderwidth=0,
            highlightthickness=0,
            bg=palette.editor_bg,
            fg=palette.editor_fg,
            insertbackground=palette.editor_cursor,
            selectbackground=palette.editor_sel,
            selectforeground=palette.editor_fg,
            insertofftime=300,
            insertwidth=2,
            tabs=("1c",),
        )
        vsb = ttk.Scrollbar(self, orient="vertical", command=self._on_scroll)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=self._on_text_yscroll, xscrollcommand=hsb.set)

        self.gutter.grid(row=0, column=0, sticky="ns")
        self.text.grid(row=0, column=1, sticky="nsew")
        vsb.grid(row=0, column=2, sticky="ns")
        hsb.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        self.text.tag_configure("kw", foreground=palette.kw)
        self.text.tag_configure("str", foreground=palette.string)
        self.text.tag_configure("num", foreground=palette.number)
        self.text.tag_configure("comment", foreground=palette.comment)

        self.autocomplete = SqlAutocomplete(self, schema_provider)

        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<KeyRelease>", self._on_key_release)
        self.text.bind("<ButtonRelease-1>", self._on_click)
        self.text.bind("<Tab>", self._on_tab)
        self.text.bind("<Control-a>", self._select_all)
        self.text.bind("<Control-A>", self._select_all)
        # Windows Tk: keysym is lowercase "space" (Control-Space is invalid)
        self.text.bind("<Control-space>", self.autocomplete.force_complete)
        self.text.bind("<Control-Key-space>", self.autocomplete.force_complete)
        self.text.bind("<Escape>", self._on_escape)
        self.text.bind("<Up>", self._on_up)
        self.text.bind("<Down>", self._on_down)
        self.text.bind("<Return>", self._on_return)
        self.text.bind("<KP_Enter>", self._on_return)

        self._refresh_gutter()

    # public API ---------------------------------------------------

    def get(self, start: str = "1.0", end: str = "end-1c") -> str:
        return self.text.get(start, end)

    def set_text(self, content: str) -> None:
        self.autocomplete.hide()
        self._updating = True
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.edit_modified(False)
        self._updating = False
        self._refresh_gutter()
        self.highlight()

    def clear(self) -> None:
        self.set_text("")

    def insert(self, index: str, content: str) -> None:
        self.text.insert(index, content)
        self._refresh_gutter()
        self.highlight()

    def focus_set(self) -> None:  # type: ignore[override]
        self.text.focus_set()

    def set_schema_provider(self, provider: Optional[SchemaProvider]) -> None:
        self.autocomplete.set_schema_provider(provider)

    def apply_palette(self, palette: Palette) -> None:
        self.palette = palette
        self.autocomplete.hide()
        self.gutter.configure(bg=palette.editor_gutter, fg=palette.editor_gutter_fg)
        self.text.configure(
            bg=palette.editor_bg,
            fg=palette.editor_fg,
            insertbackground=palette.editor_cursor,
            selectbackground=palette.editor_sel,
            selectforeground=palette.editor_fg,
        )
        self.text.tag_configure("kw", foreground=palette.kw)
        self.text.tag_configure("str", foreground=palette.string)
        self.text.tag_configure("num", foreground=palette.number)
        self.text.tag_configure("comment", foreground=palette.comment)
        self.highlight()

    def highlight(self) -> None:
        content = self.text.get("1.0", "end-1c")
        for tag in ("kw", "str", "num", "comment"):
            self.text.tag_remove(tag, "1.0", "end")
        if not content:
            return

        # comments first
        for m in _COMMENT_BLOCK_RE.finditer(content):
            self._tag_span("comment", m.start(), m.end(), content)
        for m in _COMMENT_LINE_RE.finditer(content):
            self._tag_span("comment", m.start(), m.end(), content)
        for m in _STR_RE.finditer(content):
            self._tag_span("str", m.start(), m.end(), content)
        for m in _NUM_RE.finditer(content):
            self._tag_span("num", m.start(), m.end(), content)
        for m in _KW_RE.finditer(content):
            if m.group(1).upper() in _SQL_KEYWORDS:
                self._tag_span("kw", m.start(), m.end(), content)

    # internals ----------------------------------------------------

    def _tag_span(self, tag: str, start: int, end: int, content: str) -> None:
        s_idx = self._index_from_offset(content, start)
        e_idx = self._index_from_offset(content, end)
        self.text.tag_add(tag, s_idx, e_idx)

    @staticmethod
    def _index_from_offset(content: str, offset: int) -> str:
        before = content[:offset]
        line = before.count("\n") + 1
        col = offset - (before.rfind("\n") + 1)
        return f"{line}.{col}"

    def _on_scroll(self, *args: Any) -> None:
        self.text.yview(*args)
        self.gutter.yview(*args)

    def _on_text_yscroll(self, first: str, last: str) -> None:
        self.gutter.yview_moveto(first)
        # sync scrollbar via master
        try:
            self.nametowidget(self.winfo_parent())  # noqa: keep alive
        except Exception:
            pass
        # find vertical scrollbar — update via text's linked command already set
        # re-apply to gutter
        self.gutter.yview_moveto(first)
        # forward to scrollbar: stored in grid
        for child in self.grid_slaves(row=0, column=2):
            if isinstance(child, ttk.Scrollbar):
                child.set(first, last)

    def _on_modified(self, _event: Any = None) -> None:
        if self._updating:
            return
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self._refresh_gutter()
            self._schedule_highlight()
            if self._on_change:
                self._on_change()

    def _schedule_highlight(self, _event: Any = None) -> None:
        if self._hl_job:
            try:
                self.after_cancel(self._hl_job)
            except Exception:
                pass
        self._hl_job = self.after(120, self.highlight)
        self._sync_gutter()

    def _on_key_release(self, event: tk.Event) -> None:
        self._schedule_highlight(event)
        self.autocomplete.on_key_release(event)

    def _on_click(self, _event: Any = None) -> None:
        self.autocomplete.hide()
        self._sync_gutter()

    def _on_escape(self, _event: Any = None) -> str:
        if self.autocomplete.is_active():
            self.autocomplete.hide()
            return "break"
        return ""

    def _on_up(self, _event: Any = None) -> str:
        if self.autocomplete.is_active():
            return self.autocomplete.navigate(-1)
        return ""

    def _on_down(self, _event: Any = None) -> str:
        if self.autocomplete.is_active():
            return self.autocomplete.navigate(1)
        return ""

    def _on_return(self, _event: Any = None) -> str:
        if self.autocomplete.is_active():
            return self.autocomplete.accept()
        return ""

    def _refresh_gutter(self) -> None:
        end_line = int(self.text.index("end-1c").split(".")[0])
        lines = "\n".join(str(i) for i in range(1, end_line + 1))
        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        self.gutter.insert("1.0", lines)
        self.gutter.configure(state="disabled")
        # width by digit count
        width = max(3, len(str(end_line)) + 1)
        self.gutter.configure(width=width)
        self._sync_gutter()

    def _sync_gutter(self, _event: Any = None) -> None:
        try:
            first, _ = self.text.yview()
            self.gutter.yview_moveto(first)
        except Exception:
            pass

    def _on_tab(self, _event: Any = None) -> str:
        if self.autocomplete.is_active():
            return self.autocomplete.accept()
        self.text.insert("insert", "    ")
        return "break"

    def _select_all(self, _event: Any = None) -> str:
        self.text.tag_add("sel", "1.0", "end-1c")
        return "break"


class ReadOnlyText(ttk.Frame):
    """읽기 전용 텍스트 패널 (상세/DDL)."""

    def __init__(
        self,
        parent: tk.Misc,
        palette: Palette,
        *,
        height: int = 10,
        mono: bool = True,
        dark_editor: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)
        self.palette = palette
        bg = palette.editor_bg if dark_editor else palette.surface2
        fg = palette.editor_fg if dark_editor else palette.text
        self.text = tk.Text(
            self,
            height=height,
            wrap="word",
            font=MONO_FONT if mono else UI_FONT,
            state="disabled",
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=8,
            bg=bg,
            fg=fg,
            insertbackground=fg,
            selectbackground=palette.editor_sel,
            selectforeground=palette.editor_fg,
        )
        sy = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sy.set)
        self.text.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")

    def set_content(self, content: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.configure(state="disabled")

    def get(self) -> str:
        return self.text.get("1.0", "end-1c")

    def apply_palette(self, palette: Palette, dark_editor: bool = True) -> None:
        self.palette = palette
        bg = palette.editor_bg if dark_editor else palette.surface2
        fg = palette.editor_fg if dark_editor else palette.text
        self.text.configure(
            bg=bg,
            fg=fg,
            insertbackground=fg,
            selectbackground=palette.editor_sel,
        )


class StatusBar(ttk.Frame):
    """하단 상태바 — 메시지 / 타이밍 / 연결."""

    def __init__(self, parent: tk.Misc, **kwargs: Any) -> None:
        super().__init__(parent, style="Status.TFrame", **kwargs)
        self.msg_var = tk.StringVar(value="준비")
        self.meta_var = tk.StringVar(value="")
        self.hint_var = tk.StringVar(
            value="F5 실행  ·  Ctrl+Space 자동완성  ·  Ctrl+O DB  ·  Del 삭제"
        )

        ttk.Label(self, textvariable=self.msg_var, style="Status.TLabel").pack(
            side="left", padx=(12, 8), pady=6
        )
        self.meta_label = ttk.Label(
            self, textvariable=self.meta_var, style="Success.TLabel"
        )
        self.meta_label.pack(side="left", padx=4)
        ttk.Label(self, textvariable=self.hint_var, style="Status.TLabel").pack(
            side="right", padx=12, pady=6
        )

    def set_message(self, msg: str, *, error: bool = False) -> None:
        self.msg_var.set(msg)
        self.meta_label.configure(style="Error.TLabel" if error else "Success.TLabel")

    def set_meta(self, meta: str) -> None:
        self.meta_var.set(meta)


class EmptyState(ttk.Frame):
    """빈 상태 안내 패널."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        subtitle: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, **kwargs)
        wrap = ttk.Frame(self)
        wrap.place(relx=0.5, rely=0.45, anchor="center")
        ttk.Label(wrap, text=title, style="Title.TLabel").pack()
        if subtitle:
            ttk.Label(wrap, text=subtitle, style="Muted.TLabel", justify="center").pack(
                pady=(6, 0)
            )


def bind_tree_mousewheel(tree: ttk.Treeview) -> None:
    """Treeview 가로/세로 휠 편의 (Windows)."""

    def _wheel(event: tk.Event) -> None:
        tree.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _shift_wheel(event: tk.Event) -> None:
        tree.xview_scroll(int(-1 * (event.delta / 120)), "units")

    tree.bind("<MouseWheel>", _wheel)
    tree.bind("<Shift-MouseWheel>", _shift_wheel)


def style_data_tree(tree: ttk.Treeview, palette: Palette) -> None:
    tree.tag_configure("odd", background=palette.row_odd, foreground=palette.text)
    tree.tag_configure("even", background=palette.row_even, foreground=palette.text)
    tree.tag_configure("nullish", foreground=palette.null_fg)
