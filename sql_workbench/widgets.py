"""재사용 UI 위젯 — 스크롤 폼, 라인넘버 에디터, 상태바 등."""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Optional

from .theme import (
    MONO_FONT,
    MONO_FONT_LG,
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
    """라인 번호 + SQL 하이라이트 편집기."""

    def __init__(
        self,
        parent: tk.Misc,
        palette: Palette,
        on_change: Optional[Callable[[], None]] = None,
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

        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<KeyRelease>", self._schedule_highlight)
        self.text.bind("<ButtonRelease-1>", self._sync_gutter)
        self.text.bind("<Tab>", self._on_tab)
        self.text.bind("<Control-a>", self._select_all)
        self.text.bind("<Control-A>", self._select_all)

        self._refresh_gutter()

    # public API ---------------------------------------------------

    def get(self, start: str = "1.0", end: str = "end-1c") -> str:
        return self.text.get(start, end)

    def set_text(self, content: str) -> None:
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

    def apply_palette(self, palette: Palette) -> None:
        self.palette = palette
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
            value="F5 실행  ·  Ctrl+O DB  ·  Del 삭제  ·  더블클릭 상세/수정"
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
