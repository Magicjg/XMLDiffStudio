from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from lxml import etree


APP_NAME = "XMLDiffStudio"
APP_VERSION = "0.1.0"


def get_config_path() -> Path:
    if getattr(sys, "frozen", False):
        appdata_root = Path(os.getenv("APPDATA") or str(Path.home()))
        return appdata_root / APP_NAME / "config.json"
    return Path(__file__).resolve().parent / "config.json"


def split_qname(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{"):
        namespace, local_name = tag[1:].split("}", 1)
        return namespace, local_name
    return None, tag


@dataclass
class DiffItem:
    change_type: str
    path: str
    before: str
    after: str


class XMLDiffStudioApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1380x860")
        self.root.minsize(1180, 760)

        self.left_path: Path | None = None
        self.right_path: Path | None = None
        self.diff_items: list[DiffItem] = []

        self.status_var = tk.StringVar(value="Carga dos archivos XML o JSON para compararlos.")
        self.summary_var = tk.StringVar(value="Sin comparacion todavia.")
        self.left_var = tk.StringVar(value="Archivo A no cargado")
        self.right_var = tk.StringVar(value="Archivo B no cargado")

        self._configure_style()
        self._build_ui()

    def _configure_style(self) -> None:
        self.colors = {
            "background": "#07111f",
            "panel": "#0b1220",
            "card": "#152235",
            "text": "#e2e8f0",
            "muted": "#94a3b8",
            "accent": "#22d3ee",
            "accent_soft": "#10364a",
            "success": "#22c55e",
            "warning": "#f59e0b",
            "danger": "#f87171",
            "line": "#20314a",
            "tree_selected": "#164e63",
            "tree_selected_text": "#f8fafc",
        }

        self.root.configure(bg=self.colors["background"])
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background=self.colors["background"], foreground=self.colors["text"])
        self.style.configure("App.TFrame", background=self.colors["background"])
        self.style.configure("Panel.TFrame", background=self.colors["panel"])
        self.style.configure("Card.TFrame", background=self.colors["card"])
        self.style.configure("Card.TLabelframe", background=self.colors["panel"], foreground=self.colors["text"])
        self.style.configure("Card.TLabelframe.Label", background=self.colors["panel"], foreground=self.colors["text"])
        self.style.configure("Title.TLabel", background=self.colors["background"], foreground=self.colors["text"], font=("Segoe UI Semibold", 22))
        self.style.configure("Muted.TLabel", background=self.colors["background"], foreground=self.colors["muted"], font=("Segoe UI", 10))
        self.style.configure("PanelTitle.TLabel", background=self.colors["panel"], foreground=self.colors["text"], font=("Segoe UI Semibold", 12))
        self.style.configure("Summary.TLabel", background=self.colors["panel"], foreground=self.colors["text"], font=("Segoe UI Semibold", 16))
        self.style.configure("Info.TLabel", background=self.colors["panel"], foreground=self.colors["muted"], font=("Segoe UI", 10))
        self.style.configure("App.TButton", background=self.colors["card"], foreground=self.colors["text"], padding=(14, 9), borderwidth=0, font=("Segoe UI", 10))
        self.style.configure("Accent.TButton", background=self.colors["accent"], foreground="#041018", padding=(14, 10), borderwidth=0, font=("Segoe UI Semibold", 10))
        self.style.map("App.TButton", background=[("active", self.colors["accent_soft"])])
        self.style.map("Accent.TButton", background=[("active", "#67e8f9")])
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

    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, style="App.TFrame", padding=18)
        root_frame.pack(fill="both", expand=True)
        root_frame.columnconfigure(0, weight=1)
        root_frame.rowconfigure(1, weight=1)

        header = ttk.Frame(root_frame, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text=APP_NAME, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Compara XML y JSON, detecta cambios de estructura, atributos y valores.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))

        content = ttk.Frame(root_frame, style="App.TFrame")
        content.grid(row=1, column=0, sticky="nsew")
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
        right_panel.rowconfigure(2, weight=1)

        self._build_left_panel(left_panel)
        self._build_right_panel(right_panel)

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Entradas", style="PanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            parent,
            text="Carga dos archivos del mismo tipo. XML con XML o JSON con JSON.",
            style="Info.TLabel",
            wraplength=350,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(6, 12))

        left_box = ttk.LabelFrame(parent, text="Archivo A", style="Card.TLabelframe", padding=12)
        left_box.grid(row=2, column=0, sticky="ew")
        left_box.columnconfigure(0, weight=1)
        ttk.Label(left_box, textvariable=self.left_var, style="Info.TLabel", wraplength=330, justify="left").grid(row=0, column=0, sticky="ew")
        ttk.Button(left_box, text="Cargar A", style="App.TButton", command=lambda: self.select_file("left")).grid(row=1, column=0, sticky="ew", pady=(10, 0))

        right_box = ttk.LabelFrame(parent, text="Archivo B", style="Card.TLabelframe", padding=12)
        right_box.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        right_box.columnconfigure(0, weight=1)
        ttk.Label(right_box, textvariable=self.right_var, style="Info.TLabel", wraplength=330, justify="left").grid(row=0, column=0, sticky="ew")
        ttk.Button(right_box, text="Cargar B", style="App.TButton", command=lambda: self.select_file("right")).grid(row=1, column=0, sticky="ew", pady=(10, 0))

        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        actions.columnconfigure((0, 1), weight=1)
        ttk.Button(actions, text="Comparar", style="Accent.TButton", command=self.compare_files).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="Limpiar", style="App.TButton", command=self.clear_all).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        export_row = ttk.Frame(parent, style="Panel.TFrame")
        export_row.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        export_row.columnconfigure(0, weight=1)
        ttk.Button(export_row, text="Exportar reporte", style="App.TButton", command=self.export_report).grid(row=0, column=0, sticky="ew")

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        summary_box = ttk.LabelFrame(parent, text="Resumen", style="Card.TLabelframe", padding=12)
        summary_box.grid(row=0, column=0, sticky="ew")
        summary_box.columnconfigure(0, weight=1)
        self.summary_label = ttk.Label(summary_box, textvariable=self.summary_var, style="Summary.TLabel", wraplength=820)
        self.summary_label.grid(row=0, column=0, sticky="w")
        ttk.Label(summary_box, textvariable=self.status_var, style="Info.TLabel", wraplength=820, justify="left").grid(row=1, column=0, sticky="ew", pady=(8, 0))

        results_box = ttk.LabelFrame(parent, text="Diferencias", style="Card.TLabelframe", padding=10)
        results_box.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
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
        self.results_tree.column("path", width=320, anchor="w")
        self.results_tree.column("before", width=250, anchor="w")
        self.results_tree.column("after", width=250, anchor="w")

        y_scroll = ttk.Scrollbar(results_box, orient="vertical", command=self.results_tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = ttk.Scrollbar(results_box, orient="horizontal", command=self.results_tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.results_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

    def select_file(self, side: str) -> None:
        selected = filedialog.askopenfilename(
            title="Selecciona un XML o JSON",
            filetypes=[("Supported files", "*.xml *.json"), ("Todos los archivos", "*.*")],
        )
        if not selected:
            return

        path = Path(selected).resolve()
        if side == "left":
            self.left_path = path
            self.left_var.set(str(path))
        else:
            self.right_path = path
            self.right_var.set(str(path))
        self.status_var.set("Archivos listos para comparar.")

    def clear_all(self) -> None:
        self.left_path = None
        self.right_path = None
        self.left_var.set("Archivo A no cargado")
        self.right_var.set("Archivo B no cargado")
        self.summary_var.set("Sin comparacion todavia.")
        self.status_var.set("Carga dos archivos XML o JSON para compararlos.")
        self.diff_items.clear()
        self.results_tree.delete(*self.results_tree.get_children())

    def export_report(self) -> None:
        if not self.diff_items:
            messagebox.showinfo(APP_NAME, "Todavia no hay diferencias para exportar.")
            return
        target = filedialog.asksaveasfilename(
            title="Exportar reporte",
            defaultextension=".txt",
            initialfile="xmldiffstudio_report.txt",
            filetypes=[("Text files", "*.txt"), ("Todos los archivos", "*.*")],
        )
        if not target:
            return
        lines = [f"[{item.change_type}] {item.path} | Antes: {item.before} | Despues: {item.after}" for item in self.diff_items]
        Path(target).write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.status_var.set(f"Reporte exportado en {Path(target).name}.")

    def compare_files(self) -> None:
        if not self.left_path or not self.right_path:
            messagebox.showwarning(APP_NAME, "Carga ambos archivos antes de comparar.")
            return

        if self.left_path.suffix.lower() != self.right_path.suffix.lower():
            messagebox.showwarning(APP_NAME, "Ambos archivos deben ser del mismo tipo.")
            return

        try:
            if self.left_path.suffix.lower() == ".xml":
                left_data = self._load_xml_as_data(self.left_path)
                right_data = self._load_xml_as_data(self.right_path)
            elif self.left_path.suffix.lower() == ".json":
                left_data = json.loads(self.left_path.read_text(encoding="utf-8"))
                right_data = json.loads(self.right_path.read_text(encoding="utf-8"))
            else:
                messagebox.showwarning(APP_NAME, "Solo se soportan XML y JSON.")
                return
        except (OSError, json.JSONDecodeError, etree.XMLSyntaxError) as exc:
            messagebox.showerror(APP_NAME, f"No se pudo leer uno de los archivos:\n\n{exc}")
            return

        self.diff_items = []
        self._compare_nodes(left_data, right_data, "$")
        self.results_tree.delete(*self.results_tree.get_children())
        for item in self.diff_items:
            self.results_tree.insert("", "end", values=(item.change_type, item.path, item.before, item.after))

        if not self.diff_items:
            self.summary_var.set("Sin diferencias")
            self.summary_label.configure(foreground=self.colors["success"])
            self.status_var.set("Los dos archivos son equivalentes en estructura y valores.")
            return

        self.summary_var.set("Diferencias encontradas")
        self.summary_label.configure(foreground=self.colors["warning"])
        self.status_var.set(f"Se detectaron {len(self.diff_items)} diferencia(s).")

    def _load_xml_as_data(self, path: Path) -> Any:
        tree = etree.parse(str(path))
        return self._element_to_data(tree.getroot())

    def _element_to_data(self, element) -> Any:
        namespace, local_name = split_qname(element.tag)
        node: dict[str, Any] = {"__tag__": local_name}
        if namespace:
            node["__ns__"] = namespace

        if element.attrib:
            node["__attrs__"] = {key: value for key, value in sorted(element.attrib.items())}

        text = (element.text or "").strip()
        if text:
            node["__text__"] = text

        children = list(element)
        if not children:
            return node

        grouped: dict[str, list[Any]] = {}
        for child in children:
            child_ns, child_name = split_qname(child.tag)
            group_key = f"{child_ns or ''}:{child_name}"
            grouped.setdefault(group_key, []).append(self._element_to_data(child))

        for group_key, values in grouped.items():
            _, child_name = group_key.split(":", 1)
            node[child_name] = values[0] if len(values) == 1 else values

        return node

    def _compare_nodes(self, left: Any, right: Any, path: str) -> None:
        if type(left) != type(right):
            self.diff_items.append(DiffItem("tipo", path, self._preview(left), self._preview(right)))
            return

        if isinstance(left, dict):
            left_keys = set(left.keys())
            right_keys = set(right.keys())
            for key in sorted(left_keys - right_keys):
                self.diff_items.append(DiffItem("eliminado", f"{path}.{key}", self._preview(left[key]), ""))
            for key in sorted(right_keys - left_keys):
                self.diff_items.append(DiffItem("agregado", f"{path}.{key}", "", self._preview(right[key])))
            for key in sorted(left_keys & right_keys):
                self._compare_nodes(left[key], right[key], f"{path}.{key}")
            return

        if isinstance(left, list):
            max_len = max(len(left), len(right))
            for index in range(max_len):
                item_path = f"{path}[{index}]"
                if index >= len(left):
                    self.diff_items.append(DiffItem("agregado", item_path, "", self._preview(right[index])))
                elif index >= len(right):
                    self.diff_items.append(DiffItem("eliminado", item_path, self._preview(left[index]), ""))
                else:
                    self._compare_nodes(left[index], right[index], item_path)
            return

        if left != right:
            self.diff_items.append(DiffItem("cambio", path, self._preview(left), self._preview(right)))

    def _preview(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            text = json.dumps(value, ensure_ascii=False)
        else:
            text = str(value)
        return text if len(text) <= 120 else text[:117] + "..."


def main() -> None:
    get_config_path().parent.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    XMLDiffStudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
