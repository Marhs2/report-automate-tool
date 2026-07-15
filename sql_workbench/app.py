"""SQL Workbench GUI — SQLite 조회 / 추가 / 수정 / 삭제 (v2 UI)."""

from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Optional

# 패키지 실행(python -m sql_workbench)과 직접 실행(python app.py) 모두 지원
try:
    from .db_manager import DatabaseManager, QueryResult
    from .dialogs import HistoryDialog, RowDialog, ShortcutsDialog, TextViewer
    from .display_utils import (
        format_cell,
        format_detail,
        is_long_text_column,
        suggest_col_width,
    )
    from .theme import (
        ThemeName,
        UI_FONT,
        apply_theme,
        get_palette,
    )
    from .widgets import (
        ReadOnlyText,
        SqlEditor,
        StatusBar,
        bind_tree_mousewheel,
        style_data_tree,
    )
except ImportError:
    _here = Path(__file__).resolve().parent
    if str(_here.parent) not in sys.path:
        sys.path.insert(0, str(_here.parent))
    from sql_workbench.db_manager import DatabaseManager, QueryResult
    from sql_workbench.dialogs import HistoryDialog, RowDialog, ShortcutsDialog, TextViewer
    from sql_workbench.display_utils import (
        format_cell,
        format_detail,
        is_long_text_column,
        suggest_col_width,
    )
    from sql_workbench.theme import (
        ThemeName,
        UI_FONT,
        apply_theme,
        get_palette,
    )
    from sql_workbench.widgets import (
        ReadOnlyText,
        SqlEditor,
        StatusBar,
        bind_tree_mousewheel,
        style_data_tree,
    )

DEFAULT_DB = (
    Path(__file__).resolve().parent.parent / "backend" / "data" / "daily_reports.db"
)
CONFIG_PATH = Path(__file__).resolve().parent / ".workbench_config.json"

PAGE_SIZES = (50, 100, 200, 500)
DEFAULT_PAGE_SIZE = 100
APP_VERSION = "2.0.0"


class SqlWorkbench(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"SQL Workbench  ·  v{APP_VERSION}")
        self.geometry("1480x920")
        self.minsize(1100, 700)

        self._cfg = self._load_config()
        theme_name: ThemeName = self._cfg.get("theme", "dark")  # type: ignore[assignment]
        if theme_name not in ("dark", "light"):
            theme_name = "dark"
        self.theme_name: ThemeName = theme_name
        self.palette = get_palette(self.theme_name)
        self.style = apply_theme(self, self.palette)

        geom = self._cfg.get("geometry")
        if geom:
            try:
                self.geometry(geom)
            except Exception:
                pass

        self.db = DatabaseManager()
        self.current_table: Optional[str] = None
        self.page = 0
        self.page_size = int(self._cfg.get("page_size", DEFAULT_PAGE_SIZE))
        if self.page_size not in PAGE_SIZES:
            self.page_size = DEFAULT_PAGE_SIZE
        self.total_rows = 0
        self.last_result: Optional[QueryResult] = None
        self.browse_columns: list[str] = []
        self.browse_rows: list[tuple] = []
        self.query_result_rows: list[tuple] = []
        self.query_result_columns: list[str] = []
        self.query_history: list[str] = list(self._cfg.get("query_history", []))[-50:]
        self.recent_dbs: list[str] = list(self._cfg.get("recent_dbs", []))[:8]
        self._sort_col: Optional[str] = None
        self._sort_desc = False
        self._table_col_meta: dict[str, dict[str, Any]] = {}
        self._tree_source_rows: list[tuple] = []
        self._result_source_rows: list[tuple] = []
        self._schema_count_job: Optional[str] = None
        self._search_job: Optional[str] = None
        self._schema_filter = ""
        self._fill_gen: dict[int, int] = {}  # id(tree) -> generation
        self.compact_long = tk.BooleanVar(value=bool(self._cfg.get("compact_long", True)))

        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_status()
        self._build_context_menus()
        self._apply_tree_tags()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<F5>", lambda e: self._run_sql())
        self.bind("<Control-Return>", lambda e: self._run_sql())
        self.bind("<Control-Shift-Return>", lambda e: self._run_selected_sql())
        self.bind("<Control-o>", lambda e: self._open_db())
        self.bind("<Control-O>", lambda e: self._open_db())
        self.bind("<Control-r>", lambda e: self._refresh_all())
        self.bind("<Control-R>", lambda e: self._refresh_all())
        self.bind("<Control-f>", lambda e: self._focus_search())
        self.bind("<Control-F>", lambda e: self._focus_search())
        self.bind("<Control-comma>", lambda e: self._toggle_theme())
        self.bind("<Alt-Left>", lambda e: self._prev_page())
        self.bind("<Alt-Right>", lambda e: self._next_page())
        # Delete: only when browse grid has focus
        self.browse_tree.bind("<Delete>", lambda e: self._delete_row())

        last = self._cfg.get("last_db")
        if last and Path(last).exists():
            self.after(80, lambda: self._connect_path(Path(last)))
        elif DEFAULT_DB.exists():
            self.after(80, lambda: self._connect_path(DEFAULT_DB))

    # ── config ───────────────────────────────────────────────────

    def _load_config(self) -> dict[str, Any]:
        try:
            if CONFIG_PATH.exists():
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_config(self) -> None:
        data = {
            "theme": self.theme_name,
            "geometry": self.geometry(),
            "page_size": self.page_size,
            "compact_long": self.compact_long.get(),
            "last_db": str(self.db.db_path) if self.db.db_path else self._cfg.get("last_db"),
            "recent_dbs": self.recent_dbs[:8],
            "query_history": self.query_history[-40:],
        }
        try:
            CONFIG_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # ── UI construction ──────────────────────────────────────────

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="파일", menu=file_menu)
        file_menu.add_command(label="DB 열기…\tCtrl+O", command=self._open_db)
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="최근 파일", menu=self.recent_menu)
        self._rebuild_recent_menu()
        file_menu.add_command(label="새로고침\tCtrl+R", command=self._refresh_all)
        file_menu.add_separator()
        file_menu.add_command(label="결과 CSV 내보내기…", command=self._export_csv)
        file_menu.add_separator()
        file_menu.add_command(label="종료", command=self._on_close)

        query_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="쿼리", menu=query_menu)
        query_menu.add_command(label="실행\tF5", command=self._run_sql)
        query_menu.add_command(label="선택 영역 실행\tCtrl+Shift+Enter", command=self._run_selected_sql)
        query_menu.add_command(label="편집기 비우기", command=self._clear_editor)
        query_menu.add_command(label="히스토리…", command=self._show_history)

        data_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="데이터", menu=data_menu)
        data_menu.add_command(label="행 추가", command=self._insert_row)
        data_menu.add_command(label="행 수정", command=self._edit_row)
        data_menu.add_command(label="행 삭제\tDel", command=self._delete_row)
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
        view_menu.add_command(label="테마 전환\tCtrl+,", command=self._toggle_theme)
        view_menu.add_command(label="데이터 탭", command=lambda: self.notebook.select(0))
        view_menu.add_command(label="SQL 쿼리 탭", command=lambda: self.notebook.select(1))
        view_menu.add_command(label="구조 탭", command=lambda: self.notebook.select(2))

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="도움말", menu=help_menu)
        help_menu.add_command(label="단축키", command=self._show_shortcuts)
        help_menu.add_command(label="정보", command=self._show_about)

    def _rebuild_recent_menu(self) -> None:
        self.recent_menu.delete(0, "end")
        if not self.recent_dbs:
            self.recent_menu.add_command(label="(없음)", state="disabled")
            return
        for path in self.recent_dbs:
            p = Path(path)
            self.recent_menu.add_command(
                label=p.name,
                command=lambda pp=p: self._connect_path(pp) if pp.exists() else messagebox.showwarning(
                    "알림", f"파일이 없습니다:\n{pp}", parent=self
                ),
            )

    def _build_toolbar(self) -> None:
        outer = ttk.Frame(self, style="Toolbar.TFrame", padding=(12, 8))
        outer.pack(fill="x")

        left = ttk.Frame(outer, style="Toolbar.TFrame")
        left.pack(side="left")

        ttk.Button(left, text="📂  DB 열기", style="Toolbar.TButton", command=self._open_db).pack(
            side="left", padx=2
        )
        ttk.Button(
            left, text="↻  새로고침", style="Toolbar.TButton", command=self._refresh_all
        ).pack(side="left", padx=2)

        ttk.Separator(left, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(
            left, text="▶  실행 (F5)", style="Accent.TButton", command=self._run_sql
        ).pack(side="left", padx=2)
        ttk.Button(
            left, text="선택 실행", style="Toolbar.TButton", command=self._run_selected_sql
        ).pack(side="left", padx=2)

        ttk.Separator(left, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(left, text="+ 추가", style="Toolbar.TButton", command=self._insert_row).pack(
            side="left", padx=2
        )
        ttk.Button(left, text="수정", style="Toolbar.TButton", command=self._edit_row).pack(
            side="left", padx=2
        )
        ttk.Button(left, text="삭제", style="Toolbar.TButton", command=self._delete_row).pack(
            side="left", padx=2
        )
        ttk.Button(
            left, text="상세", style="Toolbar.TButton", command=self._view_row_detail
        ).pack(side="left", padx=2)

        ttk.Separator(left, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(
            left, text="CSV", style="Toolbar.TButton", command=self._export_csv
        ).pack(side="left", padx=2)
        ttk.Button(
            left, text="테마", style="Toolbar.TButton", command=self._toggle_theme
        ).pack(side="left", padx=2)

        right = ttk.Frame(outer, style="Toolbar.TFrame")
        right.pack(side="right")
        self.db_badge = ttk.Label(right, text="●  연결 안 됨", style="ConnOff.TLabel")
        self.db_badge.pack(side="right", padx=4)
        self.table_badge = ttk.Label(right, text="", style="Toolbar.TLabel")
        self.table_badge.pack(side="right", padx=12)

        # thin accent line under toolbar
        line = tk.Frame(self, height=2, bg=self.palette.accent, bd=0, highlightthickness=0)
        line.pack(fill="x")
        self._toolbar_line = line

    def _build_body(self) -> None:
        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=(8, 4))
        self.main_paned = paned

        # ── Sidebar ──
        left = ttk.Frame(paned, style="Sidebar.TFrame", width=self.palette.sidebar_width)
        paned.add(left, weight=1)

        head = ttk.Frame(left, style="Sidebar.TFrame", padding=(10, 10, 10, 4))
        head.pack(fill="x")
        ttk.Label(head, text="스키마", style="Sidebar.Title.TLabel").pack(side="left")
        ttk.Label(head, text="더블클릭 열기", style="Surface.Muted.TLabel").pack(side="right")

        search_row = ttk.Frame(left, style="Sidebar.TFrame", padding=(10, 4, 10, 6))
        search_row.pack(fill="x")
        self.schema_search_var = tk.StringVar()
        schema_entry = ttk.Entry(search_row, textvariable=self.schema_search_var)
        schema_entry.pack(fill="x")
        schema_entry.insert(0, "")
        self._schema_placeholder = True
        schema_entry.bind("<KeyRelease>", self._on_schema_search)
        schema_entry.bind("<FocusIn>", self._schema_search_focus_in)
        # placeholder via label overlay is complex; use trace
        self.schema_search_var.trace_add("write", lambda *_: self._on_schema_search())

        tree_frame = ttk.Frame(left, style="Sidebar.TFrame", padding=(6, 0, 6, 8))
        tree_frame.pack(fill="both", expand=True)
        self.schema_tree = ttk.Treeview(
            tree_frame, show="tree", selectmode="browse", style="Schema.Treeview"
        )
        sy = ttk.Scrollbar(tree_frame, orient="vertical", command=self.schema_tree.yview)
        self.schema_tree.configure(yscrollcommand=sy.set)
        self.schema_tree.pack(side="left", fill="both", expand=True)
        sy.pack(side="right", fill="y")
        self.schema_tree.bind("<<TreeviewSelect>>", self._on_schema_select)
        self.schema_tree.bind("<Double-1>", self._on_schema_double)
        bind_tree_mousewheel(self.schema_tree)

        # ── Main tabs ──
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

        # Filter bar
        top = ttk.Frame(tab, padding=(8, 8, 8, 4))
        top.pack(fill="x")

        ttk.Label(top, text="테이블", style="Muted.TLabel").pack(side="left")
        self.table_var = tk.StringVar()
        self.table_combo = ttk.Combobox(
            top, textvariable=self.table_var, state="readonly", width=22, font=UI_FONT
        )
        self.table_combo.pack(side="left", padx=(6, 10))
        self.table_combo.bind("<<ComboboxSelected>>", lambda e: self._on_table_combo())

        ttk.Label(top, text="WHERE", style="Muted.TLabel").pack(side="left")
        self.filter_var = tk.StringVar()
        filter_entry = ttk.Entry(top, textvariable=self.filter_var, width=32, font=UI_FONT)
        filter_entry.pack(side="left", padx=(6, 4))
        filter_entry.bind("<Return>", lambda e: self._reload_table(reset_page=True))

        ttk.Button(
            top, text="적용", command=lambda: self._reload_table(reset_page=True)
        ).pack(side="left", padx=2)
        ttk.Button(top, text="초기화", style="Ghost.TButton", command=self._clear_filter).pack(
            side="left", padx=2
        )

        ttk.Label(top, text="검색", style="Muted.TLabel").pack(side="left", padx=(14, 0))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            top, textvariable=self.search_var, width=16, font=UI_FONT
        )
        self.search_entry.pack(side="left", padx=(6, 2))
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        self.search_entry.bind("<Return>", lambda e: self._apply_client_search())

        ttk.Checkbutton(
            top,
            text="긴 텍스트 요약",
            variable=self.compact_long,
            command=self._reload_table,
        ).pack(side="right", padx=4)

        # Grid + detail
        vpaned = ttk.Panedwindow(tab, orient="vertical")
        vpaned.pack(fill="both", expand=True, padx=8, pady=4)
        self.browse_vpaned = vpaned

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
        bind_tree_mousewheel(self.browse_tree)

        detail_wrap = ttk.LabelFrame(
            vpaned, text="선택 행 미리보기", padding=6, style="Card.TLabelframe"
        )
        vpaned.add(detail_wrap, weight=2)

        dbar = ttk.Frame(detail_wrap)
        dbar.pack(fill="x", pady=(0, 6))
        ttk.Label(dbar, text="컬럼", style="Muted.TLabel").pack(side="left")
        self.detail_col_var = tk.StringVar()
        self.detail_col_combo = ttk.Combobox(
            dbar,
            textvariable=self.detail_col_var,
            state="readonly",
            width=28,
            font=UI_FONT,
        )
        self.detail_col_combo.pack(side="left", padx=6)
        self.detail_col_combo.bind("<<ComboboxSelected>>", self._show_selected_cell_detail)
        ttk.Button(
            dbar, text="전체 창", style="Ghost.TButton", command=self._open_detail_window
        ).pack(side="left", padx=2)
        ttk.Button(
            dbar, text="복사", style="Ghost.TButton", command=self._copy_detail
        ).pack(side="left", padx=2)
        ttk.Button(dbar, text="행 수정", command=self._edit_row).pack(side="right")

        self.detail_panel = ReadOnlyText(detail_wrap, self.palette, height=10, dark_editor=True)
        self.detail_panel.pack(fill="both", expand=True)
        self.detail_panel.set_content("행을 선택하면 여기에 전체 내용이 표시됩니다.")

        # Pagination bar
        page_bar = ttk.Frame(tab, padding=(8, 4, 8, 8))
        page_bar.pack(fill="x")

        ttk.Button(page_bar, text="⏮", width=3, command=self._first_page).pack(side="left")
        ttk.Button(page_bar, text="◀", width=3, command=self._prev_page).pack(
            side="left", padx=2
        )
        ttk.Button(page_bar, text="▶", width=3, command=self._next_page).pack(
            side="left", padx=2
        )
        ttk.Button(page_bar, text="⏭", width=3, command=self._last_page).pack(
            side="left", padx=2
        )

        self.page_label = ttk.Label(page_bar, text="페이지 —", style="Muted.TLabel")
        self.page_label.pack(side="left", padx=12)

        ttk.Label(page_bar, text="크기", style="Muted.TLabel").pack(side="left", padx=(8, 4))
        self.page_size_var = tk.StringVar(value=str(self.page_size))
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
        vpaned.pack(fill="both", expand=True, padx=8, pady=8)
        self.query_vpaned = vpaned

        editor_frame = ttk.LabelFrame(
            vpaned, text="SQL 편집기", padding=4, style="Card.TLabelframe"
        )
        vpaned.add(editor_frame, weight=2)

        self.sql_editor = SqlEditor(editor_frame, self.palette)
        self.sql_editor.pack(fill="both", expand=True)
        # expose .sql_text for any legacy refs
        self.sql_text = self.sql_editor.text

        qbar = ttk.Frame(tab, padding=(8, 0, 8, 4))
        qbar.pack(fill="x")
        ttk.Button(
            qbar, text="▶  실행 (F5)", style="Accent.TButton", command=self._run_sql
        ).pack(side="left")
        ttk.Button(qbar, text="선택 실행", command=self._run_selected_sql).pack(
            side="left", padx=4
        )
        ttk.Button(qbar, text="비우기", style="Ghost.TButton", command=self._clear_editor).pack(
            side="left"
        )
        ttk.Button(qbar, text="히스토리", command=self._show_history).pack(
            side="left", padx=4
        )
        ttk.Button(qbar, text="샘플 쿼리", command=self._insert_sample).pack(
            side="left", padx=4
        )
        self.query_meta_var = tk.StringVar(value="")
        ttk.Label(qbar, textvariable=self.query_meta_var, style="Muted.TLabel").pack(
            side="right"
        )

        result_frame = ttk.LabelFrame(
            vpaned, text="결과", padding=4, style="Card.TLabelframe"
        )
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
        self.result_tree.bind("<Double-1>", self._on_result_double)
        bind_tree_mousewheel(self.result_tree)

    def _build_structure_tab(self) -> None:
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="  테이블 구조  ")

        info_top = ttk.Frame(tab, padding=(10, 10, 10, 4))
        info_top.pack(fill="x")
        self.structure_title = ttk.Label(
            info_top, text="테이블을 선택하세요", style="Title.TLabel"
        )
        self.structure_title.pack(side="left")
        self.structure_meta = ttk.Label(info_top, text="", style="Muted.TLabel")
        self.structure_meta.pack(side="right")

        cols_frame = ttk.LabelFrame(
            tab, text="컬럼", padding=6, style="Card.TLabelframe"
        )
        cols_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self.struct_tree = ttk.Treeview(
            cols_frame,
            columns=("name", "type", "pk", "notnull", "default"),
            show="headings",
        )
        for col, text, w in [
            ("name", "이름", 200),
            ("type", "타입", 110),
            ("pk", "PK", 50),
            ("notnull", "NOT NULL", 90),
            ("default", "DEFAULT", 200),
        ]:
            self.struct_tree.heading(col, text=text)
            self.struct_tree.column(col, width=w, anchor="w")
        ssy = ttk.Scrollbar(
            cols_frame, orient="vertical", command=self.struct_tree.yview
        )
        self.struct_tree.configure(yscrollcommand=ssy.set)
        self.struct_tree.pack(side="left", fill="both", expand=True)
        ssy.pack(side="right", fill="y")
        bind_tree_mousewheel(self.struct_tree)

        ddl_frame = ttk.LabelFrame(
            tab, text="CREATE SQL · 인덱스 · 외래키", padding=6, style="Card.TLabelframe"
        )
        ddl_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.ddl_panel = ReadOnlyText(
            ddl_frame, self.palette, height=10, mono=True, dark_editor=False
        )
        self.ddl_panel.pack(fill="both", expand=True)

    def _build_status(self) -> None:
        ttk.Separator(self, orient="horizontal").pack(fill="x", side="bottom")
        self.status = StatusBar(self)
        self.status.pack(fill="x", side="bottom")

    def _build_context_menus(self) -> None:
        self.browse_menu = tk.Menu(self, tearoff=0)
        self.browse_menu.add_command(label="상세 보기", command=self._view_row_detail)
        self.browse_menu.add_command(label="수정", command=self._edit_row)
        self.browse_menu.add_command(label="삭제", command=self._delete_row)
        self.browse_menu.add_separator()
        self.browse_menu.add_command(label="셀 값 복사", command=self._copy_selected_cell)
        self.browse_menu.add_command(label="행 복사 (TSV)", command=self._copy_selected_row)
        self.browse_menu.add_command(
            label="SELECT 문 생성", command=self._copy_select_for_row
        )
        self.browse_tree.bind("<Button-3>", self._popup_browse_menu)

        self.schema_menu = tk.Menu(self, tearoff=0)
        self.schema_menu.add_command(label="데이터 열기", command=self._schema_open_table)
        self.schema_menu.add_command(label="SELECT 넣기", command=self._schema_insert_select)
        self.schema_menu.add_command(label="구조 보기", command=self._schema_show_structure)
        self.schema_tree.bind("<Button-3>", self._popup_schema_menu)

    def _apply_tree_tags(self) -> None:
        style_data_tree(self.browse_tree, self.palette)
        style_data_tree(self.result_tree, self.palette)
        style_data_tree(self.struct_tree, self.palette)

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

    def _popup_schema_menu(self, event: tk.Event) -> None:
        row_id = self.schema_tree.identify_row(event.y)
        if row_id:
            self.schema_tree.selection_set(row_id)
            self.schema_tree.focus(row_id)
        try:
            self.schema_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.schema_menu.grab_release()

    # ── Theme ────────────────────────────────────────────────────

    def _toggle_theme(self) -> None:
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.palette = get_palette(self.theme_name)
        self.style = apply_theme(self, self.palette)
        self._toolbar_line.configure(bg=self.palette.accent)
        self.sql_editor.apply_palette(self.palette)
        self.detail_panel.apply_palette(self.palette, dark_editor=True)
        self.ddl_panel.apply_palette(self.palette, dark_editor=False)
        self._apply_tree_tags()
        # refresh connection badge style
        if self.db.is_connected:
            self.db_badge.configure(style="ConnOn.TLabel")
        else:
            self.db_badge.configure(style="ConnOff.TLabel")
        self._set_status(f"테마: {self.theme_name}")
        self._save_config()

    # ── Connection / schema ──────────────────────────────────────

    def _open_db(self) -> None:
        initial = DEFAULT_DB.parent if DEFAULT_DB.parent.exists() else Path.cwd()
        if self.db.db_path:
            initial = self.db.db_path.parent
        path = filedialog.askopenfilename(
            title="SQLite DB 열기",
            filetypes=[
                ("SQLite DB", "*.db *.sqlite *.sqlite3"),
                ("모든 파일", "*.*"),
            ],
            initialdir=str(initial),
        )
        if path:
            self._connect_path(Path(path))

    def _connect_path(self, path: Path) -> None:
        try:
            self.db.connect(path)
        except Exception as e:
            messagebox.showerror("연결 실패", str(e), parent=self)
            return

        sp = str(path.resolve())
        self.recent_dbs = [sp] + [p for p in self.recent_dbs if p != sp]
        self.recent_dbs = self.recent_dbs[:8]
        self._rebuild_recent_menu()

        self.db_badge.config(text=f"●  {path.name}", style="ConnOn.TLabel")
        self.title(f"SQL Workbench  ·  {path.name}")
        self._set_status(f"연결됨: {path}")
        self._refresh_schema()
        tables = self.db.list_tables()
        if tables:
            preferred = "daily_reports" if "daily_reports" in tables else tables[0]
            self.table_var.set(preferred)
            self.current_table = preferred
            self.table_badge.config(text=f"테이블  {preferred}")
            self._reload_table(reset_page=True)
            self._load_structure(preferred)
        self._save_config()

    def _refresh_all(self) -> None:
        if not self.db.is_connected:
            return
        self.db.invalidate_cache()
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
        filt = self.schema_search_var.get().strip().lower()

        def _match(name: str) -> bool:
            return not filt or filt in name.lower()

        root_t = self.schema_tree.insert(
            "", "end", iid="__tables__", text=f"  테이블  ({len(tables)})", open=True
        )
        table_iids: list[tuple[str, str]] = []
        for t in tables:
            if not _match(t):
                continue
            tid = f"t:{t}"
            self.schema_tree.insert(
                root_t, "end", iid=tid, text=f"  ▸  {t}", values=(t,), tags=("table",)
            )
            table_iids.append((tid, t))

        if views:
            root_v = self.schema_tree.insert(
                "", "end", iid="__views__", text=f"  뷰  ({len(views)})", open=True
            )
            for v in views:
                if not _match(v):
                    continue
                self.schema_tree.insert(
                    root_v,
                    "end",
                    iid=f"v:{v}",
                    text=f"  ▸  {v}",
                    values=(v,),
                    tags=("view",),
                )

        # 컬럼은 선택 시에만 로드 (성능). 카운트는 백그라운드 틱으로.
        if self._schema_count_job:
            try:
                self.after_cancel(self._schema_count_job)
            except Exception:
                pass
        self._schema_count_queue = list(table_iids)
        self._schema_count_job = self.after(30, self._fill_schema_counts_step)

    def _fill_schema_counts_step(self) -> None:
        """테이블 행 수를 조금씩 채워 UI 블로킹 방지."""
        if not self.db.is_connected:
            return
        queue = getattr(self, "_schema_count_queue", [])
        batch = queue[:6]
        self._schema_count_queue = queue[6:]
        for tid, t in batch:
            if not self.schema_tree.exists(tid):
                continue
            try:
                cnt = self.db.count_rows(t)
                self.schema_tree.item(tid, text=f"  ▸  {t}   ({cnt:,})")
            except Exception:
                pass
            # expand columns lazily only for current table
            if t == self.current_table:
                self._ensure_schema_columns(tid, t)
        if self._schema_count_queue:
            self._schema_count_job = self.after(20, self._fill_schema_counts_step)
        else:
            self._schema_count_job = None

    def _ensure_schema_columns(self, tid: str, table: str) -> None:
        if self.schema_tree.get_children(tid):
            return
        try:
            for col in self.db.get_table_info(table):
                pk = "  🔑" if col["pk"] else ""
                self.schema_tree.insert(
                    tid,
                    "end",
                    text=f"      {col['name']}  :  {col['type']}{pk}",
                    tags=("column",),
                )
            self.schema_tree.item(tid, open=True)
        except Exception:
            pass

    def _on_schema_search(self, _event: Any = None) -> None:
        if not self.db.is_connected:
            return
        # debounce
        if self._search_job:
            try:
                self.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.after(180, self._refresh_schema)

    def _schema_search_focus_in(self, _event: Any = None) -> None:
        pass

    def _schema_table_name(self) -> Optional[str]:
        item = self.schema_tree.focus()
        if not item:
            return None
        tags = self.schema_tree.item(item, "tags")
        if "table" in tags or "view" in tags:
            vals = self.schema_tree.item(item, "values")
            if vals:
                return str(vals[0])
            text = self.schema_tree.item(item, "text").strip()
            # "▸  name   (n)"
            text = text.lstrip("▸ ").split()[0]
            return text
        # column: parent
        parent = self.schema_tree.parent(item)
        if parent:
            vals = self.schema_tree.item(parent, "values")
            if vals:
                return str(vals[0])
        return None

    def _on_schema_select(self, _event: Any = None) -> None:
        name = self._schema_table_name()
        if not name:
            return
        item = self.schema_tree.focus()
        tags = self.schema_tree.item(item, "tags") if item else ()
        if "table" in tags or "view" in tags:
            self.current_table = name
            self.table_var.set(name)
            self.table_badge.config(text=f"테이블  {name}")
            self._load_structure(name)
            tid = item
            if tid:
                self._ensure_schema_columns(tid, name)

    def _on_schema_double(self, _event: Any = None) -> None:
        self._schema_open_table()

    def _schema_open_table(self) -> None:
        name = self._schema_table_name()
        if not name:
            return
        self.current_table = name
        self.table_var.set(name)
        self.table_badge.config(text=f"테이블  {name}")
        self._reload_table(reset_page=True)
        self._load_structure(name)
        self.notebook.select(0)
        self.sql_editor.set_text(
            f'SELECT * FROM "{name}" ORDER BY rowid DESC LIMIT 100;\n'
        )

    def _schema_insert_select(self) -> None:
        name = self._schema_table_name()
        if not name:
            return
        self.sql_editor.set_text(
            f'SELECT * FROM "{name}" ORDER BY rowid DESC LIMIT 100;\n'
        )
        self.notebook.select(1)
        self.sql_editor.focus_set()

    def _schema_show_structure(self) -> None:
        name = self._schema_table_name()
        if not name:
            return
        self.current_table = name
        self.table_var.set(name)
        self._load_structure(name)
        self.notebook.select(2)

    def _on_table_combo(self) -> None:
        name = self.table_var.get()
        if name:
            self.current_table = name
            self.table_badge.config(text=f"테이블  {name}")
            self._reload_table(reset_page=True)
            self._load_structure(name)

    def _on_page_size(self, _event: Any = None) -> None:
        try:
            self.page_size = int(self.page_size_var.get())
        except ValueError:
            self.page_size = DEFAULT_PAGE_SIZE
        self._reload_table(reset_page=True)
        self._save_config()

    # ── Browse data ──────────────────────────────────────────────

    def _clear_filter(self) -> None:
        self.filter_var.set("")
        self.search_var.set("")
        self._reload_table(reset_page=True)

    def _focus_search(self) -> None:
        self.notebook.select(0)
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, "end")

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
            self._set_status(f"오류: {e}", error=True)
            return

        self.browse_columns = result.columns
        self.browse_rows = result.rows
        self.detail_col_combo["values"] = result.columns
        if result.columns and (
            not self.detail_col_var.get()
            or self.detail_col_var.get() not in result.columns
        ):
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
                arrow = "  ▼" if self._sort_desc else "  ▲"
            self.browse_tree.heading(
                col,
                text=f"{col}{arrow}",
                command=lambda c=col: self._sort_by(c),
            )

        start = self.page * self.page_size + 1 if result.rows else 0
        end = self.page * self.page_size + len(result.rows)
        total_pages = max(1, (self.total_rows + self.page_size - 1) // self.page_size)
        self.page_label.config(
            text=(
                f"{start:,}–{end:,}  /  전체 {self.total_rows:,}행"
                f"   ·   페이지 {self.page + 1}/{total_pages}"
            )
        )
        self._set_status(result.message, meta=f"{result.elapsed_ms:.1f} ms")
        self.detail_panel.set_content("행을 선택하면 여기에 전체 내용이 표시됩니다.")

        if self.search_var.get().strip():
            self._apply_client_search()

    def _sort_by(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = False
        self._reload_table()

    def _first_page(self) -> None:
        if self.page != 0:
            self.page = 0
            self._reload_table()

    def _prev_page(self) -> None:
        if self.page > 0:
            self.page -= 1
            self._reload_table()

    def _next_page(self) -> None:
        if (self.page + 1) * self.page_size < self.total_rows:
            self.page += 1
            self._reload_table()

    def _last_page(self) -> None:
        if self.total_rows <= 0:
            return
        last = max(0, (self.total_rows - 1) // self.page_size)
        if last != self.page:
            self.page = last
            self._reload_table()

    def _on_search_key(self, _event: Any = None) -> None:
        if self._search_job:
            try:
                self.after_cancel(self._search_job)
            except Exception:
                pass
        self._search_job = self.after(220, self._apply_client_search)

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
        filtered = [
            row
            for row in self.browse_rows
            if any(q in str(v).lower() for v in row if v is not None)
        ]
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
        if not self.browse_tree.selection() or not self.browse_columns:
            return None
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
        rows = self._tree_source_rows or self.browse_rows
        if raw_idx < 0 or raw_idx >= len(rows):
            return None
        return dict(zip(self.browse_columns, rows[raw_idx]))

    def _on_browse_select(self, _event: Any = None) -> None:
        row = self._selected_raw_row()
        if not row:
            return
        col = self.detail_col_var.get()
        if col and col in row:
            self.detail_panel.set_content(format_detail(row[col], col))
        else:
            lines = [f"{k}: {format_cell(v, k, max_len=120)}" for k, v in row.items()]
            self.detail_panel.set_content("\n".join(lines))

    def _show_selected_cell_detail(self, _event: Any = None) -> None:
        self._on_browse_select()

    def _on_browse_double(self, event: tk.Event) -> None:
        region = self.browse_tree.identify("region", event.x, event.y)
        if region == "cell":
            col_id = self.browse_tree.identify_column(event.x)
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
                    meta = self._table_col_meta.get(col, {})
                    if is_long_text_column(col, meta.get("type", "")):
                        TextViewer(
                            self,
                            f"{self.current_table}.{col}",
                            format_detail(val, col),
                            palette=self.palette,
                        )
                        return
        self._edit_row()

    def _view_row_detail(self) -> None:
        row = self._selected_raw_row()
        if not row:
            messagebox.showinfo("알림", "행을 선택하세요.", parent=self)
            return
        parts = [f"══ {k} ══\n{format_detail(v, k)}\n" for k, v in row.items()]
        TextViewer(
            self,
            f"행 상세 — {self.current_table}",
            "\n".join(parts),
            palette=self.palette,
        )

    def _open_detail_window(self) -> None:
        content = self.detail_panel.get()
        col = self.detail_col_var.get() or "detail"
        TextViewer(
            self, f"{self.current_table}.{col}", content, palette=self.palette
        )

    def _copy_detail(self) -> None:
        content = self.detail_panel.get()
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

    def _copy_select_for_row(self) -> None:
        row = self._selected_raw_row()
        table = self.current_table
        if not row or not table:
            return
        pks = self.db.get_primary_keys(table) if self.db.is_connected else []
        if pks and all(pk in row for pk in pks):
            conds = []
            for pk in pks:
                v = row[pk]
                if v is None:
                    conds.append(f'"{pk}" IS NULL')
                elif isinstance(v, (int, float)):
                    conds.append(f'"{pk}" = {v}')
                else:
                    esc = str(v).replace("'", "''")
                    conds.append(f"\"{pk}\" = '{esc}'")
            sql = f'SELECT * FROM "{table}" WHERE {" AND ".join(conds)};'
        else:
            sql = f'SELECT * FROM "{table}" LIMIT 1;'
        self.clipboard_clear()
        self.clipboard_append(sql)
        self._set_status("SELECT 문 복사됨")

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
        if raw_idx is None or raw_idx >= len(self.query_result_rows):
            return
        row = dict(zip(self.query_result_columns, self.query_result_rows[raw_idx]))
        parts = [f"══ {k} ══\n{format_detail(v, k)}\n" for k, v in row.items()]
        TextViewer(self, "쿼리 결과 상세", "\n".join(parts), palette=self.palette)

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

        dlg = RowDialog(self, f"행 추가 — {table}", cols, palette=self.palette)
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
            self,
            f"행 수정 — {table}",
            cols,
            values=row,
            readonly_pk=True,
            palette=self.palette,
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
        rows = self._tree_source_rows or self.browse_rows
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
        sql = self.sql_editor.get().strip()
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
            self._set_status(f"오류: {e}", error=True)
            self.query_meta_var.set("실패")
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
            self.query_meta_var.set(
                f"{result.rowcount:,}행  ·  {result.elapsed_ms:.1f} ms"
            )
        else:
            self.query_result_columns = ["message"]
            self.query_result_rows = [(result.message,)]
            self._fill_tree(
                self.result_tree, ["message"], [(result.message,)], compact=False
            )
            self._refresh_schema()
            if self.current_table:
                self._reload_table()
            self.query_meta_var.set(
                f"영향 {result.affected}행  ·  {result.elapsed_ms:.1f} ms"
            )

        self._set_status(result.message, meta=f"{result.elapsed_ms:.1f} ms")
        self._save_config()

    def _clear_editor(self) -> None:
        self.sql_editor.clear()

    def _show_history(self) -> None:
        if not self.query_history:
            messagebox.showinfo("히스토리", "실행 기록이 없습니다.", parent=self)
            return
        dlg = HistoryDialog(self, self.query_history, palette=self.palette)
        self.wait_window(dlg)
        if dlg.result:
            self.sql_editor.set_text(dlg.result)
            self.notebook.select(1)
            self.sql_editor.focus_set()

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

-- 일일 보고서 + 멤버 이름
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
        self.sql_editor.set_text(samples)
        self.notebook.select(1)

    # ── Structure ────────────────────────────────────────────────

    def _load_structure(self, table: str) -> None:
        if not self.db.is_connected:
            return
        self.structure_title.config(text=f"테이블  ·  {table}")
        self.struct_tree.delete(*self.struct_tree.get_children())
        try:
            cols = self.db.get_table_info(table)
            for i, c in enumerate(cols):
                tag = "even" if i % 2 == 0 else "odd"
                self.struct_tree.insert(
                    "",
                    "end",
                    values=(
                        c["name"],
                        c["type"],
                        "●" if c["pk"] else "",
                        "●" if c["notnull"] else "",
                        c["default"] if c["default"] is not None else "",
                    ),
                    tags=(tag,),
                )
            ddl = self.db.get_create_sql(table) or "(DDL 없음)"
            parts = [ddl]

            fks = self.db.get_foreign_keys(table)
            if fks:
                lines = [
                    f"  {f['from']} → {f['table']}.{f['to']} "
                    f"(ON UPDATE {f['on_update']}, ON DELETE {f['on_delete']})"
                    for f in fks
                ]
                parts.append("\nForeign Keys:\n" + "\n".join(lines))

            try:
                indexes = self.db.get_indexes(table)
                if indexes:
                    lines = [
                        f"  {ix['name']}"
                        f"{' UNIQUE' if ix['unique'] else ''}"
                        f" ({', '.join(ix['columns'])})"
                        for ix in indexes
                    ]
                    parts.append("\nIndexes:\n" + "\n".join(lines))
            except Exception:
                pass

            try:
                cnt = self.db.count_rows(table)
                parts.append(f"\nRow count: {cnt:,}")
                self.structure_meta.config(text=f"{len(cols)} 컬럼  ·  {cnt:,} 행")
            except Exception:
                self.structure_meta.config(text=f"{len(cols)} 컬럼")

            self.ddl_panel.set_content("\n".join(parts))
        except Exception as e:
            self._set_status(f"구조 로드 실패: {e}", error=True)

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
        batch_size = 100
        total = len(src)
        tid = id(tree)
        gen = self._fill_gen.get(tid, 0) + 1
        self._fill_gen[tid] = gen

        def _insert_range(start: int) -> None:
            if self._fill_gen.get(tid) != gen:
                return  # superseded by newer fill
            end = min(start + batch_size, total)
            for i in range(start, end):
                row = src[i]
                if compact:
                    display = tuple(
                        format_cell(v, c, max_len=max_len) for c, v in zip(columns, row)
                    )
                else:
                    display = tuple(
                        format_cell(v, c, max_len=500) for c, v in zip(columns, row)
                    )
                tag = "even" if i % 2 == 0 else "odd"
                tree.insert(
                    "", "end", iid=str(i), values=display, tags=(tag, f"idx:{i}")
                )
            if end < total:
                tree.after(1, lambda: _insert_range(end))

        if total:
            _insert_range(0)

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

    def _set_status(self, msg: str, *, error: bool = False, meta: str = "") -> None:
        self.status.set_message(msg, error=error)
        if meta:
            self.status.set_meta(meta)
        elif not error:
            # keep previous meta unless cleared intentionally
            pass

    def _show_shortcuts(self) -> None:
        ShortcutsDialog(self, palette=self.palette)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "SQL Workbench",
            f"SQLite SQL Workbench  v{APP_VERSION}\n\n"
            "조회 · 추가 · 수정 · 삭제 · SQL 실행\n"
            "다크/라이트 테마 · JSON 미리보기\n"
            "라인 번호 에디터 · 쿼리 실행 시간\n"
            "report-automate-tool 용 로컬 도구",
            parent=self,
        )

    def _on_close(self) -> None:
        self._save_config()
        self.db.close()
        self.destroy()


def main() -> None:
    app = SqlWorkbench()
    app.mainloop()


if __name__ == "__main__":
    main()
