"""모달 다이얼로그 — 행 편집, 텍스트 뷰어, 히스토리, 단축키."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Optional

from .display_utils import is_long_text_column, try_pretty_json
from .theme import MONO_FONT, MONO_FONT_LG, Palette, UI_FONT, UI_FONT_BOLD, UI_FONT_SMALL
from .widgets import ScrollableFrame


class TextViewer(tk.Toplevel):
    """긴 텍스트 / JSON 전체 보기."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        content: str,
        palette: Optional[Palette] = None,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.geometry("820x600")
        self.minsize(480, 320)
        self.transient(parent)
        p = palette

        if p:
            self.configure(bg=p.bg)

        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")
        ttk.Label(bar, text=title, style="Title.TLabel").pack(side="left")
        ttk.Button(bar, text="닫기  Esc", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="복사", command=lambda: self._copy(content)).pack(
            side="right", padx=6
        )
        self._wrap_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            bar,
            text="줄바꿈",
            variable=self._wrap_var,
            command=self._toggle_wrap,
        ).pack(side="right", padx=6)

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        bg = p.editor_bg if p else "#0f172a"
        fg = p.editor_fg if p else "#e2e8f0"
        self.text = tk.Text(
            frame,
            wrap="word",
            font=MONO_FONT_LG,
            undo=False,
            bg=bg,
            fg=fg,
            insertbackground=fg,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=p.border if p else "#334155",
            padx=12,
            pady=12,
        )
        sy = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sy.set)
        self.text.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")
        self.text.insert("1.0", content)
        self.text.configure(state="disabled")
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-c>", lambda e: self._copy(content))

    def _toggle_wrap(self) -> None:
        self.text.configure(state="normal")
        self.text.configure(wrap="word" if self._wrap_var.get() else "none")
        self.text.configure(state="disabled")

    def _copy(self, content: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("복사", "클립보드에 복사했습니다.", parent=self)


class RowDialog(tk.Toplevel):
    """Insert / Edit row dialog — 긴 필드는 멀티라인."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        columns: list[dict[str, Any]],
        values: Optional[dict[str, Any]] = None,
        readonly_pk: bool = False,
        palette: Optional[Palette] = None,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.result: Optional[dict[str, Any]] = None
        self.values = values or {}
        self.columns = columns
        self.readonly_pk = readonly_pk
        self.entries: dict[str, Any] = {}
        self.palette = palette

        if palette:
            self.configure(bg=palette.bg)

        self.geometry("700x620")
        self.minsize(520, 400)

        header = ttk.Frame(self, padding=(12, 10))
        header.pack(fill="x")
        ttk.Label(header, text=title, style="Title.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="* 필수  ·  [PK] 기본키",
            style="Muted.TLabel",
        ).pack(side="right")

        body = ScrollableFrame(self, palette=palette)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        for i, col in enumerate(columns):
            name = col["name"]
            label_parts = [name, f"({col['type'] or 'TEXT'})"]
            if col["pk"]:
                label_parts.append("[PK]")
            if col["notnull"] and not col["pk"]:
                label_parts.append("*")
            ttk.Label(body.inner, text=" ".join(label_parts), font=UI_FONT).grid(
                row=i, column=0, sticky="nw", padx=(4, 10), pady=8
            )

            raw_val = ""
            if name in self.values and self.values[name] is not None:
                raw_val = str(self.values[name])
                pretty = try_pretty_json(self.values[name])
                if pretty:
                    raw_val = pretty
            elif col["default"] is not None and name not in self.values:
                raw_val = str(col["default"])

            long_field = is_long_text_column(name, col.get("type") or "")
            state = "disabled" if (readonly_pk and col["pk"]) else "normal"
            editor_bg = palette.editor_bg if palette else "#0f172a"
            editor_fg = palette.editor_fg if palette else "#e2e8f0"

            if long_field:
                frame = ttk.Frame(body.inner)
                frame.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                txt = tk.Text(
                    frame,
                    height=6,
                    width=58,
                    wrap="word",
                    font=MONO_FONT,
                    state=state if state != "disabled" else "disabled",
                    bg=editor_bg,
                    fg=editor_fg,
                    insertbackground=editor_fg,
                    borderwidth=0,
                    highlightthickness=1,
                    highlightbackground=palette.border if palette else "#334155",
                    padx=8,
                    pady=6,
                )
                sy = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
                txt.configure(yscrollcommand=sy.set)
                txt.pack(side="left", fill="both", expand=True)
                sy.pack(side="right", fill="y")
                txt.configure(state="normal")
                txt.insert("1.0", raw_val)
                if state == "disabled":
                    txt.configure(state="disabled")
                self.entries[name] = txt
            else:
                var = tk.StringVar(value=raw_val)
                entry = ttk.Entry(
                    body.inner,
                    textvariable=var,
                    width=58,
                    state="readonly" if state == "disabled" else "normal",
                    font=UI_FONT,
                )
                entry.grid(row=i, column=1, sticky="ew", padx=4, pady=8)
                self.entries[name] = var

        body.inner.columnconfigure(1, weight=1)

        btns = ttk.Frame(self, padding=(12, 10))
        btns.pack(fill="x")
        ttk.Button(btns, text="취소  Esc", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="저장  Ctrl+S", style="Accent.TButton", command=self._save).pack(
            side="right", padx=4
        )

        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-s>", lambda e: self._save())
        self.bind("<Control-S>", lambda e: self._save())
        self.wait_visibility()
        self.focus_set()

    def _get_value(self, name: str) -> str:
        w = self.entries[name]
        if isinstance(w, tk.Text):
            return w.get("1.0", "end-1c")
        return w.get()

    def _save(self) -> None:
        data: dict[str, Any] = {}
        for col in self.columns:
            name = col["name"]
            if self.readonly_pk and col["pk"]:
                continue
            raw = self._get_value(name).strip()
            if raw == "":
                if col["notnull"] and not col["pk"] and col["default"] is None:
                    messagebox.showerror(
                        "입력 오류",
                        f"'{name}' 은(는) 필수 항목입니다.",
                        parent=self,
                    )
                    return
                if col["pk"] and not self.readonly_pk:
                    continue
                data[name] = None
            else:
                data[name] = self._coerce(raw, col["type"])
        self.result = data
        self.destroy()

    @staticmethod
    def _coerce(value: str, col_type: str) -> Any:
        t = (col_type or "").upper()
        if t in {"INTEGER", "INT", "BIGINT", "SMALLINT"}:
            try:
                return int(value)
            except ValueError:
                return value
        if t in {"REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL"}:
            try:
                return float(value)
            except ValueError:
                return value
        return value


class HistoryDialog(tk.Toplevel):
    """쿼리 히스토리 선택."""

    def __init__(
        self,
        parent: tk.Misc,
        history: list[str],
        palette: Optional[Palette] = None,
    ) -> None:
        super().__init__(parent)
        self.title("쿼리 히스토리")
        self.geometry("760x460")
        self.transient(parent)
        self.result: Optional[str] = None
        self._history = history
        p = palette
        if p:
            self.configure(bg=p.bg)

        ttk.Label(self, text="최근 실행 쿼리 (더블클릭으로 불러오기)", style="Muted.TLabel").pack(
            anchor="w", padx=12, pady=(10, 4)
        )

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=12, pady=4)

        self.lb = tk.Listbox(
            frame,
            font=MONO_FONT,
            activestyle="dotbox",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=p.border if p else "#334155",
            bg=p.editor_bg if p else "#0f172a",
            fg=p.editor_fg if p else "#e2e8f0",
            selectbackground=p.accent if p else "#2563eb",
            selectforeground="#ffffff",
        )
        sy = ttk.Scrollbar(frame, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=sy.set)
        self.lb.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")

        for i, q in enumerate(reversed(history), 1):
            preview = q.replace("\n", " ")[:160]
            self.lb.insert("end", f"{i:02d}  {preview}")

        btns = ttk.Frame(self, padding=10)
        btns.pack(fill="x")
        ttk.Button(btns, text="닫기", command=self.destroy).pack(side="right")
        ttk.Button(
            btns, text="편집기에 넣기", style="Accent.TButton", command=self._use
        ).pack(side="right", padx=6)

        self.lb.bind("<Double-1>", lambda e: self._use())
        self.bind("<Escape>", lambda e: self.destroy())
        self.lb.focus_set()

    def _use(self) -> None:
        sel = self.lb.curselection()
        if not sel:
            return
        idx = len(self._history) - 1 - int(sel[0])
        self.result = self._history[idx]
        self.destroy()


class ShortcutsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, palette: Optional[Palette] = None) -> None:
        super().__init__(parent)
        self.title("단축키")
        self.geometry("480x420")
        self.resizable(False, False)
        self.transient(parent)
        if palette:
            self.configure(bg=palette.bg)

        items = [
            ("F5 / Ctrl+Enter", "SQL 실행"),
            ("Ctrl+Shift+Enter", "선택 영역 실행"),
            ("Ctrl+O", "DB 열기"),
            ("Ctrl+R", "스키마/데이터 새로고침"),
            ("Ctrl+S", "행 편집 저장 (다이얼로그)"),
            ("Ctrl+,", "테마 전환"),
            ("Delete", "선택 행 삭제 (데이터 그리드 포커스 시)"),
            ("Ctrl+F", "데이터 검색 포커스"),
            ("Alt+Left / Right", "이전/다음 페이지"),
            ("더블클릭 (스키마)", "테이블 열기 + 샘플 SELECT"),
            ("더블클릭 (긴 셀)", "전체 보기"),
            ("더블클릭 (일반 셀)", "행 수정"),
            ("우클릭", "컨텍스트 메뉴"),
            ("WHERE 예", "member_id = 1"),
        ]

        ttk.Label(self, text="키보드 단축키", style="Title.TLabel").pack(
            anchor="w", padx=16, pady=(14, 8)
        )
        body = ttk.Frame(self, padding=(16, 0))
        body.pack(fill="both", expand=True)
        for i, (k, v) in enumerate(items):
            ttk.Label(body, text=k, font=UI_FONT_BOLD).grid(
                row=i, column=0, sticky="w", pady=3, padx=(0, 16)
            )
            ttk.Label(body, text=v, style="Muted.TLabel").grid(
                row=i, column=1, sticky="w", pady=3
            )

        ttk.Button(self, text="닫기", command=self.destroy).pack(pady=12)
        self.bind("<Escape>", lambda e: self.destroy())
