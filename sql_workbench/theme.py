"""SQL Workbench 테마 · 타이포 · ttk 스타일."""

from __future__ import annotations

from dataclasses import dataclass
from tkinter import ttk
from typing import Literal

ThemeName = Literal["dark", "light"]

UI_FONT = ("Malgun Gothic", 10)
UI_FONT_BOLD = ("Malgun Gothic", 10, "bold")
UI_FONT_SMALL = ("Malgun Gothic", 9)
UI_FONT_TITLE = ("Malgun Gothic", 11, "bold")
UI_FONT_TINY = ("Malgun Gothic", 8)
MONO_FONT = ("Consolas", 10)
MONO_FONT_LG = ("Consolas", 11)
MONO_FONT_SM = ("Consolas", 9)


@dataclass(frozen=True)
class Palette:
    name: ThemeName
    bg: str
    surface: str
    surface2: str
    surface3: str
    border: str
    text: str
    text_muted: str
    text_dim: str
    accent: str
    accent_hover: str
    accent_soft: str
    success: str
    warning: str
    danger: str
    info: str
    row_odd: str
    row_even: str
    row_selected: str
    row_selected_fg: str
    null_fg: str
    editor_bg: str
    editor_fg: str
    editor_gutter: str
    editor_gutter_fg: str
    editor_cursor: str
    editor_sel: str
    kw: str
    string: str
    comment: str
    number: str
    toolbar_bg: str
    status_bg: str
    tab_active: str
    sidebar_width: int = 280


DARK = Palette(
    name="dark",
    bg="#0b1220",
    surface="#111827",
    surface2="#1a2332",
    surface3="#243044",
    border="#2d3a4f",
    text="#e8eef7",
    text_muted="#94a3b8",
    text_dim="#64748b",
    accent="#3b82f6",
    accent_hover="#2563eb",
    accent_soft="#1e3a5f",
    success="#22c55e",
    warning="#f59e0b",
    danger="#ef4444",
    info="#38bdf8",
    row_odd="#111827",
    row_even="#0f172a",
    row_selected="#2563eb",
    row_selected_fg="#ffffff",
    null_fg="#64748b",
    editor_bg="#0d1526",
    editor_fg="#e2e8f0",
    editor_gutter="#0a101c",
    editor_gutter_fg="#475569",
    editor_cursor="#e2e8f0",
    editor_sel="#1e3a5f",
    kw="#7dd3fc",
    string="#86efac",
    comment="#64748b",
    number="#fbbf24",
    toolbar_bg="#0f172a",
    status_bg="#0a101c",
    tab_active="#1e293b",
)

LIGHT = Palette(
    name="light",
    bg="#eef2f7",
    surface="#ffffff",
    surface2="#f8fafc",
    surface3="#e2e8f0",
    border="#cbd5e1",
    text="#0f172a",
    text_muted="#475569",
    text_dim="#94a3b8",
    accent="#2563eb",
    accent_hover="#1d4ed8",
    accent_soft="#dbeafe",
    success="#16a34a",
    warning="#d97706",
    danger="#dc2626",
    info="#0284c7",
    row_odd="#ffffff",
    row_even="#f1f5f9",
    row_selected="#2563eb",
    row_selected_fg="#ffffff",
    null_fg="#94a3b8",
    editor_bg="#0f172a",
    editor_fg="#f8fafc",
    editor_gutter="#0b1220",
    editor_gutter_fg="#64748b",
    editor_cursor="#f8fafc",
    editor_sel="#1e3a5f",
    kw="#7dd3fc",
    string="#86efac",
    comment="#64748b",
    number="#fbbf24",
    toolbar_bg="#f8fafc",
    status_bg="#f1f5f9",
    tab_active="#ffffff",
)


def get_palette(name: ThemeName = "dark") -> Palette:
    return DARK if name == "dark" else LIGHT


def apply_theme(root, palette: Palette) -> ttk.Style:
    """ttk 스타일 및 루트 배경 적용. Style 인스턴스 반환."""
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    p = palette
    root.configure(bg=p.bg)
    root.option_add("*Font", UI_FONT)
    root.option_add("*Menu.font", UI_FONT)
    root.option_add("*Menu.background", p.surface)
    root.option_add("*Menu.foreground", p.text)
    root.option_add("*Menu.activeBackground", p.accent)
    root.option_add("*Menu.activeForeground", "#ffffff")

    style.configure(".", font=UI_FONT, background=p.bg, foreground=p.text)
    style.configure("TFrame", background=p.bg)
    style.configure("Surface.TFrame", background=p.surface)
    style.configure("Toolbar.TFrame", background=p.toolbar_bg)
    style.configure("Status.TFrame", background=p.status_bg)
    style.configure("Sidebar.TFrame", background=p.surface)
    style.configure("Card.TFrame", background=p.surface2)

    style.configure("TLabel", background=p.bg, foreground=p.text, font=UI_FONT)
    style.configure("Surface.TLabel", background=p.surface, foreground=p.text, font=UI_FONT)
    style.configure(
        "Toolbar.TLabel",
        background=p.toolbar_bg,
        foreground=p.text_muted,
        font=UI_FONT_SMALL,
    )
    style.configure(
        "Status.TLabel",
        background=p.status_bg,
        foreground=p.text_muted,
        font=UI_FONT_SMALL,
    )
    style.configure("Title.TLabel", background=p.bg, foreground=p.text, font=UI_FONT_TITLE)
    style.configure(
        "Sidebar.Title.TLabel",
        background=p.surface,
        foreground=p.text,
        font=UI_FONT_TITLE,
    )
    style.configure(
        "Muted.TLabel",
        background=p.bg,
        foreground=p.text_muted,
        font=UI_FONT_SMALL,
    )
    style.configure(
        "Surface.Muted.TLabel",
        background=p.surface,
        foreground=p.text_muted,
        font=UI_FONT_SMALL,
    )
    style.configure(
        "Accent.TLabel",
        background=p.bg,
        foreground=p.accent,
        font=UI_FONT_BOLD,
    )
    style.configure(
        "Success.TLabel",
        background=p.status_bg,
        foreground=p.success,
        font=UI_FONT_SMALL,
    )
    style.configure(
        "Error.TLabel",
        background=p.status_bg,
        foreground=p.danger,
        font=UI_FONT_SMALL,
    )
    style.configure(
        "ConnOn.TLabel",
        background=p.toolbar_bg,
        foreground=p.success,
        font=UI_FONT_SMALL,
    )
    style.configure(
        "ConnOff.TLabel",
        background=p.toolbar_bg,
        foreground=p.text_dim,
        font=UI_FONT_SMALL,
    )

    style.configure(
        "TButton",
        padding=(10, 5),
        font=UI_FONT,
        background=p.surface3,
        foreground=p.text,
        borderwidth=0,
        focuscolor=p.accent,
    )
    style.map(
        "TButton",
        background=[("active", p.border), ("pressed", p.accent_soft)],
        foreground=[("disabled", p.text_dim)],
    )
    style.configure(
        "Accent.TButton",
        padding=(12, 5),
        font=UI_FONT_BOLD,
        background=p.accent,
        foreground="#ffffff",
        borderwidth=0,
    )
    style.map(
        "Accent.TButton",
        background=[("active", p.accent_hover), ("pressed", p.accent_hover)],
        foreground=[("disabled", "#cbd5e1")],
    )
    style.configure(
        "Ghost.TButton",
        padding=(8, 4),
        font=UI_FONT_SMALL,
        background=p.surface,
        foreground=p.text_muted,
        borderwidth=0,
    )
    style.map(
        "Ghost.TButton",
        background=[("active", p.surface3)],
        foreground=[("active", p.text)],
    )
    style.configure(
        "Danger.TButton",
        padding=(10, 5),
        font=UI_FONT,
        background=p.danger,
        foreground="#ffffff",
    )
    style.map("Danger.TButton", background=[("active", "#b91c1c")])
    style.configure(
        "Toolbar.TButton",
        padding=(9, 4),
        font=UI_FONT_SMALL,
        background=p.toolbar_bg,
        foreground=p.text,
    )
    style.map("Toolbar.TButton", background=[("active", p.surface3)])

    style.configure(
        "TEntry",
        fieldbackground=p.surface2 if p.name == "dark" else "#ffffff",
        foreground=p.text,
        insertcolor=p.text,
        bordercolor=p.border,
        lightcolor=p.border,
        darkcolor=p.border,
        padding=5,
    )
    style.map(
        "TEntry",
        fieldbackground=[("readonly", p.surface3), ("disabled", p.surface3)],
        bordercolor=[("focus", p.accent)],
        lightcolor=[("focus", p.accent)],
    )
    style.configure(
        "TCombobox",
        fieldbackground=p.surface2 if p.name == "dark" else "#ffffff",
        foreground=p.text,
        background=p.surface3,
        arrowcolor=p.text_muted,
        bordercolor=p.border,
        padding=4,
    )
    style.map(
        "TCombobox",
        fieldbackground=[
            ("readonly", p.surface2 if p.name == "dark" else "#ffffff"),
            ("disabled", p.surface3),
        ],
        bordercolor=[("focus", p.accent)],
        arrowcolor=[("active", p.text)],
    )
    root.option_add(
        "*TCombobox*Listbox.background",
        p.surface2 if p.name == "dark" else "#ffffff",
    )
    root.option_add("*TCombobox*Listbox.foreground", p.text)
    root.option_add("*TCombobox*Listbox.selectBackground", p.accent)
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
    root.option_add("*TCombobox*Listbox.font", UI_FONT)

    style.configure(
        "Treeview",
        rowheight=28,
        font=UI_FONT,
        background=p.row_odd,
        fieldbackground=p.row_odd,
        foreground=p.text,
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "Treeview.Heading",
        font=UI_FONT_BOLD,
        background=p.surface3,
        foreground=p.text,
        relief="flat",
        borderwidth=0,
        padding=6,
    )
    style.map(
        "Treeview",
        background=[("selected", p.row_selected)],
        foreground=[("selected", p.row_selected_fg)],
    )
    style.map("Treeview.Heading", background=[("active", p.border)])
    style.configure(
        "Schema.Treeview",
        rowheight=26,
        font=UI_FONT,
        background=p.surface,
        fieldbackground=p.surface,
        foreground=p.text,
        borderwidth=0,
    )
    style.map(
        "Schema.Treeview",
        background=[("selected", p.accent_soft)],
        foreground=[("selected", p.text if p.name == "dark" else p.accent)],
    )

    style.configure("TNotebook", background=p.bg, borderwidth=0, tabmargins=(6, 6, 6, 0))
    style.configure(
        "TNotebook.Tab",
        padding=(16, 8),
        font=UI_FONT,
        background=p.surface2,
        foreground=p.text_muted,
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", p.tab_active), ("active", p.surface3)],
        foreground=[("selected", p.text), ("active", p.text)],
        expand=[("selected", (0, 0, 0, 2))],
    )

    style.configure(
        "TLabelframe",
        background=p.bg,
        foreground=p.text,
        bordercolor=p.border,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=p.bg,
        foreground=p.text_muted,
        font=UI_FONT_BOLD,
    )
    style.configure(
        "Card.TLabelframe",
        background=p.surface,
        foreground=p.text,
        bordercolor=p.border,
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=p.surface,
        foreground=p.text_muted,
        font=UI_FONT_BOLD,
    )

    style.configure("TSeparator", background=p.border)
    style.configure(
        "TCheckbutton",
        background=p.bg,
        foreground=p.text,
        font=UI_FONT_SMALL,
        focuscolor=p.accent,
    )
    style.map(
        "TCheckbutton",
        background=[("active", p.bg)],
        foreground=[("disabled", p.text_dim)],
    )
    style.configure(
        "Toolbar.TCheckbutton",
        background=p.toolbar_bg,
        foreground=p.text_muted,
        font=UI_FONT_SMALL,
    )
    style.map("Toolbar.TCheckbutton", background=[("active", p.toolbar_bg)])

    style.configure(
        "TScrollbar",
        background=p.surface3,
        troughcolor=p.surface,
        bordercolor=p.surface,
        arrowcolor=p.text_muted,
        relief="flat",
    )
    style.map("TScrollbar", background=[("active", p.border)])

    style.configure("Horizontal.TPanedwindow", background=p.bg)
    style.configure("Vertical.TPanedwindow", background=p.bg)
    style.configure("Sash", sashthickness=6, gripcount=0)

    style.configure(
        "TProgressbar",
        background=p.accent,
        troughcolor=p.surface3,
        borderwidth=0,
        thickness=3,
    )

    return style
