from __future__ import annotations

import csv
import json
import queue
import sys
import threading
import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from lxml import etree

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

from . import APP_NAME, APP_VERSION
from .config import ConfigStore
from .diff_engine import DiffEngine, DiffItem, DiffResult


def get_asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        base_path = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    else:
        base_path = Path(__file__).resolve().parent.parent
    return base_path / "assets" / name


ICON_PATH = get_asset_path("xmldiffstudio-icon.ico")
ICON_PNG_PATH = get_asset_path("xmldiffstudio-icon.png")


class XMLDiffStudioApp:
    FILTER_OPTIONS = ("Todos", "cambio", "agregado", "eliminado", "tipo")
    THEMES = {
        "Oscuro": {
            "background": "#06101a",
            "panel": "#0d1724",
            "card": "#132235",
            "text": "#edf5ff",
            "muted": "#8fa4bc",
            "accent": "#38bdf8",
            "accent_soft": "#16344a",
            "success": "#34d399",
            "warning": "#fbbf24",
            "danger": "#f87171",
            "line": "#27405d",
            "tree_selected": "#1b4d6b",
            "tree_selected_text": "#f8fafc",
        },
        "Claro": {
            "background": "#eef4fb",
            "panel": "#dbe6f3",
            "card": "#ffffff",
            "text": "#102033",
            "muted": "#4a6179",
            "accent": "#0ea5e9",
            "accent_soft": "#c8def3",
            "success": "#15803d",
            "warning": "#b45309",
            "danger": "#b91c1c",
            "line": "#bfd0e3",
            "tree_selected": "#c7e7fb",
            "tree_selected_text": "#0f172a",
        },
    }

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self._apply_window_icon()
        self.logo_image = self._load_logo_image()

        self.config_store = ConfigStore()
        self.config = self.config_store.load()
        self.engine = DiffEngine()

        self.left_path: Path | None = None
        self.right_path: Path | None = None
        if self.config.restore_last_session:
            self.left_path = Path(self.config.last_left_path) if self.config.last_left_path else None
            self.right_path = Path(self.config.last_right_path) if self.config.last_right_path else None
        self.diff_items: list[DiffItem] = []
        self.visible_items: list[DiffItem] = []
        self.compare_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.compare_thread: threading.Thread | None = None

        self.status_var = tk.StringVar(value="Carga dos archivos XML o JSON para compararlos.")
        self.summary_var = tk.StringVar(value="Sin comparacion todavia.")
        self.left_var = tk.StringVar(value=str(self.left_path) if self.left_path else "Archivo A no cargado")
        self.right_var = tk.StringVar(value=str(self.right_path) if self.right_path else "Archivo B no cargado")
        self.filter_var = tk.StringVar(value=self.config.filter_value or "Todos")
        self.search_var = tk.StringVar(value=self.config.search_text or "")
        self.counts_var = tk.StringVar(value="Sin resultados todavia.")
        self.theme_var = tk.StringVar(value=self.config.theme or "Oscuro")
        self.total_metric_var = tk.StringVar(value="0")
        self.change_metric_var = tk.StringVar(value="0")
        self.added_metric_var = tk.StringVar(value="0")
        self.removed_metric_var = tk.StringVar(value="0")
        self.detail_meta_var = tk.StringVar(value="Selecciona una diferencia para ver el detalle completo.")

        self._configure_style()
        self._apply_window_config()
        self._build_ui()
        self._build_menu()
        self._bind_events()
        self._sync_selection_labels()

    def _apply_window_icon(self) -> None:
        if not ICON_PATH.exists():
            return
        try:
            self.root.iconbitmap(str(ICON_PATH))
        except tk.TclError:
            pass

    def _load_logo_image(self) -> tk.PhotoImage | None:
        if not ICON_PNG_PATH.exists():
            return None
        try:
            return tk.PhotoImage(file=str(ICON_PNG_PATH))
        except tk.TclError:
            return None

    def _configure_style(self) -> None:
        self.colors = self.THEMES.get(self.theme_var.get(), self.THEMES["Oscuro"]).copy()

        self.root.configure(bg=self.colors["background"])
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background=self.colors["background"], foreground=self.colors["text"])
        self.style.configure("App.TFrame", background=self.colors["background"])
        self.style.configure("Panel.TFrame", background=self.colors["panel"])
        self.style.configure("Card.TFrame", background=self.colors["card"])
        self.style.configure("Card.TLabelframe", background=self.colors["panel"], foreground=self.colors["text"])
        self.style.configure("Card.TLabelframe.Label", background=self.colors["panel"], foreground=self.colors["text"])
        self.style.configure("Toolbar.TFrame", background=self.colors["panel"])
        self.style.configure("Title.TLabel", background=self.colors["background"], foreground=self.colors["text"], font=("Segoe UI Semibold", 23))
        self.style.configure("Muted.TLabel", background=self.colors["background"], foreground=self.colors["muted"], font=("Segoe UI", 10))
        self.style.configure("PanelTitle.TLabel", background=self.colors["panel"], foreground=self.colors["text"], font=("Segoe UI Semibold", 12))
        self.style.configure("Summary.TLabel", background=self.colors["panel"], foreground=self.colors["text"], font=("Segoe UI Semibold", 16))
        self.style.configure("Info.TLabel", background=self.colors["panel"], foreground=self.colors["muted"], font=("Segoe UI", 10))
        self.style.configure("ToolbarInfo.TLabel", background=self.colors["panel"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        self.style.configure("MetricValue.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI Semibold", 16))
        self.style.configure("MetricLabel.TLabel", background=self.colors["card"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        self.style.configure("SummaryCard.TFrame", background=self.colors["card"])
        self.style.configure("SummaryValue.TLabel", background=self.colors["card"], foreground=self.colors["text"], font=("Segoe UI Semibold", 15))
        self.style.configure("SummaryCardLabel.TLabel", background=self.colors["card"], foreground=self.colors["muted"], font=("Segoe UI", 9))
        self.style.configure("App.TCheckbutton", background=self.colors["panel"], foreground=self.colors["text"], font=("Segoe UI", 10))
        self.style.configure("App.TButton", background=self.colors["card"], foreground=self.colors["text"], padding=(14, 9), borderwidth=0, font=("Segoe UI", 10))
        self.style.configure("Accent.TButton", background=self.colors["accent"], foreground="#041018", padding=(14, 10), borderwidth=0, font=("Segoe UI Semibold", 10))
        self.style.configure("App.TEntry", fieldbackground=self.colors["card"], foreground=self.colors["text"])
        self.style.configure("App.TCombobox", fieldbackground=self.colors["card"], foreground=self.colors["text"], arrowsize=14)
        self.style.map(
            "App.TCombobox",
            fieldbackground=[("readonly", self.colors["card"])],
            foreground=[("readonly", self.colors["text"])],
            selectbackground=[("readonly", self.colors["tree_selected"])],
            selectforeground=[("readonly", self.colors["tree_selected_text"])],
        )
        self.style.map(
            "App.TCheckbutton",
            background=[("active", self.colors["panel"]), ("selected", self.colors["panel"])],
            foreground=[
                ("disabled", self.colors["muted"]),
                ("active", self.colors["text"]),
                ("selected", self.colors["text"]),
            ],
            indicatorcolor=[("selected", self.colors["accent"]), ("!selected", self.colors["card"])],
            indicatorbackground=[("selected", self.colors["accent"]), ("!selected", self.colors["card"])],
        )
        self.style.configure(
            "Treeview",
            background=self.colors["card"],
            foreground=self.colors["text"],
            fieldbackground=self.colors["card"],
            rowheight=30,
            bordercolor=self.colors["line"],
            lightcolor=self.colors["line"],
            darkcolor=self.colors["line"],
        )
        self.style.configure("Treeview.Heading", background=self.colors["panel"], foreground=self.colors["text"], relief="flat", font=("Segoe UI Semibold", 10))
        self.style.map("Treeview", background=[("selected", self.colors["tree_selected"])], foreground=[("selected", self.colors["tree_selected_text"])])
        self.style.map("App.TButton", background=[("active", self.colors["accent_soft"])])
        self.style.map("Accent.TButton", background=[("active", "#7dd3fc")])

    def _build_menu(self) -> None:
        self.menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_menu.add_command(label="Cargar Archivo A", command=lambda: self.select_file("left"))
        file_menu.add_command(label="Cargar Archivo B", command=lambda: self.select_file("right"))
        file_menu.add_separator()
        file_menu.add_command(label="Comparar", command=self.compare_files, accelerator="F5")
        file_menu.add_command(label="Exportar Reporte", command=self.export_report)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.on_close)
        self.menu_bar.add_cascade(label="Archivo", menu=file_menu)

        view_menu = tk.Menu(self.menu_bar, tearoff=0)
        view_menu.add_radiobutton(label="Tema Oscuro", variable=self.theme_var, value="Oscuro", command=self.change_theme)
        view_menu.add_radiobutton(label="Tema Claro", variable=self.theme_var, value="Claro", command=self.change_theme)
        view_menu.add_separator()
        view_menu.add_command(label="Preferencias", command=self.show_preferences)
        self.menu_bar.add_cascade(label="Ver", menu=view_menu)

        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        help_menu.add_command(label="Atajos", command=self.show_shortcuts)
        help_menu.add_command(label="Acerca de", command=self.show_about)
        self.menu_bar.add_cascade(label="Ayuda", menu=help_menu)

        self.root.config(menu=self.menu_bar)

    def _apply_window_config(self) -> None:
        self.root.geometry(self.config.window_geometry or "1380x860")
        self.root.minsize(1180, 760)

    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, style="App.TFrame", padding=18)
        root_frame.pack(fill="both", expand=True)
        root_frame.columnconfigure(0, weight=1)
        root_frame.rowconfigure(2, weight=1)

        header = ttk.Frame(root_frame, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text=APP_NAME, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Compara XML y JSON, detecta cambios de estructura, atributos, texto y listas repetidas.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))

        toolbar = ttk.Frame(root_frame, style="Toolbar.TFrame", padding=12)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        toolbar.columnconfigure(5, weight=1)
        self._build_toolbar(toolbar)

        content = ttk.Frame(root_frame, style="App.TFrame")
        content.grid(row=2, column=0, sticky="nsew")
        content.columnconfigure(0, weight=0)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(content, style="Panel.TFrame", padding=16)
        left_panel.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        left_panel.configure(width=400)
        left_panel.grid_propagate(False)
        left_panel.columnconfigure(0, weight=1)

        right_panel = ttk.Frame(content, style="Panel.TFrame", padding=16)
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(3, weight=1)

        self._build_left_panel(left_panel)
        self._build_right_panel(right_panel)

    def _build_toolbar(self, parent: ttk.Frame) -> None:
        ttk.Button(parent, text="Abrir A", style="App.TButton", command=lambda: self.select_file("left")).grid(row=0, column=0, sticky="w")
        ttk.Button(parent, text="Abrir B", style="App.TButton", command=lambda: self.select_file("right")).grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.compare_button = ttk.Button(parent, text="Comparar", style="Accent.TButton", command=self.compare_files)
        self.compare_button.grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Button(parent, text="Exportar", style="App.TButton", command=self.export_report).grid(row=0, column=3, sticky="w", padx=(8, 0))
        ttk.Button(parent, text="Limpiar", style="App.TButton", command=self.clear_all).grid(row=0, column=4, sticky="w", padx=(8, 0))
        ttk.Label(parent, text="Usa Ver para tema y preferencias, Ayuda para acerca de.", style="ToolbarInfo.TLabel").grid(row=0, column=5, sticky="e")

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Entradas", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            parent,
            text="Selecciona tus archivos desde la barra superior o el menu Archivo. Este panel se concentra en contexto y estado actual.",
            style="Info.TLabel",
            wraplength=350,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 12))

        metrics = ttk.Frame(parent, style="Panel.TFrame")
        metrics.grid(row=2, column=0, sticky="ew")
        metrics.columnconfigure((0, 1), weight=1)

        left_metric = ttk.Frame(metrics, style="Card.TFrame", padding=12)
        left_metric.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        left_metric.columnconfigure(0, weight=1)
        ttk.Label(left_metric, text="Archivo A", style="MetricLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.left_status_metric = ttk.Label(left_metric, text="No cargado", style="MetricValue.TLabel")
        self.left_status_metric.grid(row=1, column=0, sticky="w", pady=(6, 0))

        right_metric = ttk.Frame(metrics, style="Card.TFrame", padding=12)
        right_metric.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        right_metric.columnconfigure(0, weight=1)
        ttk.Label(right_metric, text="Archivo B", style="MetricLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.right_status_metric = ttk.Label(right_metric, text="No cargado", style="MetricValue.TLabel")
        self.right_status_metric.grid(row=1, column=0, sticky="w", pady=(6, 0))

        left_box = ttk.LabelFrame(parent, text="Archivo A", style="Card.TLabelframe", padding=12)
        left_box.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        left_box.columnconfigure(0, weight=1)
        ttk.Label(left_box, textvariable=self.left_var, style="Info.TLabel", wraplength=330, justify="left").grid(row=0, column=0, sticky="ew")
        self.left_drop_label = tk.Label(
            left_box,
            text="Arrastra aqui el Archivo A",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            relief="solid",
            bd=1,
            padx=10,
            pady=10,
            anchor="center",
        )
        self.left_drop_label.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        right_box = ttk.LabelFrame(parent, text="Archivo B", style="Card.TLabelframe", padding=12)
        right_box.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        right_box.columnconfigure(0, weight=1)
        ttk.Label(right_box, textvariable=self.right_var, style="Info.TLabel", wraplength=330, justify="left").grid(row=0, column=0, sticky="ew")
        self.right_drop_label = tk.Label(
            right_box,
            text="Arrastra aqui el Archivo B",
            bg=self.colors["card"],
            fg=self.colors["muted"],
            relief="solid",
            bd=1,
            padx=10,
            pady=10,
            anchor="center",
        )
        self.right_drop_label.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        self._register_drop_target(self.left_drop_label, "left")
        self._register_drop_target(self.right_drop_label, "right")

        progress_box = ttk.LabelFrame(parent, text="Proceso", style="Card.TLabelframe", padding=12)
        progress_box.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        progress_box.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(progress_box, mode="indeterminate")
        self.progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(progress_box, textvariable=self.counts_var, style="Info.TLabel", wraplength=330, justify="left").grid(row=1, column=0, sticky="ew", pady=(8, 0))

        utility_box = ttk.LabelFrame(parent, text="Accesos", style="Card.TLabelframe", padding=12)
        utility_box.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        utility_box.columnconfigure(0, weight=1)
        ttk.Button(utility_box, text="Copiar seleccion", style="App.TButton", command=self.copy_selected).grid(row=0, column=0, sticky="ew")

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        summary_box = ttk.LabelFrame(parent, text="Resumen", style="Card.TLabelframe", padding=12)
        summary_box.grid(row=0, column=0, sticky="ew")
        summary_box.columnconfigure(0, weight=1)
        self.summary_label = ttk.Label(summary_box, textvariable=self.summary_var, style="Summary.TLabel", wraplength=820)
        self.summary_label.grid(row=0, column=0, sticky="w")
        ttk.Label(summary_box, textvariable=self.status_var, style="Info.TLabel", wraplength=820, justify="left").grid(row=1, column=0, sticky="ew", pady=(8, 0))

        metrics_box = ttk.Frame(parent, style="Panel.TFrame")
        metrics_box.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        metrics_box.columnconfigure((0, 1, 2, 3), weight=1)
        self._build_summary_metric(metrics_box, 0, "Total", self.total_metric_var)
        self._build_summary_metric(metrics_box, 1, "Cambios", self.change_metric_var)
        self._build_summary_metric(metrics_box, 2, "Agregados", self.added_metric_var)
        self._build_summary_metric(metrics_box, 3, "Eliminados", self.removed_metric_var)

        filter_box = ttk.LabelFrame(parent, text="Filtros", style="Card.TLabelframe", padding=12)
        filter_box.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        filter_box.columnconfigure(3, weight=1)
        ttk.Label(filter_box, text="Tipo", style="Info.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.filter_combo = ttk.Combobox(filter_box, textvariable=self.filter_var, state="readonly", values=self.FILTER_OPTIONS, style="App.TCombobox")
        self.filter_combo.grid(row=0, column=1, sticky="w")
        ttk.Label(filter_box, text="Buscar", style="Info.TLabel").grid(row=0, column=2, sticky="w", padx=(18, 8))
        self.search_entry = ttk.Entry(filter_box, textvariable=self.search_var, style="App.TEntry")
        self.search_entry.grid(row=0, column=3, sticky="ew")

        results_box = ttk.LabelFrame(parent, text="Diferencias", style="Card.TLabelframe", padding=10)
        results_box.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        results_box.columnconfigure(0, weight=1)
        results_box.rowconfigure(0, weight=1)

        columns = ("change_type", "path", "before", "after")
        self.results_tree = ttk.Treeview(results_box, columns=columns, show="headings")
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        self.results_tree.heading("change_type", text="Tipo")
        self.results_tree.heading("path", text="Ruta")
        self.results_tree.heading("before", text="Antes")
        self.results_tree.heading("after", text="Despues")
        self.results_tree.column("change_type", width=120, anchor="center", stretch=False)
        self.results_tree.column("path", width=360, anchor="w")
        self.results_tree.column("before", width=280, anchor="w")
        self.results_tree.column("after", width=280, anchor="w")
        self.results_tree.tag_configure("cambio", background="#2b2230")
        self.results_tree.tag_configure("agregado", background="#163229")
        self.results_tree.tag_configure("eliminado", background="#331d22")
        self.results_tree.tag_configure("tipo", background="#312817")

        y_scroll = ttk.Scrollbar(results_box, orient="vertical", command=self.results_tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(results_box, orient="horizontal", command=self.results_tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.results_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        detail_box = ttk.LabelFrame(parent, text="Detalle", style="Card.TLabelframe", padding=12)
        detail_box.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        detail_box.columnconfigure((0, 1), weight=1)
        ttk.Label(detail_box, textvariable=self.detail_meta_var, style="Info.TLabel", wraplength=820, justify="left").grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        before_box = ttk.LabelFrame(detail_box, text="Antes", style="Card.TLabelframe", padding=8)
        before_box.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        before_box.columnconfigure(0, weight=1)
        after_box = ttk.LabelFrame(detail_box, text="Despues", style="Card.TLabelframe", padding=8)
        after_box.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        after_box.columnconfigure(0, weight=1)
        self.before_text = tk.Text(before_box, height=10, wrap="word", bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["text"], relief="flat", padx=10, pady=10)
        self.before_text.grid(row=0, column=0, sticky="ew")
        self.after_text = tk.Text(after_box, height=10, wrap="word", bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["text"], relief="flat", padx=10, pady=10)
        self.after_text.grid(row=0, column=0, sticky="ew")
        self._set_detail("Selecciona una diferencia para ver el detalle completo.", "", "")

    def _build_summary_metric(self, parent: ttk.Frame, column: int, label: str, variable: tk.StringVar) -> None:
        card = ttk.Frame(parent, style="SummaryCard.TFrame", padding=12)
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text=label, style="SummaryCardLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, textvariable=variable, style="SummaryValue.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 0))

    def _bind_events(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.filter_var.trace_add("write", lambda *_: self.apply_filters())
        self.search_var.trace_add("write", lambda *_: self.apply_filters())
        self.theme_var.trace_add("write", lambda *_: self.change_theme())
        self.results_tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.results_tree.bind("<Control-c>", lambda _event: self.copy_selected())
        self.root.bind("<F5>", lambda _event: self.compare_files())

    def _sync_selection_labels(self) -> None:
        if self.left_path:
            self.left_var.set(str(self.left_path))
        if self.right_path:
            self.right_var.set(str(self.right_path))
        self._update_file_metrics()

    def _update_file_metrics(self) -> None:
        self.left_status_metric.configure(text="Listo" if self.left_path else "No cargado")
        self.right_status_metric.configure(text="Listo" if self.right_path else "No cargado")

    def _register_drop_target(self, widget: tk.Widget, side: str) -> None:
        if not TkinterDnD or not DND_FILES:
            return
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<DropEnter>>", lambda _event, target=widget: self._set_drop_highlight(target, True))
        widget.dnd_bind("<<DropLeave>>", lambda _event, target=widget: self._set_drop_highlight(target, False))
        widget.dnd_bind("<<Drop>>", lambda event, target_side=side: self._handle_drop(event.data, target_side))

    def _handle_drop(self, raw_data: str, side: str) -> None:
        paths = self._parse_dropped_files(raw_data)
        target = self.left_drop_label if side == "left" else self.right_drop_label
        self._set_drop_highlight(target, False)
        if not paths:
            return
        self._load_path_into_side(paths[0], side)

    def _parse_dropped_files(self, raw_data: str) -> list[Path]:
        normalized = self.root.tk.splitlist(raw_data)
        paths: list[Path] = []
        for item in normalized:
            cleaned = item.strip().strip("{}")
            if not cleaned:
                continue
            path = Path(cleaned).resolve()
            if path.suffix.lower() not in {".xml", ".json"}:
                continue
            if path.exists():
                paths.append(path)
        return paths

    def _set_drop_highlight(self, widget: tk.Widget, active: bool) -> None:
        background = self.colors["tree_selected"] if active else self.colors["card"]
        foreground = self.colors["tree_selected_text"] if active else self.colors["muted"]
        widget.configure(bg=background, fg=foreground)

    def _load_path_into_side(self, path: Path, side: str) -> None:
        self.config.last_directory = str(path.parent)
        if side == "left":
            self.left_path = path
            self.left_var.set(str(path))
        else:
            self.right_path = path
            self.right_var.set(str(path))
        self._update_file_metrics()
        self.status_var.set(f"{path.name} cargado en {'Archivo A' if side == 'left' else 'Archivo B'}.")
        self.save_config()
        if self.config.auto_compare_on_load and self.left_path and self.right_path:
            self.compare_files()

    def select_file(self, side: str) -> None:
        initial_dir = self.config.last_directory or str(Path.home())
        selected = filedialog.askopenfilename(
            title="Selecciona un XML o JSON",
            initialdir=initial_dir,
            filetypes=[("Supported files", "*.xml *.json"), ("Todos los archivos", "*.*")],
        )
        if not selected:
            return

        path = Path(selected).resolve()
        self._load_path_into_side(path, side)
        self.status_var.set("Archivos listos para comparar.")

    def clear_all(self) -> None:
        if self.compare_thread and self.compare_thread.is_alive():
            messagebox.showinfo(APP_NAME, "Espera a que termine la comparacion actual.")
            return

        self.left_path = None
        self.right_path = None
        self.left_var.set("Archivo A no cargado")
        self.right_var.set("Archivo B no cargado")
        self._update_file_metrics()
        self.total_metric_var.set("0")
        self.change_metric_var.set("0")
        self.added_metric_var.set("0")
        self.removed_metric_var.set("0")
        self.summary_var.set("Sin comparacion todavia.")
        self.summary_label.configure(foreground=self.colors["text"])
        self.status_var.set("Carga dos archivos XML o JSON para compararlos.")
        self.counts_var.set("Sin resultados todavia.")
        self.diff_items.clear()
        self.visible_items.clear()
        self.filter_var.set("Todos")
        self.search_var.set("")
        self.results_tree.delete(*self.results_tree.get_children())
        self._set_detail("Selecciona una diferencia para ver el detalle completo.", "", "")
        self.save_config()

    def compare_files(self) -> None:
        if self.compare_thread and self.compare_thread.is_alive():
            return

        if not self.left_path or not self.right_path:
            messagebox.showwarning(APP_NAME, "Carga ambos archivos antes de comparar.")
            return

        if self.left_path.suffix.lower() != self.right_path.suffix.lower():
            messagebox.showwarning(APP_NAME, "Ambos archivos deben ser del mismo tipo.")
            return

        self.compare_button.state(["disabled"])
        self.progress.start(12)
        self.status_var.set("Comparando archivos...")
        self.counts_var.set("Procesando diff en segundo plano.")
        self._set_detail("La comparacion esta en proceso. Puedes esperar aqui sin congelar la ventana.")

        self.compare_thread = threading.Thread(target=self._run_compare_job, daemon=True)
        self.compare_thread.start()
        self.root.after(120, self._poll_compare_queue)

    def _run_compare_job(self) -> None:
        assert self.left_path is not None
        assert self.right_path is not None
        try:
            result = self.engine.compare_paths(self.left_path, self.right_path)
            self.compare_queue.put(("success", result))
        except (OSError, json.JSONDecodeError, etree.XMLSyntaxError, ValueError) as exc:
            self.compare_queue.put(("error", str(exc)))

    def _poll_compare_queue(self) -> None:
        try:
            status, payload = self.compare_queue.get_nowait()
        except queue.Empty:
            if self.compare_thread and self.compare_thread.is_alive():
                self.root.after(120, self._poll_compare_queue)
            return

        self.progress.stop()
        self.compare_button.state(["!disabled"])

        if status == "error":
            self.status_var.set("La comparacion fallo.")
            self.counts_var.set("No se pudo generar el diff.")
            messagebox.showerror(APP_NAME, f"No se pudo leer uno de los archivos:\n\n{payload}")
            return

        self._apply_diff_result(payload)

    def _apply_diff_result(self, result: DiffResult) -> None:
        self.diff_items = result.items
        self.apply_filters()

        counts = result.counts
        self.counts_var.set(
            f"Total: {counts['total']} | cambios: {counts['cambio']} | agregados: {counts['agregado']} | eliminados: {counts['eliminado']} | tipo: {counts['tipo']}"
        )
        self.total_metric_var.set(str(counts["total"]))
        self.change_metric_var.set(str(counts["cambio"]))
        self.added_metric_var.set(str(counts["agregado"]))
        self.removed_metric_var.set(str(counts["eliminado"]))

        if not self.diff_items:
            self.summary_var.set("Sin diferencias")
            self.summary_label.configure(foreground=self.colors["success"])
            self.status_var.set("Los dos archivos son equivalentes en estructura y valores.")
            self._set_detail("No se encontraron diferencias.", "", "")
        else:
            self.summary_var.set("Diferencias encontradas")
            self.summary_label.configure(foreground=self.colors["warning"])
            self.status_var.set(f"Se detectaron {len(self.diff_items)} diferencia(s).")
            if self.visible_items:
                self.on_tree_select()

        self.save_config()

    def apply_filters(self) -> None:
        selected_type = self.filter_var.get()
        search_text = self.search_var.get().strip().lower()

        self.visible_items = []
        for item in self.diff_items:
            if selected_type != "Todos" and item.change_type != selected_type:
                continue
            searchable = " ".join((item.change_type, item.path, item.before, item.after)).lower()
            if search_text and search_text not in searchable:
                continue
            self.visible_items.append(item)

        self.results_tree.delete(*self.results_tree.get_children())
        for index, item in enumerate(self.visible_items):
            self.results_tree.insert("", "end", iid=str(index), values=(item.change_type, item.path, item.before, item.after), tags=(item.change_type,))

        if self.visible_items:
            self.results_tree.selection_set("0")
            self.results_tree.focus("0")
            self.on_tree_select()
        else:
            self._set_detail("No hay resultados para el filtro actual.", "", "")

        if self.diff_items:
            self.status_var.set(f"Mostrando {len(self.visible_items)} de {len(self.diff_items)} diferencia(s).")

        self.save_config()

    def on_tree_select(self, _event: Any | None = None) -> None:
        selection = self.results_tree.selection()
        if not selection:
            return
        item = self.visible_items[int(selection[0])]
        meta = f"Tipo: {item.change_type} | Ruta: {item.path}"
        self._set_detail(meta, item.before or "(vacio)", item.after or "(vacio)")

    def _set_detail(self, meta_text: str, before_text: str, after_text: str) -> None:
        self.detail_meta_var.set(meta_text)
        for widget, text in ((self.before_text, before_text), (self.after_text, after_text)):
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", text)
            widget.configure(state="disabled")

    def change_theme(self) -> None:
        self._configure_style()
        self._refresh_widget_colors()
        self.save_config()

    def _refresh_widget_colors(self) -> None:
        self.root.configure(bg=self.colors["background"])
        for widget in (self.before_text, self.after_text):
            widget.configure(
                bg=self.colors["card"],
                fg=self.colors["text"],
                insertbackground=self.colors["text"],
                selectbackground=self.colors["tree_selected"],
                selectforeground=self.colors["tree_selected_text"],
            )
        for widget in (self.left_drop_label, self.right_drop_label):
            widget.configure(bg=self.colors["card"], fg=self.colors["muted"])
        self.summary_label.configure(background=self.colors["panel"], foreground=self.colors["text"])
        if self.diff_items:
            if self.summary_var.get() == "Sin diferencias":
                self.summary_label.configure(foreground=self.colors["success"])
            else:
                self.summary_label.configure(foreground=self.colors["warning"])

    def show_shortcuts(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            "Atajos disponibles:\n\nF5: comparar archivos\nCtrl+C: copiar la diferencia seleccionada",
        )

    def show_about(self) -> None:
        about_window = tk.Toplevel(self.root)
        about_window.title(f"Acerca de {APP_NAME}")
        about_window.transient(self.root)
        about_window.resizable(False, False)
        about_window.configure(bg=self.colors["background"])

        frame = ttk.Frame(about_window, style="Panel.TFrame", padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        current_row = 0
        if self.logo_image:
            ttk.Label(frame, image=self.logo_image, style="Panel.TFrame").grid(row=current_row, column=0, sticky="w", pady=(0, 8))
            current_row += 1
        ttk.Label(frame, text=APP_NAME, style="Title.TLabel").grid(row=current_row, column=0, sticky="w")
        current_row += 1
        ttk.Label(frame, text=f"Version {APP_VERSION}", style="Muted.TLabel").grid(row=current_row, column=0, sticky="w", pady=(4, 12))
        current_row += 1
        ttk.Label(
            frame,
            text="Comparador de XML y JSON para revisar diferencias de estructura, atributos, texto y listas con una interfaz de escritorio mas comoda.",
            style="Info.TLabel",
            wraplength=420,
            justify="left",
        ).grid(row=current_row, column=0, sticky="ew")
        current_row += 1
        ttk.Label(
            frame,
            text=f"Tema actual: {self.theme_var.get()}\nFunciones clave: filtros, busqueda, detalle, copia, exportacion y comparacion en segundo plano.",
            style="Info.TLabel",
            wraplength=420,
            justify="left",
        ).grid(row=current_row, column=0, sticky="ew", pady=(12, 0))
        current_row += 1
        ttk.Button(frame, text="Cerrar", style="Accent.TButton", command=about_window.destroy).grid(row=current_row, column=0, sticky="e", pady=(16, 0))

        about_window.grab_set()

    def show_preferences(self) -> None:
        pref_window = tk.Toplevel(self.root)
        pref_window.title("Preferencias")
        pref_window.transient(self.root)
        pref_window.resizable(False, False)
        pref_window.configure(bg=self.colors["background"])

        restore_var = tk.BooleanVar(value=self.config.restore_last_session)
        auto_compare_var = tk.BooleanVar(value=self.config.auto_compare_on_load)
        export_var = tk.StringVar(value=self.config.default_export_format)

        frame = ttk.Frame(pref_window, style="Panel.TFrame", padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Preferencias", style="PanelTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(frame, text="Restaurar ultimos archivos al iniciar", variable=restore_var, style="App.TCheckbutton").grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Checkbutton(frame, text="Comparar automaticamente al cargar ambos archivos", variable=auto_compare_var, style="App.TCheckbutton").grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(frame, text="Formato de exportacion por defecto", style="Info.TLabel").grid(row=3, column=0, sticky="w", pady=(14, 0))
        ttk.Combobox(frame, textvariable=export_var, state="readonly", values=("txt", "csv", "json"), width=12, style="App.TCombobox").grid(row=3, column=1, sticky="w", pady=(14, 0))

        button_row = ttk.Frame(frame, style="Panel.TFrame")
        button_row.grid(row=4, column=0, columnspan=2, sticky="e", pady=(18, 0))
        ttk.Button(button_row, text="Cancelar", style="App.TButton", command=pref_window.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(
            button_row,
            text="Guardar",
            style="Accent.TButton",
            command=lambda: self._save_preferences(pref_window, restore_var.get(), auto_compare_var.get(), export_var.get()),
        ).grid(row=0, column=1)

        pref_window.grab_set()

    def _save_preferences(self, window: tk.Toplevel, restore_last_session: bool, auto_compare_on_load: bool, default_export_format: str) -> None:
        self.config.restore_last_session = restore_last_session
        self.config.auto_compare_on_load = auto_compare_on_load
        self.config.default_export_format = default_export_format
        self.save_config()
        window.destroy()
        self.status_var.set("Preferencias actualizadas.")

    def copy_selected(self) -> None:
        selection = self.results_tree.selection()
        if not selection:
            messagebox.showinfo(APP_NAME, "Selecciona una diferencia primero.")
            return
        item = self.visible_items[int(selection[0])]
        payload = json.dumps(asdict(item), ensure_ascii=False, indent=2)
        self.root.clipboard_clear()
        self.root.clipboard_append(payload)
        self.status_var.set("Diferencia copiada al portapapeles.")

    def export_report(self) -> None:
        if not self.diff_items:
            messagebox.showinfo(APP_NAME, "Todavia no hay diferencias para exportar.")
            return

        initial_dir = self.config.last_export_directory or self.config.last_directory or str(Path.home())
        default_extension = f".{self.config.default_export_format}"
        target = filedialog.asksaveasfilename(
            title="Exportar reporte",
            initialdir=initial_dir,
            defaultextension=default_extension,
            initialfile=f"xmldiffstudio_report{default_extension}",
            filetypes=[
                ("Texto", "*.txt"),
                ("CSV", "*.csv"),
                ("JSON", "*.json"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not target:
            return

        path = Path(target)
        self.config.last_export_directory = str(path.parent)

        if path.suffix.lower() == ".csv":
            self._export_csv(path)
        elif path.suffix.lower() == ".json":
            self._export_json(path)
        else:
            self._export_txt(path)

        self.status_var.set(f"Reporte exportado en {path.name}.")
        self.save_config()

    def _export_txt(self, path: Path) -> None:
        lines = [f"[{item.change_type}] {item.path} | Antes: {item.before} | Despues: {item.after}" for item in self.diff_items]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _export_csv(self, path: Path) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["change_type", "path", "before", "after"])
            writer.writeheader()
            for item in self.diff_items:
                writer.writerow(asdict(item))

    def _export_json(self, path: Path) -> None:
        payload = {"summary": {"total": len(self.diff_items)}, "items": [asdict(item) for item in self.diff_items]}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def save_config(self) -> None:
        self.config.window_geometry = self.root.geometry()
        self.config.last_left_path = str(self.left_path) if self.left_path else ""
        self.config.last_right_path = str(self.right_path) if self.right_path else ""
        self.config.filter_value = self.filter_var.get()
        self.config.search_text = self.search_var.get()
        self.config.theme = self.theme_var.get()
        self.config.restore_last_session = getattr(self.config, "restore_last_session", True)
        self.config.auto_compare_on_load = getattr(self.config, "auto_compare_on_load", False)
        self.config.default_export_format = getattr(self.config, "default_export_format", "txt")
        self.config_store.save(self.config)

    def on_close(self) -> None:
        self.save_config()
        self.root.destroy()


def main() -> None:
    root_class = TkinterDnD.Tk if TkinterDnD else tk.Tk
    root = root_class()
    root.withdraw()
    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(bg="#06101a")

    container = tk.Frame(splash, bg="#06101a", padx=24, pady=20)
    container.pack(fill="both", expand=True)

    splash_logo = None
    if ICON_PNG_PATH.exists():
        try:
            splash_logo = tk.PhotoImage(file=str(ICON_PNG_PATH))
            logo_label = tk.Label(container, image=splash_logo, bg="#06101a")
            logo_label.image = splash_logo
            logo_label.pack(anchor="center", pady=(0, 10))
        except tk.TclError:
            splash_logo = None

    tk.Label(container, text=APP_NAME, bg="#06101a", fg="#edf5ff", font=("Segoe UI Semibold", 18)).pack()
    tk.Label(container, text="Cargando comparador XML/JSON...", bg="#06101a", fg="#8fa4bc", font=("Segoe UI", 10)).pack(pady=(6, 0))

    splash.update_idletasks()
    width = splash.winfo_width()
    height = splash.winfo_height()
    screen_w = splash.winfo_screenwidth()
    screen_h = splash.winfo_screenheight()
    pos_x = (screen_w - width) // 2
    pos_y = (screen_h - height) // 2
    splash.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    XMLDiffStudioApp(root)
    root.after(900, lambda: (splash.destroy(), root.deiconify()))
    root.mainloop()
