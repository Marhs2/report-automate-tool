"""SQL Workbench GUI — SQLite 조회 / 추가 / 수정 / 삭제."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Optional

# 패키지 실행(python -m sql_workbench)과 직접 실행(python app.py) 모두 지원
try:
    from .db_manager import DatabaseManager, QueryResult
    from .display_utils import (
        format_cell,
        format_detail,
        is_long_text_column,
        suggest_col_width,
        try_pretty_json,
    )
except ImportError:
    _here = Path(__file__).resolve().parent
    if str(_here) not in sys.path:
        sys.path.insert(0, str(_here))
    from db_manager import DatabaseManager, QueryResult
    from display_utils import (
        format_cell,
        format_detail,
        is_long_text_column,
        suggest_col_width,
        try_pretty_json,
    )

DEFAULT_DB = (
    Path(__file__).resolve().parent.parent / "backend" / "data" / "daily_reports.db"
)

PAGE_SIZES = (50, 100, 200, 500)
DEFAULT_PAGE_SIZE = 100
UI_FONT = ("Malgun Gothic", 10)
UI_FONT_BOLD = ("Malgun Gothic", 10, "bold")
UI_FONT_SMALL = ("Malgun Gothic", 9)
MONO_FONT = ("Consolas", 10)
MONO_FONT_LG = ("Consolas", 11)


class ScrollableFrame(ttk.Frame):
    """Vertical scroll container for forms."""

    def __init__(self, parent: tk.Misc, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
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


class TextViewer(tk.Toplevel):
    """긴 텍스트 / JSON 전체 보기."""

    def __init__(self, parent: tk.Misc, title: str, content: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.geometry("780x560")
        self.minsize(480, 320)
        self.transient(parent)

        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Button(bar, text="복사", command=lambda: self._copy(content)).pack(
            side="left"
        )
        ttk.Button(bar, text="닫기", command=self.destroy).pack(side="right")

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        text = tk.Text(frame, wrap="word", font=MONO_FONT_LG, undo=False)
        sy = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=sy.set)
        text.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")
        text.insert("1.0", content)
        text.configure(state="disabled")
        self.bind("<Escape>", lambda e: self.destroy())

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
        self.entries: dict[str, Any] = {}  # StringVar or Text

        self.geometry("640x560")
        self.minsize(480, 360)

        body = ScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        for i, col in enumerate(columns):
            name = col["name"]
            label_parts = [name, f"({col['type'] or 'TEXT'})"]
            if col["pk"]:
                label_parts.append("[PK]")
            if col["notnull"] and not col["pk"]:
                label_parts.append("*")
            ttk.Label(body.inner, text=" ".join(label_parts), font=UI_FONT).grid(
                row=i, column=0, sticky="nw", padx=4, pady=6
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

            if long_field:
                frame = ttk.Frame(body.inner)
                frame.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                txt = tk.Text(
                    frame,
                    height=6,
                    width=56,
                    wrap="word",
                    font=MONO_FONT,
                    state=state if state != "disabled" else "disabled",
                )
                sy = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
                txt.configure(yscrollcommand=sy.set)
                txt.pack(side="left", fill="both", expand=True)
                sy.pack(side="right", fill="y")
                if state != "disabled":
                    txt.insert("1.0", raw_val)
                else:
                    txt.configure(state="normal")
                    txt.insert("1.0", raw_val)
                    txt.configure(state="disabled")
                self.entries[name] = txt
            else:
                var = tk.StringVar(value=raw_val)
                entry = ttk.Entry(
                    body.inner,
                    textvariable=var,
                    width=56,
                    state="readonly" if state == "disabled" else "normal",
                    font=UI_FONT,
                )
                entry.grid(row=i, column=1, sticky="ew", padx=4, pady=6)
                self.entries[name] = var

        body.inner.columnconfigure(1, weight=1)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=10)
        ttk.Button(btns, text="취소", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="저장", command=self._save).pack(side="right", padx=4)

        self.bind("<Escape>", lambda e: self.destroy())
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
                # pretty JSON 편집 후 다시 compact 저장 가능하도록 그대로 둠
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


class SqlWorkbench(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("SQL Workbench")
        self.geometry("1400x880")
        self.minsize(1024, 640)

        self.db = DatabaseManager()
        self.current_table: Optional[str] = None
        self.page = 0
        self.page_size = DEFAULT_PAGE_SIZE
        self.total_rows = 0
        self.last_result: Optional[QueryResult] = None
        self.browse_columns: list[str] = []
        self.browse_rows: list[tuple] = []  # 원본 전체 값
        self.query_result_rows: list[tuple] = []
        self.query_result_columns: list[str] = []
        self.query_history: list[str] = []
        self._sort_col: Optional[str] = None
        self._sort_desc = False
        self._table_col_meta: dict[str, dict[str, Any]] = {}
        self.compact_long = tk.BooleanVar(value=True)

        self._setup_style()
        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_status()
        self._build_context_menus()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<F5>", lambda e: self._run_sql())
        self.bind("<Control-Return>", lambda e: self._run_sql())
        self.bind("<Control-o>", lambda e: self._open_db())
        self.bind("<Control-r>", lambda e: self._refresh_all())
        self.bind("<Delete>", lambda e: self._delete_row())

        if DEFAULT_DB.exists():
            self.after(100, lambda: self._connect_path(DEFAULT_DB))

    # ── UI construction ──────────────────────────────────────────

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        # clam: 행 배경색 태그 지원이 안정적
        if "clam" in style.theme_names():
            style.theme_use("clam")
        elif "vista" in style.theme_names():
            style.theme_use("vista")

        style.configure(".", font=UI_FONT)
        style.configure("Treeview", rowheight=26, font=UI_FONT, fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=UI_FONT_BOLD, padding=4)
        style.map(
            "Treeview",
            background=[("selected", "#2563eb")],
            foreground=[("selected", "#ffffff")],
        )
        style.configure("TButton", padding=(8, 4), font=UI_FONT)
        style.configure("Accent.TButton", padding=(10, 4), font=UI_FONT_BOLD)
        style.configure("Status.TLabel", font=UI_FONT_SMALL, foreground="#334155")
        style.configure("Title.TLabel", font=UI_FONT_BOLD)
        style.configure("Muted.TLabel", font=UI_FONT_SMALL, foreground="#64748b")
        style.configure("TLabelframe.Label", font=UI_FONT_BOLD)
        style.configure("TNotebook.Tab", padding=(12, 6), font=UI_FONT)

        self.option_add("*Font", UI_FONT)
        self.configure(bg="#f1f5f9")

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="파일", menu=file_menu)
        file_menu.add_command(label="DB 열기…  Ctrl+O", command=self._open_db)
        file_menu.add_command(label="새로고침  Ctrl+R", command=self._refresh_all)
        file_menu.add_separator()
        file_menu.add_command(label="결과 CSV 내보내기…", command=self._export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="종료", command=self._on_close)

        query_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="쿼리", menu=query_menu)
        query_menu.add_command(label="실행  F5", command=self._run_sql)
        query_menu.add_command(label="선택 영역 실행", command=self._run_selected_sql)
        query_menu.add_command(label="편집기 비우기", command=self._clear_editor)

        data_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="데이터", menu=data_menu)
        data_menu.add_command(label="행 추가", command=self._insert_row)
        data_menu.add_command(label="행 수정", command=self._edit_row)
        data_menu.add_command(label="행 삭제  Del", command=self._delete_row)
        data_menu.add_command(label="선택 행 상세 보기", command=self._view_row_detail)
        data_menu.add_separator()
        data_menu.add_command(label="테이블 데이터 새로고침", command=self._reload_table)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="보기", menu=view_menu)
        view_menu.add_checkbutton(
            label="긴 텍스트 요약 표시",
            variable=self.compact_long,
            command=self._reload_table,
        )

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="도움말", menu=help_menu)
        help_menu.add_command(label="단축키", command=self._show_shortcuts)
        help_menu.add_command(label="정보", command=self._show_about)

    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self, padding=(10, 8))
        bar.pack(fill="x")

        ttk.Button(bar, text="DB 열기", command=self._open_db).pack(side="left", padx=2)
        ttk.Button(bar, text="새로고침", command=self._refresh_all).pack(
            side="left", padx=2
        )
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(
            bar, text="▶ 실행 (F5)", style="Accent.TButton", command=self._run_sql
        ).pack(side="left", padx=2)
        ttk.Button(bar, text="선택 실행", command=self._run_selected_sql).pack(
            side="left", padx=2
        )
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(bar, text="+ 추가", command=self._insert_row).pack(
            side="left", padx=2
        )
        ttk.Button(bar, text="수정", command=self._edit_row).pack(side="left", padx=2)
        ttk.Button(bar, text="삭제", command=self._delete_row).pack(side="left", padx=2)
        ttk.Button(bar, text="상세 보기", command=self._view_row_detail).pack(
            side="left", padx=2
        )
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(bar, text="CSV 내보내기", command=self._export_csv).pack(
            side="left", padx=2
        )

        self.db_label = ttk.Label(bar, text="연결 안 됨", style="Status.TLabel")
        self.db_label.pack(side="right", padx=8)

    def _build_body(self) -> None:
        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        left = ttk.Frame(paned, width=260)
        paned.add(left, weight=1)

        ttk.Label(left, text="스키마", style="Title.TLabel").pack(
            anchor="w", padx=4, pady=(6, 4)
        )
        hint = ttk.Label(
            left, text="더블클릭: 데이터 열기", style="Muted.TLabel"
        )
        hint.pack(anchor="w", padx=4)

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True, pady=4)
        self.schema_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        sy = ttk.Scrollbar(tree_frame, orient="vertical", command=self.schema_tree.yview)
        self.schema_tree.configure(yscrollcommand=sy.set)
        self.schema_tree.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")
        self.schema_tree.bind("<<TreeviewSelect>>", self._on_schema_select)
        self.schema_tree.bind("<Double-1>", self._on_schema_double)

        right = ttk.Frame(paned)
        paned.add(right, weight=5)

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)

        self._build_browse_tab()
        self._build_query_tab()
        self._build_structure_tab()

    def _build_browse_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  데이터 브라우저  ")

        top = ttk.Frame(tab, padding=6)
        top.pack(fill="x")

        ttk.Label(top, text="테이블").pack(side="left")
        self.table_var = tk.StringVar()
        self.table_combo = ttk.Combobox(
            top, textvariable=self.table_var, state="readonly", width=24, font=UI_FONT
        )
        self.table_combo.pack(side="left", padx=6)
        self.table_combo.bind("<<ComboboxSelected>>", lambda e: self._on_table_combo())

        ttk.Label(top, text="WHERE").pack(side="left", padx=(10, 2))
        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(top, textvariable=self.filter_var, width=36, font=UI_FONT)
        filter_entry.pack(side="left", padx=2)
        filter_entry.bind("<Return>", lambda e: self._reload_table(reset_page=True))

        ttk.Button(
            top, text="적용", command=lambda: self._reload_table(reset_page=True)
        ).pack(side="left", padx=2)
        ttk.Button(top, text="초기화", command=self._clear_filter).pack(
            side="left", padx=2
        )

        ttk.Label(top, text="검색").pack(side="left", padx=(12, 2))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(top, textvariable=self.search_var, width=18, font=UI_FONT)
        search_entry.pack(side="left", padx=2)
        search_entry.bind("<Return>", lambda e: self._apply_client_search())
        ttk.Button(top, text="찾기", command=self._apply_client_search).pack(
            side="left", padx=2
        )

        ttk.Checkbutton(
            top,
            text="긴 텍스트 요약",
            variable=self.compact_long,
            command=self._reload_table,
        ).pack(side="right", padx=4)

        # 세로 분할: 그리드 + 상세 미리보기
        vpaned = ttk.Panedwindow(tab, orient="vertical")
        vpaned.pack(fill="both", expand=True, padx=6, pady=4)

        grid_wrap = ttk.Frame(vpaned)
        vpaned.add(grid_wrap, weight=3)

        grid_frame = ttk.Frame(grid_wrap)
        grid_frame.pack(fill="both", expand=True)

        self.browse_tree = ttk.Treeview(
            grid_frame, show="headings", selectmode="extended"
        )
        by = ttk.Scrollbar(grid_frame, orient="vertical", command=self.browse_tree.yview)
        bx = ttk.Scrollbar(
            grid_frame, orient="horizontal", command=self.browse_tree.xview
        )
        self.browse_tree.configure(yscrollcommand=by.set, xscrollcommand=bx.set)
        self.browse_tree.grid(row=0, column=0, sticky="nsew")
        by.grid(row=0, column=1, sticky="ns")
        bx.grid(row=1, column=0, sticky="ew")
        grid_frame.rowconfigure(0, weight=1)
        grid_frame.columnconfigure(0, weight=1)
        self.browse_tree.bind("<<TreeviewSelect>>", self._on_browse_select)
        self.browse_tree.bind("<Double-1>", self._on_browse_double)
        self.browse_tree.tag_configure("odd", background="#ffffff")
        self.browse_tree.tag_configure("even", background="#f8fafc")

        detail_wrap = ttk.LabelFrame(vpaned, text="선택 행 미리보기 (읽기 쉬운 JSON)", padding=4)
        vpaned.add(detail_wrap, weight=2)

        dbar = ttk.Frame(detail_wrap)
        dbar.pack(fill="x", pady=(0, 4))
        self.detail_col_var = tk.StringVar()
        self.detail_col_combo = ttk.Combobox(
            dbar,
            textvariable=self.detail_col_var,
            state="readonly",
            width=28,
            font=UI_FONT,
        )
        self.detail_col_combo.pack(side="left")
        self.detail_col_combo.bind("<<ComboboxSelected>>", self._show_selected_cell_detail)
        ttk.Button(dbar, text="전체 창으로 보기", command=self._open_detail_window).pack(
            side="left", padx=6
        )
        ttk.Button(dbar, text="값 복사", command=self._copy_detail).pack(side="left")
        ttk.Button(dbar, text="행 수정", command=self._edit_row).pack(side="right")

        dframe = ttk.Frame(detail_wrap)
        dframe.pack(fill="both", expand=True)
        self.detail_text = tk.Text(
            dframe,
            height=10,
            wrap="word",
            font=MONO_FONT,
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            relief="flat",
            padx=8,
            pady=8,
        )
        dsy = ttk.Scrollbar(dframe, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=dsy.set)
        self.detail_text.pack(side="left", fill="both", expand=True)
        dsy.pack(side="right", fill="y")
        self.detail_text.insert("1.0", "행을 선택하면 여기에 전체 내용이 표시됩니다.")
        self.detail_text.configure(state="disabled")

        # Pagination
        page_bar = ttk.Frame(tab, padding=6)
        page_bar.pack(fill="x")
        ttk.Button(page_bar, text="◀ 이전", command=self._prev_page).pack(side="left")
        ttk.Button(page_bar, text="다음 ▶", command=self._next_page).pack(
            side="left", padx=4
        )
        self.page_label = ttk.Label(page_bar, text="페이지 -", style="Muted.TLabel")
        self.page_label.pack(side="left", padx=12)

        ttk.Label(page_bar, text="페이지 크기").pack(side="left", padx=(16, 4))
        self.page_size_var = tk.StringVar(value=str(DEFAULT_PAGE_SIZE))
        ps = ttk.Combobox(
            page_bar,
            textvariable=self.page_size_var,
            values=[str(x) for x in PAGE_SIZES],
            width=6,
            state="readonly",
        )
        ps.pack(side="left")
        ps.bind("<<ComboboxSelected>>", self._on_page_size)

        ttk.Button(page_bar, text="행 추가", command=self._insert_row).pack(side="right")
        ttk.Button(page_bar, text="행 수정", command=self._edit_row).pack(
            side="right", padx=4
        )
        ttk.Button(page_bar, text="행 삭제", command=self._delete_row).pack(
            side="right", padx=4
        )

    def _build_query_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  SQL 쿼리  ")

        vpaned = ttk.Panedwindow(tab, orient="vertical")
        vpaned.pack(fill="both", expand=True, padx=6, pady=6)

        editor_frame = ttk.LabelFrame(vpaned, text="SQL 편집기", padding=4)
        vpaned.add(editor_frame, weight=2)

        self.sql_text = tk.Text(
            editor_frame,
            height=10,
            wrap="none",
            font=MONO_FONT_LG,
            undo=True,
            bg="#1e293b",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
            padx=8,
            pady=8,
        )
        esy = ttk.Scrollbar(editor_frame, orient="vertical", command=self.sql_text.yview)
        esx = ttk.Scrollbar(
            editor_frame, orient="horizontal", command=self.sql_text.xview
        )
        self.sql_text.configure(yscrollcommand=esy.set, xscrollcommand=esx.set)
        self.sql_text.grid(row=0, column=0, sticky="nsew")
        esy.grid(row=0, column=1, sticky="ns")
        esx.grid(row=1, column=0, sticky="ew")
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)

        # 간단 키워드 색상 흉내 (tag)
        self.sql_text.tag_configure("kw", foreground="#7dd3fc")

        qbar = ttk.Frame(tab, padding=(6, 0))
        qbar.pack(fill="x")
        ttk.Button(
            qbar, text="▶ 실행 (F5)", style="Accent.TButton", command=self._run_sql
        ).pack(side="left")
        ttk.Button(qbar, text="선택 실행", command=self._run_selected_sql).pack(
            side="left", padx=4
        )
        ttk.Button(qbar, text="비우기", command=self._clear_editor).pack(side="left")
        ttk.Button(qbar, text="히스토리", command=self._show_history).pack(
            side="left", padx=4
        )
        ttk.Button(qbar, text="샘플 쿼리", command=self._insert_sample).pack(
            side="left", padx=4
        )

        result_frame = ttk.LabelFrame(vpaned, text="결과", padding=4)
        vpaned.add(result_frame, weight=3)

        self.result_tree = ttk.Treeview(
            result_frame, show="headings", selectmode="browse"
        )
        rsy = ttk.Scrollbar(
            result_frame, orient="vertical", command=self.result_tree.yview
        )
        rsx = ttk.Scrollbar(
            result_frame, orient="horizontal", command=self.result_tree.xview
        )
        self.result_tree.configure(yscrollcommand=rsy.set, xscrollcommand=rsx.set)
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        rsy.grid(row=0, column=1, sticky="ns")
        rsx.grid(row=1, column=0, sticky="ew")
        result_frame.rowconfigure(0, weight=1)
        result_frame.columnconfigure(0, weight=1)
        self.result_tree.tag_configure("odd", background="#ffffff")
        self.result_tree.tag_configure("even", background="#f8fafc")
        self.result_tree.bind("<Double-1>", self._on_result_double)

    def _build_structure_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  테이블 구조  ")

        info_top = ttk.Frame(tab, padding=6)
        info_top.pack(fill="x")
        self.structure_title = ttk.Label(
            info_top, text="테이블을 선택하세요", style="Title.TLabel"
        )
        self.structure_title.pack(side="left")

        cols_frame = ttk.LabelFrame(tab, text="컬럼", padding=4)
        cols_frame.pack(fill="both", expand=True, padx=6, pady=4)

        self.struct_tree = ttk.Treeview(
            cols_frame,
            columns=("name", "type", "pk", "notnull", "default"),
            show="headings",
        )
        for col, text, w in [
            ("name", "이름", 180),
            ("type", "타입", 100),
            ("pk", "PK", 50),
            ("notnull", "NOT NULL", 90),
            ("default", "DEFAULT", 180),
        ]:
            self.struct_tree.heading(col, text=text)
            self.struct_tree.column(col, width=w, anchor="w")
        ssy = ttk.Scrollbar(
            cols_frame, orient="vertical", command=self.struct_tree.yview
        )
        self.struct_tree.configure(yscrollcommand=ssy.set)
        self.struct_tree.pack(side="left", fill="both", expand=True)
        ssy.pack(side="right", fill="y")

        ddl_frame = ttk.LabelFrame(tab, text="CREATE SQL / 외래키", padding=4)
        ddl_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.ddl_text = tk.Text(
            ddl_frame,
            height=8,
            wrap="word",
            font=MONO_FONT,
            state="disabled",
            bg="#f8fafc",
        )
        self.ddl_text.pack(fill="both", expand=True)

    def _build_status(self) -> None:
        self.status_var = tk.StringVar(value="준비")
        bar = ttk.Frame(self, padding=(10, 6))
        bar.pack(fill="x", side="bottom")
        ttk.Separator(self, orient="horizontal").pack(fill="x", side="bottom")
        ttk.Label(bar, textvariable=self.status_var, style="Status.TLabel").pack(
            side="left"
        )
        self.hint_var = tk.StringVar(
            value="팁: 행 선택 → 하단 미리보기  |  더블클릭 → 수정  |  F5 → SQL 실행"
        )
        ttk.Label(bar, textvariable=self.hint_var, style="Muted.TLabel").pack(
            side="right"
        )

    def _build_context_menus(self) -> None:
        self.browse_menu = tk.Menu(self, tearoff=0)
        self.browse_menu.add_command(label="상세 보기", command=self._view_row_detail)
        self.browse_menu.add_command(label="수정", command=self._edit_row)
        self.browse_menu.add_command(label="삭제", command=self._delete_row)
        self.browse_menu.add_separator()
        self.browse_menu.add_command(label="셀 값 복사", command=self._copy_selected_cell)
        self.browse_menu.add_command(label="행 복사 (TSV)", command=self._copy_selected_row)
        self.browse_tree.bind("<Button-3>", self._popup_browse_menu)

    def _popup_browse_menu(self, event: tk.Event) -> None:
        row_id = self.browse_tree.identify_row(event.y)
        if row_id:
            self.browse_tree.selection_set(row_id)
            self.browse_tree.focus(row_id)
            self._on_browse_select()
        try:
            self.browse_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.browse_menu.grab_release()

    # ── Connection / schema ──────────────────────────────────────

    def _open_db(self) -> None:
        path = filedialog.askopenfilename(
            title="SQLite DB 열기",
            filetypes=[
                ("SQLite DB", "*.db *.sqlite *.sqlite3"),
                ("모든 파일", "*.*"),
            ],
            initialdir=str(
                DEFAULT_DB.parent if DEFAULT_DB.parent.exists() else Path.cwd()
            ),
        )
        if path:
            self._connect_path(Path(path))

    def _connect_path(self, path: Path) -> None:
        try:
            self.db.connect(path)
        except Exception as e:
            messagebox.showerror("연결 실패", str(e), parent=self)
            return
        self.db_label.config(text=f"DB: {path.name}")
        self.title(f"SQL Workbench — {path}")
        self._set_status(f"연결됨: {path}")
        self._refresh_schema()
        tables = self.db.list_tables()
        if tables:
            # daily_reports 우선
            preferred = "daily_reports" if "daily_reports" in tables else tables[0]
            self.table_var.set(preferred)
            self.current_table = preferred
            self._reload_table(reset_page=True)
            self._load_structure(preferred)

    def _refresh_all(self) -> None:
        if not self.db.is_connected:
            return
        self._refresh_schema()
        if self.current_table:
            self._reload_table()
            self._load_structure(self.current_table)
        self._set_status("새로고침 완료")

    def _refresh_schema(self) -> None:
        self.schema_tree.delete(*self.schema_tree.get_children())
        if not self.db.is_connected:
            return

        tables = self.db.list_tables()
        views = self.db.list_views()
        self.table_combo["values"] = tables

        root_t = self.schema_tree.insert(
            "", "end", text=f"Tables ({len(tables)})", open=True
        )
        for t in tables:
            try:
                cnt = self.db.count_rows(t)
                label = f"{t}  ({cnt})"
            except Exception:
                label = t
            tid = self.schema_tree.insert(
                root_t, "end", text=label, values=(t,), tags=("table",)
            )
            try:
                for col in self.db.get_table_info(t):
                    pk = " 🔑" if col["pk"] else ""
                    self.schema_tree.insert(
                        tid,
                        "end",
                        text=f"{col['name']} : {col['type']}{pk}",
                        tags=("column",),
                    )
            except Exception:
                pass

        if views:
            root_v = self.schema_tree.insert(
                "", "end", text=f"Views ({len(views)})", open=True
            )
            for v in views:
                self.schema_tree.insert(
                    root_v, "end", text=v, values=(v,), tags=("view",)
                )

    def _on_schema_select(self, _event: Any = None) -> None:
        item = self.schema_tree.focus()
        if not item:
            return
        tags = self.schema_tree.item(item, "tags")
        if "table" in tags or "view" in tags:
            vals = self.schema_tree.item(item, "values")
            name = vals[0] if vals else self.schema_tree.item(item, "text").split()[0]
            self.current_table = name
            self.table_var.set(name)
            self._load_structure(name)

    def _on_schema_double(self, _event: Any = None) -> None:
        item = self.schema_tree.focus()
        if not item:
            return
        tags = self.schema_tree.item(item, "tags")
        if "table" in tags or "view" in tags:
            vals = self.schema_tree.item(item, "values")
            name = vals[0] if vals else self.schema_tree.item(item, "text").split()[0]
            self.current_table = name
            self.table_var.set(name)
            self._reload_table(reset_page=True)
            self._load_structure(name)
            self.notebook.select(0)
            self.sql_text.delete("1.0", "end")
            self.sql_text.insert(
                "1.0", f'SELECT * FROM "{name}" ORDER BY rowid DESC LIMIT 100;\n'
            )

    def _on_table_combo(self) -> None:
        name = self.table_var.get()
        if name:
            self.current_table = name
            self._reload_table(reset_page=True)
            self._load_structure(name)

    def _on_page_size(self, _event: Any = None) -> None:
        try:
            self.page_size = int(self.page_size_var.get())
        except ValueError:
            self.page_size = DEFAULT_PAGE_SIZE
        self._reload_table(reset_page=True)

    # ── Browse data ──────────────────────────────────────────────

    def _clear_filter(self) -> None:
        self.filter_var.set("")
        self.search_var.set("")
        self._reload_table(reset_page=True)

    def _default_order_col(self, table: str) -> Optional[str]:
        try:
            cols = self.db.get_table_info(table)
        except Exception:
            return None
        names = [c["name"] for c in cols]
        if "id" in names:
            return "id"
        pks = [c["name"] for c in cols if c["pk"]]
        return pks[0] if pks else None

    def _reload_table(self, reset_page: bool = False) -> None:
        if not self.db.is_connected or not self.current_table:
            return
        if reset_page:
            self.page = 0
            if self._sort_col is None:
                self._sort_col = self._default_order_col(self.current_table)
                self._sort_desc = True

        where = self.filter_var.get().strip() or None
        try:
            meta = self.db.get_table_info(self.current_table)
            self._table_col_meta = {c["name"]: c for c in meta}
            self.total_rows = self.db.count_rows(self.current_table, where=where)
            result = self.db.fetch_table(
                self.current_table,
                limit=self.page_size,
                offset=self.page * self.page_size,
                order_by=self._sort_col,
                order_desc=self._sort_desc,
                where=where,
            )
        except Exception as e:
            messagebox.showerror("조회 오류", str(e), parent=self)
            self._set_status(f"오류: {e}")
            return

        self.browse_columns = result.columns
        self.browse_rows = result.rows
        self.detail_col_combo["values"] = result.columns
        if result.columns and (
            not self.detail_col_var.get()
            or self.detail_col_var.get() not in result.columns
        ):
            # 긴 텍스트 컬럼 우선
            preferred = next(
                (
                    c
                    for c in result.columns
                    if is_long_text_column(
                        c, (self._table_col_meta.get(c) or {}).get("type", "")
                    )
                ),
                result.columns[0],
            )
            self.detail_col_var.set(preferred)

        self._fill_tree(
            self.browse_tree,
            result.columns,
            result.rows,
            compact=self.compact_long.get(),
        )

        for col in result.columns:
            arrow = ""
            if self._sort_col == col:
                arrow = " ▼" if self._sort_desc else " ▲"
            self.browse_tree.heading(
                col,
                text=f"{col}{arrow}",
                command=lambda c=col: self._sort_by(c),
            )

        start = self.page * self.page_size + 1 if result.rows else 0
        end = self.page * self.page_size + len(result.rows)
        self.page_label.config(
            text=f"{start}–{end} / 전체 {self.total_rows}행  |  페이지 {self.page + 1}"
        )
        self._set_status(result.message)
        self._set_detail_text("행을 선택하면 여기에 전체 내용이 표시됩니다.")

        # 클라이언트 검색 유지
        if self.search_var.get().strip():
            self._apply_client_search()

    def _sort_by(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = False
        self._reload_table()

    def _prev_page(self) -> None:
        if self.page > 0:
            self.page -= 1
            self._reload_table()

    def _next_page(self) -> None:
        if (self.page + 1) * self.page_size < self.total_rows:
            self.page += 1
            self._reload_table()

    def _apply_client_search(self) -> None:
        q = self.search_var.get().strip().lower()
        if not q:
            self._fill_tree(
                self.browse_tree,
                self.browse_columns,
                self.browse_rows,
                compact=self.compact_long.get(),
            )
            return
        filtered = []
        for row in self.browse_rows:
            if any(q in str(v).lower() for v in row if v is not None):
                filtered.append(row)
        self._fill_tree(
            self.browse_tree,
            self.browse_columns,
            filtered,
            compact=self.compact_long.get(),
            source_rows=filtered,
        )
        self._set_status(f"검색 '{q}': {len(filtered)}행 (현재 페이지 내)")

    # ── Selection / detail ───────────────────────────────────────

    def _selected_row_index(self) -> Optional[int]:
        sel = self.browse_tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _selected_raw_row(self) -> Optional[dict[str, Any]]:
        """원본 값 dict (표시용 잘린 문자열 아님)."""
        idx = self._selected_row_index()
        if idx is None or not self.browse_columns:
            return None
        # iid 는 현재 tree에 채워진 순번. source mapping 사용
        item = self.browse_tree.selection()[0]
        tags = self.browse_tree.item(item, "tags")
        raw_idx = None
        for t in tags:
            if t.startswith("idx:"):
                raw_idx = int(t.split(":", 1)[1])
                break
        if raw_idx is None:
            try:
                raw_idx = int(item)
            except ValueError:
                return None
        # browse_rows may be filtered - we stored absolute index in tag against filled list
        # When filling we use enumerate over the rows passed in, and tag with that row's id from original
        rows = getattr(self, "_tree_source_rows", self.browse_rows)
        if raw_idx < 0 or raw_idx >= len(rows):
            return None
        return dict(zip(self.browse_columns, rows[raw_idx]))

    def _on_browse_select(self, _event: Any = None) -> None:
        row = self._selected_raw_row()
        if not row:
            return
        col = self.detail_col_var.get()
        if col and col in row:
            self._set_detail_text(format_detail(row[col], col))
        else:
            # 전체 행 요약
            lines = []
            for k, v in row.items():
                preview = format_cell(v, k, max_len=120)
                lines.append(f"{k}: {preview}")
            self._set_detail_text("\n".join(lines))

    def _show_selected_cell_detail(self, _event: Any = None) -> None:
        self._on_browse_select()

    def _set_detail_text(self, text: str) -> None:
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")

    def _on_browse_double(self, event: tk.Event) -> None:
        region = self.browse_tree.identify("region", event.x, event.y)
        if region == "cell":
            col_id = self.browse_tree.identify_column(event.x)
            # #1, #2, ...
            try:
                col_index = int(col_id.replace("#", "")) - 1
            except ValueError:
                col_index = -1
            if 0 <= col_index < len(self.browse_columns):
                self.detail_col_var.set(self.browse_columns[col_index])
                row = self._selected_raw_row()
                if row:
                    col = self.browse_columns[col_index]
                    val = row.get(col)
                    # 긴 필드면 상세 창, 아니면 수정
                    meta = self._table_col_meta.get(col, {})
                    if is_long_text_column(col, meta.get("type", "")):
                        TextViewer(
                            self,
                            f"{self.current_table}.{col}",
                            format_detail(val, col),
                        )
                        return
        self._edit_row()

    def _view_row_detail(self) -> None:
        row = self._selected_raw_row()
        if not row:
            messagebox.showinfo("알림", "행을 선택하세요.", parent=self)
            return
        parts = []
        for k, v in row.items():
            parts.append(f"══ {k} ══\n{format_detail(v, k)}\n")
        TextViewer(self, f"행 상세 — {self.current_table}", "\n".join(parts))

    def _open_detail_window(self) -> None:
        content = self.detail_text.get("1.0", "end-1c")
        col = self.detail_col_var.get() or "detail"
        TextViewer(self, f"{self.current_table}.{col}", content)

    def _copy_detail(self) -> None:
        content = self.detail_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)
        self._set_status("미리보기 내용 복사됨")

    def _copy_selected_cell(self) -> None:
        row = self._selected_raw_row()
        col = self.detail_col_var.get()
        if not row or not col or col not in row:
            messagebox.showinfo("알림", "행/컬럼을 선택하세요.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append("" if row[col] is None else str(row[col]))
        self._set_status(f"복사됨: {col}")

    def _copy_selected_row(self) -> None:
        row = self._selected_raw_row()
        if not row:
            return
        line = "\t".join("" if v is None else str(v) for v in row.values())
        self.clipboard_clear()
        self.clipboard_append(line)
        self._set_status("행 복사됨 (TSV)")

    def _on_result_double(self, _event: Any = None) -> None:
        sel = self.result_tree.selection()
        if not sel or not self.query_result_columns:
            return
        item = sel[0]
        tags = self.result_tree.item(item, "tags")
        raw_idx = None
        for t in tags:
            if t.startswith("idx:"):
                raw_idx = int(t.split(":", 1)[1])
        if raw_idx is None:
            return
        if raw_idx >= len(self.query_result_rows):
            return
        row = dict(zip(self.query_result_columns, self.query_result_rows[raw_idx]))
        parts = [
            f"══ {k} ══\n{format_detail(v, k)}\n" for k, v in row.items()
        ]
        TextViewer(self, "쿼리 결과 상세", "\n".join(parts))

    # ── CRUD ─────────────────────────────────────────────────────

    def _require_table(self) -> Optional[str]:
        if not self.db.is_connected:
            messagebox.showwarning("알림", "DB에 먼저 연결하세요.", parent=self)
            return None
        if not self.current_table:
            messagebox.showwarning("알림", "테이블을 선택하세요.", parent=self)
            return None
        return self.current_table

    def _insert_row(self) -> None:
        table = self._require_table()
        if not table:
            return
        try:
            cols = self.db.get_table_info(table)
        except Exception as e:
            messagebox.showerror("오류", str(e), parent=self)
            return

        dlg = RowDialog(self, f"행 추가 — {table}", cols)
        self.wait_window(dlg)
        if not dlg.result:
            return
        try:
            row_id = self.db.insert_row(table, dlg.result)
            self._set_status(f"행 추가됨 (id={row_id})")
            self._refresh_schema()
            self._reload_table()
        except Exception as e:
            messagebox.showerror("추가 실패", str(e), parent=self)

    def _edit_row(self) -> None:
        table = self._require_table()
        if not table:
            return
        row = self._selected_raw_row()
        if not row:
            messagebox.showinfo("알림", "수정할 행을 선택하세요.", parent=self)
            return

        try:
            cols = self.db.get_table_info(table)
            pks = self.db.get_primary_keys(table)
        except Exception as e:
            messagebox.showerror("오류", str(e), parent=self)
            return

        if not pks:
            messagebox.showwarning(
                "알림",
                "Primary Key가 없어 GUI 수정을 지원하지 않습니다.\n"
                "SQL 쿼리 탭에서 UPDATE를 실행하세요.",
                parent=self,
            )
            return

        dlg = RowDialog(
            self, f"행 수정 — {table}", cols, values=row, readonly_pk=True
        )
        self.wait_window(dlg)
        if not dlg.result:
            return

        pk_info = {c["name"]: c for c in cols}
        coerced_pks = [
            RowDialog._coerce(str(row[pk]), pk_info[pk]["type"]) for pk in pks
        ]

        try:
            n = self.db.update_row(table, dlg.result, pks, coerced_pks)
            self._set_status(f"{n}행 수정됨")
            self._reload_table()
        except Exception as e:
            messagebox.showerror("수정 실패", str(e), parent=self)

    def _delete_row(self) -> None:
        table = self._require_table()
        if not table:
            return
        selections = self.browse_tree.selection()
        if not selections:
            messagebox.showinfo("알림", "삭제할 행을 선택하세요.", parent=self)
            return

        try:
            cols = self.db.get_table_info(table)
            pks = self.db.get_primary_keys(table)
        except Exception as e:
            messagebox.showerror("오류", str(e), parent=self)
            return

        if not pks:
            messagebox.showwarning(
                "알림",
                "Primary Key가 없어 GUI 삭제를 지원하지 않습니다.",
                parent=self,
            )
            return

        if not messagebox.askyesno(
            "삭제 확인",
            f"선택한 {len(selections)}개 행을 삭제할까요?\n이 작업은 되돌릴 수 없습니다.",
            parent=self,
        ):
            return

        pk_info = {c["name"]: c for c in cols}
        rows = getattr(self, "_tree_source_rows", self.browse_rows)
        deleted = 0
        try:
            for item in selections:
                tags = self.browse_tree.item(item, "tags")
                raw_idx = None
                for t in tags:
                    if t.startswith("idx:"):
                        raw_idx = int(t.split(":", 1)[1])
                if raw_idx is None:
                    continue
                row = dict(zip(self.browse_columns, rows[raw_idx]))
                pk_values = [
                    RowDialog._coerce(str(row[pk]), pk_info[pk]["type"]) for pk in pks
                ]
                deleted += self.db.delete_row(table, pks, pk_values)
            self._set_status(f"{deleted}행 삭제됨")
            self._refresh_schema()
            self._reload_table()
        except Exception as e:
            messagebox.showerror("삭제 실패", str(e), parent=self)

    # ── SQL query ───────────────────────────────────────────────

    def _run_sql(self) -> None:
        if not self.db.is_connected:
            messagebox.showwarning("알림", "DB에 먼저 연결하세요.", parent=self)
            return
        sql = self.sql_text.get("1.0", "end").strip()
        if not sql:
            messagebox.showinfo("알림", "실행할 SQL을 입력하세요.", parent=self)
            return
        self._execute_sql(sql)

    def _run_selected_sql(self) -> None:
        if not self.db.is_connected:
            messagebox.showwarning("알림", "DB에 먼저 연결하세요.", parent=self)
            return
        try:
            sql = self.sql_text.get("sel.first", "sel.last").strip()
        except tk.TclError:
            sql = ""
        if not sql:
            messagebox.showinfo("알림", "실행할 영역을 선택하세요.", parent=self)
            return
        self._execute_sql(sql)

    def _execute_sql(self, sql: str) -> None:
        try:
            result = self.db.execute(sql)
        except Exception as e:
            messagebox.showerror("SQL 오류", str(e), parent=self)
            self._set_status(f"오류: {e}")
            return

        self.last_result = result
        self.query_history.append(sql)
        if len(self.query_history) > 50:
            self.query_history = self.query_history[-50:]

        if result.is_select:
            self.query_result_columns = result.columns
            self.query_result_rows = result.rows
            self._fill_tree(
                self.result_tree, result.columns, result.rows, compact=True
            )
            self.notebook.select(1)
        else:
            self.query_result_columns = ["message"]
            self.query_result_rows = [(result.message,)]
            self._fill_tree(
                self.result_tree, ["message"], [(result.message,)], compact=False
            )
            self._refresh_schema()
            if self.current_table:
                self._reload_table()

        self._set_status(result.message)

    def _clear_editor(self) -> None:
        self.sql_text.delete("1.0", "end")

    def _show_history(self) -> None:
        if not self.query_history:
            messagebox.showinfo("히스토리", "실행 기록이 없습니다.", parent=self)
            return
        win = tk.Toplevel(self)
        win.title("쿼리 히스토리")
        win.geometry("720x420")
        win.transient(self)
        lb = tk.Listbox(win, font=MONO_FONT)
        lb.pack(fill="both", expand=True, padx=8, pady=8)
        for i, q in enumerate(reversed(self.query_history), 1):
            preview = q.replace("\n", " ")[:140]
            lb.insert("end", f"{i}. {preview}")

        def use_selected() -> None:
            sel = lb.curselection()
            if not sel:
                return
            idx = len(self.query_history) - 1 - sel[0]
            self.sql_text.delete("1.0", "end")
            self.sql_text.insert("1.0", self.query_history[idx])
            win.destroy()
            self.notebook.select(1)

        ttk.Button(win, text="편집기에 넣기", command=use_selected).pack(pady=8)
        lb.bind("<Double-1>", lambda e: use_selected())

    def _insert_sample(self) -> None:
        samples = """-- 멤버 목록
SELECT * FROM members ORDER BY id;

-- 일일 보고서 (최근순)
SELECT id, member_id, report_date,
       substr(raw_text, 1, 80) AS raw_preview,
       created_at
FROM daily_reports
ORDER BY id DESC
LIMIT 50;

-- 일일 보고서 + 멤버 이름 (members에 데이터가 있을 때)
SELECT d.id, m.name AS member_name, d.report_date,
       substr(d.raw_text, 1, 100) AS raw_preview, d.created_at
FROM daily_reports d
LEFT JOIN members m ON m.id = d.member_id
ORDER BY d.report_date DESC
LIMIT 50;

-- 프로젝트 현황
SELECT * FROM projects ORDER BY id DESC LIMIT 50;

-- 멤버 추가 예시
-- INSERT INTO members (name) VALUES ('홍길동');

-- 보고서 수정 예시
-- UPDATE daily_reports SET raw_text = '내용' WHERE id = 1;
"""
        self.sql_text.delete("1.0", "end")
        self.sql_text.insert("1.0", samples)
        self.notebook.select(1)

    # ── Structure ────────────────────────────────────────────────

    def _load_structure(self, table: str) -> None:
        if not self.db.is_connected:
            return
        self.structure_title.config(text=f"테이블: {table}")
        self.struct_tree.delete(*self.struct_tree.get_children())
        try:
            cols = self.db.get_table_info(table)
            for c in cols:
                self.struct_tree.insert(
                    "",
                    "end",
                    values=(
                        c["name"],
                        c["type"],
                        "YES" if c["pk"] else "",
                        "YES" if c["notnull"] else "",
                        c["default"] if c["default"] is not None else "",
                    ),
                )
            ddl = self.db.get_create_sql(table) or "(DDL 없음)"
            fks = self.db.get_foreign_keys(table)
            fk_text = ""
            if fks:
                lines = [
                    f"  {f['from']} → {f['table']}.{f['to']} "
                    f"(ON UPDATE {f['on_update']}, ON DELETE {f['on_delete']})"
                    for f in fks
                ]
                fk_text = "\n\nForeign Keys:\n" + "\n".join(lines)
            try:
                cnt = self.db.count_rows(table)
                fk_text += f"\n\nRow count: {cnt}"
            except Exception:
                pass

            self.ddl_text.configure(state="normal")
            self.ddl_text.delete("1.0", "end")
            self.ddl_text.insert("1.0", ddl + fk_text)
            self.ddl_text.configure(state="disabled")
        except Exception as e:
            self._set_status(f"구조 로드 실패: {e}")

    # ── Tree helpers / export ────────────────────────────────────

    def _fill_tree(
        self,
        tree: ttk.Treeview,
        columns: list[str],
        rows: list[tuple],
        compact: bool = True,
        source_rows: Optional[list[tuple]] = None,
    ) -> None:
        tree.delete(*tree.get_children())
        tree["columns"] = columns

        # 폭 계산용 샘플
        col_samples: dict[str, list[Any]] = {c: [] for c in columns}
        for row in rows[:30]:
            for c, v in zip(columns, row):
                col_samples[c].append(v)

        for col in columns:
            tree.heading(col, text=col)
            width = suggest_col_width(col, col_samples.get(col))
            tree.column(col, width=width, minwidth=50, anchor="w", stretch=False)

        src = source_rows if source_rows is not None else rows
        if tree is self.browse_tree:
            self._tree_source_rows = src
        if tree is self.result_tree:
            self._result_source_rows = src

        max_len = 72 if compact else 200
        for i, row in enumerate(src):
            if compact:
                display = tuple(
                    format_cell(v, c, max_len=max_len) for c, v in zip(columns, row)
                )
            else:
                display = tuple(
                    format_cell(v, c, max_len=500) for c, v in zip(columns, row)
                )
            tag = "even" if i % 2 == 0 else "odd"
            tree.insert("", "end", iid=str(i), values=display, tags=(tag, f"idx:{i}"))

    def _export_csv(self) -> None:
        current = self.notebook.index(self.notebook.select())
        if current == 1 and self.last_result and self.last_result.columns:
            columns = self.last_result.columns
            rows = self.last_result.rows
        elif self.browse_columns:
            columns = self.browse_columns
            rows = self.browse_rows
        else:
            messagebox.showinfo("알림", "내보낼 데이터가 없습니다.", parent=self)
            return

        path = filedialog.asksaveasfilename(
            title="CSV 내보내기",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            self.db.export_csv(path, columns, rows)
            self._set_status(f"CSV 저장: {path}")
            messagebox.showinfo("완료", f"저장되었습니다.\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("내보내기 실패", str(e), parent=self)

    # ── Misc ─────────────────────────────────────────────────────

    def _set_status(self, msg: str) -> None:
        self.status_var.set(msg)

    def _show_shortcuts(self) -> None:
        messagebox.showinfo(
            "단축키",
            "F5 / Ctrl+Enter  — SQL 실행\n"
            "Ctrl+O           — DB 열기\n"
            "Ctrl+R           — 새로고침\n"
            "Delete           — 선택 행 삭제\n"
            "더블클릭 (스키마) — 테이블 열기\n"
            "더블클릭 (긴 텍스트 셀) — 전체 보기\n"
            "더블클릭 (일반 셀) — 행 수정\n"
            "우클릭           — 컨텍스트 메뉴\n"
            "WHERE 필터 예    — member_id = 1\n"
            "검색             — 현재 페이지 내 텍스트 찾기\n",
            parent=self,
        )

    def _show_about(self) -> None:
        messagebox.showinfo(
            "SQL Workbench",
            "SQLite SQL Workbench\n\n"
            "조회 · 추가 · 수정 · 삭제 · SQL 실행\n"
            "JSON 미리보기 · 긴 텍스트 요약 표시\n"
            "report-automate-tool 용 로컬 도구",
            parent=self,
        )

    def _on_close(self) -> None:
        self.db.close()
        self.destroy()


def main() -> None:
    app = SqlWorkbench()
    app.mainloop()


if __name__ == "__main__":
    main()
