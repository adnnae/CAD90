"""CAD90Pro — Interface principale, thème clair professionnel."""

from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

from core.generator import DataFileGenerator
from core.models import ExecutionResult, ParameterSchema, StructureType
from core.parser import ParsedResults, parse_engine_report
from core.bq_export import HAS_OPENPYXL, build_bq_params, export_bq_excel
from core.pdf_export import export_pdf_report
from core.results import format_execution_summary, read_text_with_fallback
from core.runner import EngineRunner
from ui.dynamic_form import DynamicForm
from ui.sketch import DalotSketchCanvas

# ── Palette claire ────────────────────────────────────────────────────────────
C = {
    "bg":           "#F8FAFC",   # fond général
    "header_bg":    "#1E3A5F",   # header bleu marine
    "header_fg":    "#FFFFFF",
    "header_sub":   "#93C5FD",   # sous-titre header
    "panel":        "#FFFFFF",   # cartes / panneaux
    "panel_hdr":    "#1E3A5F",   # en-tête panneau
    "panel_hdr_fg": "#FFFFFF",
    "section_bg":   "#F1F5F9",   # fond section titre
    "section_fg":   "#1E3A5F",   # texte section titre
    "border":       "#E2E8F0",   # bordures légères
    "border2":      "#CBD5E1",   # bordures plus visibles
    "accent":       "#2563EB",   # bleu principal
    "accent_hover": "#1D4ED8",
    "accent_light": "#EFF6FF",   # fond bleu très clair
    "accent_lt":    "#93C5FD",   # bleu clair texte header
    "text":         "#0F172A",   # texte principal
    "text2":        "#334155",   # texte secondaire
    "text3":        "#64748B",   # texte muet
    "input_bg":     "#FFFFFF",
    "input_border": "#CBD5E1",
    "row_odd":      "#FFFFFF",
    "row_even":     "#F8FAFC",
    "row_sel":      "#DBEAFE",
    "row_sel_fg":   "#1E3A8A",
    "th_bg":        "#1E3A5F",
    "th_fg":        "#FFFFFF",
    "success":      "#16A34A",
    "warning":      "#D97706",
    "danger":       "#DC2626",
    "pill_active":  "#2563EB",
    "pill_active_fg":"#FFFFFF",
    "pill_idle":    "#E2E8F0",
    "pill_idle_fg": "#334155",
    "btn_ghost_bg": "#FFFFFF",
    "btn_ghost_fg": "#334155",
    "btn_ghost_bd": "#CBD5E1",
    "status_bar":   "#1E3A5F",
    "status_fg":    "#FFFFFF",
}


class DalotApp(tk.Tk):

    def __init__(self, app_dir: Path, default_bins_dir: Path,
                 work_base_dir: Optional[Path] = None):
        super().__init__()
        self.app_dir = app_dir
        self.title("CAD90Pro — Ponts Cadres en Béton Armé")
        self.geometry("1300x780")
        self.minsize(1100, 640)
        self.configure(bg=C["bg"])

        schema_path = app_dir / "config" / "parameters.json"
        self.schema = ParameterSchema(schema_path)
        self.generator = DataFileGenerator()

        self._bins_bundled: bool = (
            default_bins_dir / "CASIMPLE_WIN64.EXE").is_file()

        base_work = work_base_dir or app_dir
        self.var_type     = tk.StringVar(value=StructureType.SIMPLE.value)
        self.var_bins_dir = tk.StringVar(value=str(default_bins_dir))
        self.var_work_dir = tk.StringVar(
            value=str(base_work / "runs" / "latest"))
        self.var_status   = tk.StringVar(value="Prêt")

        self._generated_files: List[Path] = []
        self._last_result: Optional[ExecutionResult] = None
        self._last_parsed: Optional[ParsedResults]  = None
        self._last_params: Dict[str, Any] = {}

        self._apply_theme()
        self._build_ui()
        self._on_type_changed()

    # ── Thème ttk ─────────────────────────────────────────────────────────────
    def _apply_theme(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure(".",
                    background=C["panel"], foreground=C["text"],
                    font=("Segoe UI", 9), borderwidth=0, relief="flat")
        s.configure("TFrame",      background=C["panel"])
        s.configure("Bg.TFrame",   background=C["bg"])
        s.configure("TLabel",      background=C["panel"], foreground=C["text"])
        s.configure("TLabelframe",
                    background=C["panel"], bordercolor=C["border2"],
                    relief="solid", borderwidth=1)
        s.configure("TLabelframe.Label",
                    background=C["panel"], foreground=C["section_fg"],
                    font=("Segoe UI", 9, "bold"))

        s.configure("TEntry",
                    fieldbackground=C["input_bg"], background=C["input_bg"],
                    foreground=C["text"], insertcolor=C["text"],
                    borderwidth=1, relief="flat", padding=(6, 4))
        s.map("TEntry",
              bordercolor=[("focus", C["accent"]), ("!focus", C["input_border"])])

        s.configure("TCombobox",
                    fieldbackground=C["input_bg"], background=C["panel"],
                    foreground=C["text"], arrowcolor=C["text2"],
                    borderwidth=1, relief="flat", padding=(4, 3))
        s.map("TCombobox", fieldbackground=[("readonly", C["input_bg"])])

        s.configure("Primary.TButton",
                    background=C["accent"], foreground="#FFFFFF",
                    font=("Segoe UI", 10, "bold"),
                    padding=(20, 9), borderwidth=0)
        s.map("Primary.TButton",
              background=[("active", C["accent_hover"]),
                          ("disabled", C["border2"])])

        s.configure("Ghost.TButton",
                    background=C["btn_ghost_bg"],
                    foreground=C["btn_ghost_fg"],
                    font=("Segoe UI", 9),
                    padding=(11, 6), borderwidth=1)
        s.map("Ghost.TButton",
              background=[("active", C["accent_light"])],
              foreground=[("active", C["accent"])],
              bordercolor=[("active", C["accent"]),
                           ("!active", C["btn_ghost_bd"])])

        # Treeview
        s.configure("Treeview",
                    background=C["row_odd"],
                    fieldbackground=C["row_odd"],
                    foreground=C["text"],
                    rowheight=26,
                    font=("Segoe UI", 9),
                    borderwidth=0)
        s.configure("Treeview.Heading",
                    background=C["th_bg"],
                    foreground=C["th_fg"],
                    font=("Segoe UI", 9, "bold"),
                    relief="flat", padding=(6, 7))
        s.map("Treeview",
              background=[("selected", C["row_sel"])],
              foreground=[("selected", C["row_sel_fg"])])
        s.map("Treeview.Heading",
              background=[("active", C["accent"])])

        # Notebook
        s.configure("TNotebook",     background=C["bg"], borderwidth=0)
        s.configure("TNotebook.Tab",
                    background=C["border"], foreground=C["text3"],
                    padding=(14, 7), font=("Segoe UI", 9))
        s.map("TNotebook.Tab",
              background=[("selected", C["panel"])],
              foreground=[("selected", C["accent"])],
              font=[("selected", ("Segoe UI", 9, "bold"))])

        s.configure("TScrollbar",
                    background=C["border"], troughcolor=C["bg"],
                    arrowcolor=C["text3"], borderwidth=0)
        s.map("TScrollbar", background=[("active", C["border2"])])

        s.configure("TProgressbar",
                    troughcolor=C["border"],
                    background=C["accent"], borderwidth=0)

    # ── Construction UI ───────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        self._build_header()
        self._build_status_bar()
        self._build_body()

    def _build_header(self) -> None:
        # ── Bande accent 3px ─────────────────────────────────────────────
        tk.Frame(self, bg=C["accent"], height=3).pack(fill=tk.X)

        hdr = tk.Frame(self, bg=C["header_bg"], height=66)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        # ══════════════════════════════════════════════════════════════════
        # LOGO
        # ══════════════════════════════════════════════════════════════════
        logo_zone = tk.Frame(hdr, bg=C["header_bg"])
        logo_zone.pack(side=tk.LEFT, padx=(18, 0))

        name_row = tk.Frame(logo_zone, bg=C["header_bg"])
        name_row.pack(anchor=tk.W, pady=(12, 0))

        tk.Label(name_row, text="CAD90",
                 bg=C["header_bg"], fg="#FFFFFF",
                 font=("Segoe UI", 17, "bold")).pack(side=tk.LEFT)
        tk.Label(name_row, text="Pro",
                 bg=C["header_bg"], fg=C["accent_lt"],
                 font=("Segoe UI", 17, "bold")).pack(side=tk.LEFT)

        badge = tk.Label(name_row, text="  v2  ",
                         bg=C["accent"], fg="#FFFFFF",
                         font=("Segoe UI", 7, "bold"))
        badge.pack(side=tk.LEFT, padx=(8, 0), pady=(6, 0))

        tk.Label(logo_zone,
                 text="Dimensionnement des Ponts Cadres en Béton Armé",
                 bg=C["header_bg"], fg="#5B8DB8",
                 font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(1, 0))

        # ══════════════════════════════════════════════════════════════════
        # ZONE CENTRALE : TYPE + PROJET
        # ══════════════════════════════════════════════════════════════════
        center = tk.Frame(hdr, bg=C["header_bg"])
        center.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(30, 20))

        # ── TYPE D'OUVRAGE ────────────────────────────────────────────────
        col_type = tk.Frame(center, bg=C["header_bg"])
        col_type.pack(side=tk.LEFT, pady=0)

        tk.Label(col_type, text="TYPE D'OUVRAGE",
                 bg=C["header_bg"], fg="#5B8DB8",
                 font=("Segoe UI", 7, "bold")).pack(
            anchor=tk.W, pady=(12, 5))

        pills = tk.Frame(col_type, bg="#162032",
                         highlightbackground="#2D5A8E",
                         highlightthickness=1)
        pills.pack(anchor=tk.W)

        self._pill_btns: Dict[str, tk.Button] = {}
        types_def = [
            (StructureType.SIMPLE, "Dalot Simple"),
            (StructureType.DOUBLE, "Dalot Double"),
            (StructureType.TRIPLE, "Dalot Triple"),
        ]
        for i, (st, lbl) in enumerate(types_def):
            is_active = (st == StructureType.SIMPLE)
            if i > 0:
                tk.Frame(pills, bg="#2D5A8E", width=1).pack(
                    side=tk.LEFT, fill=tk.Y, pady=3)
            b = tk.Button(
                pills,
                text=lbl,
                bg="#2563EB"  if is_active else "#162032",
                fg="#FFFFFF",
                font=("Segoe UI", 10, "bold"),
                relief=tk.FLAT, bd=0,
                padx=20, pady=8,
                cursor="hand2",
                activebackground="#1D4ED8",
                activeforeground="#FFFFFF",
                command=lambda s=st: self._select_type(s),
            )
            b.pack(side=tk.LEFT)
            self._pill_btns[st.value] = b

        # ── Séparateur ────────────────────────────────────────────────────
        tk.Frame(center, bg="#2D5A8E", width=1).pack(
            side=tk.LEFT, fill=tk.Y, padx=28, pady=10)

        # ── PROJET ────────────────────────────────────────────────────────
        col_proj = tk.Frame(center, bg=C["header_bg"])
        col_proj.pack(side=tk.LEFT, pady=0)

        tk.Label(col_proj, text="PROJET",
                 bg=C["header_bg"], fg="#5B8DB8",
                 font=("Segoe UI", 7, "bold")).pack(
            anchor=tk.W, pady=(12, 5))

        proj_btns = tk.Frame(col_proj, bg=C["header_bg"])
        proj_btns.pack(anchor=tk.W)

        for icon_char, lbl, cmd in [
            ("⊞", "Ouvrir",       self._on_open_project),
            ("⊟", "Enregistrer",  self._on_save_project),
        ]:
            b = tk.Button(
                proj_btns,
                text=f"{icon_char}   {lbl}",
                bg="#1E3352", fg="#BFDBFE",
                font=("Segoe UI", 9),
                relief=tk.FLAT, bd=0,
                padx=14, pady=7,
                cursor="hand2",
                activebackground="#2D5A8E",
                activeforeground="#FFFFFF",
                command=cmd,
                highlightbackground="#2D5A8E",
                highlightthickness=1,
            )
            b.pack(side=tk.LEFT, padx=(0, 6))

        # ══════════════════════════════════════════════════════════════════
        # BOUTON CALCULER (droite)
        # ══════════════════════════════════════════════════════════════════
        right_zone = tk.Frame(hdr, bg=C["header_bg"])
        right_zone.pack(side=tk.RIGHT, padx=(0, 18))

        self._btn_calc_main = tk.Button(
            right_zone,
            text="▶   Calculer",
            bg=C["accent"], fg="#FFFFFF",
            font=("Segoe UI", 11, "bold"),
            relief=tk.FLAT, bd=0,
            padx=24, pady=10,
            cursor="hand2",
            activebackground=C["accent_hover"],
            activeforeground="#FFFFFF",
            command=self._on_run,
        )
        self._btn_calc_main.pack(pady=14)

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self, bg=C["status_bar"], height=36)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)

        inner = tk.Frame(bar, bg=C["status_bar"])
        inner.pack(fill=tk.X, padx=12, pady=4)

        self._status_dot = tk.Label(
            inner, text="●", bg=C["status_bar"],
            fg=C["success"], font=("Segoe UI", 10))
        self._status_dot.pack(side=tk.LEFT, padx=(0, 6))

        tk.Label(inner, textvariable=self.var_status,
                 bg=C["status_bar"], fg=C["header_fg"],
                 font=("Segoe UI", 9)).pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(
            inner, mode="indeterminate", length=160)

        for lbl, cmd in [
            ("Générer données",   self._on_preview),
            ("Avant-métré Excel", self._on_export_bq),
            ("Exporter TXT",      self._on_export_txt),
            ("Exporter PDF",      self._on_export_pdf),
        ]:
            b = tk.Button(
                inner, text=lbl, command=cmd,
                bg="#2D5A8E", fg="#FFFFFF",
                font=("Segoe UI", 9),
                relief=tk.FLAT, bd=0,
                padx=12, pady=4,
                cursor="hand2",
                activebackground=C["accent"],
                activeforeground="#FFFFFF",
            )
            b.pack(side=tk.RIGHT, padx=(4, 0))

    def _build_body(self) -> None:
        # PanedWindow horizontal pour que chaque colonne soit redimensionnable
        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ── Colonne gauche : paramètres ───────────────────────────────────
        left_wrap = tk.Frame(body, bg=C["bg"])

        left_hdr = tk.Frame(left_wrap, bg=C["panel_hdr"], height=34)
        left_hdr.pack(fill=tk.X)
        left_hdr.pack_propagate(False)
        tk.Label(left_hdr, text="PARAMÈTRES DE L'OUVRAGE",
                 bg=C["panel_hdr"], fg=C["panel_hdr_fg"],
                 font=("Segoe UI", 9, "bold")).pack(
            side=tk.LEFT, padx=12, pady=7)

        left_body = tk.Frame(
            left_wrap, bg=C["panel"],
            highlightbackground=C["border2"], highlightthickness=1)
        left_body.pack(fill=tk.BOTH, expand=True)

        self.form = DynamicForm(left_body)
        self.form.pack(fill=tk.BOTH, expand=True)

        body.add(left_wrap, weight=2)

        # ── Colonne centre : croquis + efforts ───────────────────────────
        mid_wrap = tk.Frame(body, bg=C["bg"])

        mid_hdr = tk.Frame(mid_wrap, bg=C["panel_hdr"], height=34)
        mid_hdr.pack(fill=tk.X)
        mid_hdr.pack_propagate(False)
        tk.Label(mid_hdr, text="CROQUIS & MODÉLISATION",
                 bg=C["panel_hdr"], fg=C["panel_hdr_fg"],
                 font=("Segoe UI", 9, "bold")).pack(
            side=tk.LEFT, padx=12, pady=7)

        mid_body = tk.Frame(
            mid_wrap, bg=C["panel"],
            highlightbackground=C["border2"], highlightthickness=1)
        mid_body.pack(fill=tk.BOTH, expand=True)

        # Croquis (partie haute, 65% de la hauteur)
        sketch_frame = tk.Frame(mid_body, bg=C["panel"])
        sketch_frame.pack(fill=tk.BOTH, expand=True)
        self.sketch = DalotSketchCanvas(sketch_frame)
        self.sketch.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 0))

        # Séparateur
        tk.Frame(mid_body, bg=C["border2"], height=1).pack(
            fill=tk.X, padx=6, pady=4)

        # Bande des efforts clés (partie basse)
        self._efforts_frame = tk.Frame(mid_body, bg=C["panel"])
        self._efforts_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._build_efforts_strip(self._efforts_frame)

        body.add(mid_wrap, weight=3)

        # ── Colonne droite : résultats ────────────────────────────────────
        right_wrap = tk.Frame(body, bg=C["bg"])

        right_hdr = tk.Frame(right_wrap, bg=C["panel_hdr"], height=34)
        right_hdr.pack(fill=tk.X)
        right_hdr.pack_propagate(False)
        tk.Label(right_hdr, text="ANALYSE & RÉSULTATS",
                 bg=C["panel_hdr"], fg=C["panel_hdr_fg"],
                 font=("Segoe UI", 9, "bold")).pack(
            side=tk.LEFT, padx=12, pady=7)

        right_body = tk.Frame(
            right_wrap, bg=C["panel"],
            highlightbackground=C["border2"], highlightthickness=1)
        right_body.pack(fill=tk.BOTH, expand=True)

        self._build_results_pane(right_body)

        body.add(right_wrap, weight=3)

    def _build_efforts_strip(self, parent: tk.Frame) -> None:
        """Bande d'efforts clés sous le croquis — 4 cartes métriques."""
        self._metric_cards: Dict[str, tk.Label] = {}

        metrics_def = [
            ("Effort tranchant max (T)",     "Effort tranchant",  "T"),
            ("Moment transversal max (Tm/m)", "Moment trans. max", "Tm/m"),
            ("Moment transversal min (Tm/m)", "Moment trans. min", "Tm/m"),
            ("Pression max au sol (T/m²)",    "Pression au sol",   "T/m²"),
        ]

        for i, (key, short_lbl, unit) in enumerate(metrics_def):
            parent.columnconfigure(i, weight=1)
            card = tk.Frame(
                parent, bg=C["accent_light"],
                highlightbackground=C["border2"],
                highlightthickness=1)
            card.grid(row=0, column=i, sticky=tk.EW,
                      padx=(0 if i == 0 else 4, 0), pady=2)

            tk.Label(card, text=short_lbl,
                     bg=C["accent_light"], fg=C["text3"],
                     font=("Segoe UI", 7, "bold")).pack(
                anchor=tk.W, padx=8, pady=(4, 0))

            val_lbl = tk.Label(
                card, text="—",
                bg=C["accent_light"], fg=C["text"],
                font=("Segoe UI", 13, "bold"))
            val_lbl.pack(anchor=tk.CENTER, padx=8)

            tk.Label(card, text=unit,
                     bg=C["accent_light"], fg=C["text3"],
                     font=("Segoe UI", 7)).pack(
                anchor=tk.E, padx=8, pady=(0, 4))

            self._metric_cards[key] = val_lbl

    def _update_efforts_strip(self, metrics: Dict[str, str]) -> None:
        """Met à jour les valeurs dans les cartes de métriques."""
        for key, lbl in self._metric_cards.items():
            val = metrics.get(key, "—")
            lbl.configure(
                text=val if val else "—",
                fg=C["accent"] if val and val != "—" else C["text3"])

    # ── Résultats ─────────────────────────────────────────────────────────────
    def _build_results_pane(self, parent: tk.Widget) -> None:
        self.nb_results = ttk.Notebook(parent)
        self.nb_results.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        t1 = ttk.Frame(self.nb_results)
        self._build_moments_tab(t1)
        self.nb_results.add(t1, text="  Moments & Efforts  ")

        t2 = ttk.Frame(self.nb_results)
        self._build_rebar_tab(t2)
        self.nb_results.add(t2, text="  Ferraillage  ")

        t3 = ttk.Frame(self.nb_results, padding=4)
        sy3 = ttk.Scrollbar(t3, orient=tk.VERTICAL)
        sx3 = ttk.Scrollbar(t3, orient=tk.HORIZONTAL)
        self.txt_console = tk.Text(
            t3, wrap=tk.NONE,
            font=("Consolas", 9),
            bg=C["input_bg"], fg=C["text"],
            yscrollcommand=sy3.set, xscrollcommand=sx3.set,
            state=tk.DISABLED, relief=tk.FLAT, bd=0)
        sy3.config(command=self.txt_console.yview)
        sx3.config(command=self.txt_console.xview)
        sy3.pack(side=tk.RIGHT, fill=tk.Y)
        sx3.pack(side=tk.BOTTOM, fill=tk.X)
        self.txt_console.pack(fill=tk.BOTH, expand=True)
        self.nb_results.add(t3, text="  Rapport natif  ")

        t4 = ttk.Frame(self.nb_results, padding=4)
        self.txt_summary = tk.Text(
            t4, wrap=tk.WORD,
            bg=C["input_bg"], fg=C["text"],
            font=("Consolas", 9),
            state=tk.DISABLED, relief=tk.FLAT, bd=0)
        self.txt_summary.pack(fill=tk.BOTH, expand=True)
        self.nb_results.add(t4, text="  Résumé  ")

        t5 = ttk.Frame(self.nb_results, padding=4)
        self.lst_files = tk.Listbox(
            t5, height=4,
            bg=C["input_bg"], fg=C["text"],
            selectbackground=C["row_sel"],
            selectforeground=C["row_sel_fg"],
            font=("Consolas", 9),
            relief=tk.FLAT, bd=0)
        self.lst_files.pack(fill=tk.X, pady=(0, 6))
        self.lst_files.bind("<<ListboxSelect>>", self._on_file_selected)
        self.txt_file_preview = tk.Text(
            t5, wrap=tk.NONE,
            font=("Consolas", 9),
            bg=C["input_bg"], fg=C["text"],
            state=tk.DISABLED, relief=tk.FLAT, bd=0)
        self.txt_file_preview.pack(fill=tk.BOTH, expand=True)
        self.nb_results.add(t5, text="  Fichiers générés  ")

    def _build_moments_tab(self, parent: ttk.Frame) -> None:
        cols = ("zone", "extremum", "ch_perm", "ch_rout", "sch_remb", "combinaison")
        frame = tk.Frame(parent, bg=C["panel"])
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        sy = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        sx = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)

        self.tree_moments = ttk.Treeview(
            frame, columns=cols, show="headings",
            yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.config(command=self.tree_moments.yview)
        sx.config(command=self.tree_moments.xview)

        for cid, title, w, anc in [
            ("zone",        "Zone",         175, tk.W),
            ("extremum",    "Extremum",      82, tk.CENTER),
            ("ch_perm",     "Ch. Perm.",     80, tk.E),
            ("ch_rout",     "Ch. Rout.",     80, tk.E),
            ("sch_remb",    "Sch. Remb.",    82, tk.E),
            ("combinaison", "Combinaison",   88, tk.E),
        ]:
            self.tree_moments.heading(cid, text=title, anchor=anc)
            self.tree_moments.column(
                cid, width=w, anchor=anc, minwidth=50, stretch=True)

        self.tree_moments.tag_configure(
            "odd",  background="#FFFFFF", foreground=C["text"])
        self.tree_moments.tag_configure(
            "even", background="#F8FAFC", foreground=C["text"])

        sy.pack(side=tk.RIGHT,  fill=tk.Y)
        sx.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree_moments.pack(fill=tk.BOTH, expand=True)

        # Métriques scalaires
        self.var_metrics = tk.StringVar(
            value="Lancez un calcul pour afficher les efforts.")
        tk.Label(
            parent, textvariable=self.var_metrics,
            bg=C["panel"], fg=C["text2"],
            font=("Segoe UI", 9),
            wraplength=440, justify=tk.LEFT,
            anchor=tk.W,
        ).pack(fill=tk.X, padx=6, pady=(4, 2))

    def _build_rebar_tab(self, parent: ttk.Frame) -> None:
        cols = ("acier", "sec", "d", "ec", "longueur", "nombre")
        frame = tk.Frame(parent, bg=C["panel"])
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        sy = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        sx = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)

        self.tree_rebar = ttk.Treeview(
            frame, columns=cols, show="headings",
            yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.config(command=self.tree_rebar.yview)
        sx.config(command=self.tree_rebar.xview)

        for cid, title, w, anc in [
            ("acier",    "Acier / Nature",  130, tk.W),
            ("sec",      "Section",          82, tk.E),
            ("d",        "Diamètre",         82, tk.E),
            ("ec",       "Espacement",       88, tk.E),
            ("longueur", "Longueur (m)",     90, tk.E),
            ("nombre",   "Nombre",           70, tk.E),
        ]:
            self.tree_rebar.heading(cid, text=title, anchor=anc)
            self.tree_rebar.column(
                cid, width=w, anchor=anc, minwidth=50, stretch=True)

        self.tree_rebar.tag_configure(
            "odd",  background="#FFFFFF", foreground=C["text"])
        self.tree_rebar.tag_configure(
            "even", background="#F8FAFC", foreground=C["text"])

        sy.pack(side=tk.RIGHT,  fill=tk.Y)
        sx.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree_rebar.pack(fill=tk.BOTH, expand=True)

    # ── Sélecteur type ────────────────────────────────────────────────────────
    def _select_type(self, st: StructureType) -> None:
        self.var_type.set(st.value)
        for val, btn in self._pill_btns.items():
            active = val == st.value
            btn.configure(
                bg="#2563EB" if active else "#162032",
                fg="#FFFFFF",
                font=("Segoe UI", 10, "bold"),
            )
        self._on_type_changed()

    def _on_type_changed(self) -> None:
        st = StructureType(self.var_type.get())
        self.form.build(self.schema.sections_for(st))
        try:
            params = self.form.collect_values()
            self.sketch.update_sketch(st, params, self._last_parsed)
        except Exception:
            self.sketch.update_sketch(st, {}, self._last_parsed)

    # ── Navigation ───────────────────────────────────────────────────────────
    def _browse_bins(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.var_bins_dir.get())
        if chosen:
            self.var_bins_dir.set(chosen)

    def _browse_work(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.var_work_dir.get())
        if chosen:
            self.var_work_dir.set(chosen)

    # ── Projet : Ouvrir / Enregistrer ────────────────────────────────────────
    def _on_save_project(self) -> None:
        """Sérialise le type d'ouvrage + tous les paramètres du formulaire en JSON."""
        try:
            params = self.form.collect_values()
        except ValueError as exc:
            messagebox.showerror("Données incomplètes", str(exc))
            return

        import json
        project = {
            "version":        "1.0",
            "structure_type": self.var_type.get(),
            "params":         params,
        }

        nom = params.get("nom_fichier", "DALOT01")
        path = filedialog.asksaveasfilename(
            defaultextension=".dalot",
            filetypes=[
                ("Projet CAD90Pro", "*.dalot"),
                ("Fichier JSON",    "*.json"),
            ],
            initialfile=f"{nom}.dalot",
            title="Enregistrer le projet",
        )
        if not path:
            return

        try:
            Path(path).write_text(
                json.dumps(project, ensure_ascii=False, indent=2),
                encoding="utf-8")
            self.var_status.set(
                f"Projet enregistré : {Path(path).name}")
        except Exception as exc:
            messagebox.showerror("Erreur d'enregistrement", str(exc))

    def _on_open_project(self) -> None:
        """Charge un projet .dalot et recharge le formulaire avec ses données."""
        import json

        path = filedialog.askopenfilename(
            defaultextension=".dalot",
            filetypes=[
                ("Projet CAD90Pro", "*.dalot"),
                ("Fichier JSON",    "*.json"),
            ],
            title="Ouvrir un projet",
        )
        if not path:
            return

        try:
            data = json.loads(
                Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            messagebox.showerror("Erreur d'ouverture", str(exc))
            return

        # Vérifier la structure minimale
        if "params" not in data:
            messagebox.showerror(
                "Fichier invalide",
                "Ce fichier ne contient pas de données CAD90Pro valides.")
            return

        # 1. Sélectionner le type d'ouvrage
        stype_val = data.get("structure_type",
                              StructureType.SIMPLE.value)
        try:
            st = StructureType(stype_val)
        except ValueError:
            st = StructureType.SIMPLE

        # Mettre à jour les pills sans déclencher de rebuild prématuré
        self.var_type.set(st.value)
        for val, btn in self._pill_btns.items():
            active = val == st.value
            btn.configure(
                bg=C["accent"] if active else "#253F60",
                fg="#FFFFFF"   if active else "#93C5FD",
            )

        # 2. Reconstruire le formulaire pour ce type
        self.form.build(self.schema.sections_for(st))

        # 3. Injecter les valeurs dans les champs
        params = data["params"]
        self._inject_params_into_form(params)

        # 4. Mettre à jour le croquis
        try:
            vals = self.form.collect_values()
            self._last_params = vals
            self.sketch.update_sketch(st, vals, None)
        except Exception:
            pass

        self.var_status.set(
            f"Projet ouvert : {Path(path).name}")

    def _inject_params_into_form(self, params: Dict[str, Any]) -> None:
        """Injecte les valeurs d'un dict de params dans les widgets du formulaire."""
        # Accéder aux variables internes du formulaire
        fvars   = self.form._vars
        cmaps   = self.form._choice_maps
        cas_vars = self.form._cas_vars

        for field in self.form._fields:
            fid   = field["id"]
            ftype = field.get("type", "string")

            if fid not in params:
                continue

            val = params[fid]

            # Listes dynamiques (hauteurs_remblai, epaisseurs_cadre)
            if ftype == "float_list" and fid in cas_vars:
                items = val if isinstance(val, list) else [val]
                # S'assurer que le nombre de cas correspond
                nb_cas = len(items)
                try:
                    self.form._vars["nb_cas_remblai"].set(str(nb_cas))
                except Exception:
                    pass
                self.form._rebuild_cas_rows(
                    fid, nb_cas,
                    1.0 if fid == "hauteurs_remblai" else 0.20)
                for i, v in enumerate(items):
                    if i < len(self.form._cas_vars.get(fid, [])):
                        self.form._cas_vars[fid][i].set(str(v))
                continue

            if fid not in fvars:
                continue

            # Choice : retrouver le label correspondant à la valeur
            if ftype == "choice" and fid in cmaps:
                rev = {v: k for k, v in cmaps[fid].items()}
                label = rev.get(val)
                if label:
                    fvars[fid].set(label)
            else:
                fvars[fid].set(str(val))

    # ── Helpers UI ───────────────────────────────────────────────────────────
    def _set_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)
        widget.configure(state=tk.DISABLED)

    def _set_waiting(self, active: bool, message: str) -> None:
        self.var_status.set(message)
        self._status_dot.configure(
            fg=C["warning"] if active else C["success"])
        self._btn_calc_main.configure(
            state=tk.DISABLED if active else tk.NORMAL,
            bg=C["border2"] if active else C["accent"],
            text="⏳  Calcul…" if active else "▶   Calculer",
        )
        if active:
            self.progress.pack(side=tk.LEFT, padx=(8, 0), pady=4)
            self.progress.start(10)
            self.configure(cursor="watch")
        else:
            self.progress.stop()
            self.progress.pack_forget()
            self.configure(cursor="")

    # ── Actions ──────────────────────────────────────────────────────────────
    def _on_preview(self) -> None:
        st = StructureType(self.var_type.get())
        try:
            params = self.form.collect_values()
            self._last_params = params
            out_file = self.generator.generate(
                st, params, Path(self.var_work_dir.get()))
            self.var_status.set(f"Fichier généré : {out_file.name}")
            self._set_text(self.txt_file_preview,
                           read_text_with_fallback(out_file))
            self._refresh_files([out_file])
            self.sketch.update_sketch(st, params, self._last_parsed)
            self.nb_results.select(4)
        except Exception as exc:
            messagebox.showerror("Erreur de saisie", str(exc))

    def _on_run(self) -> None:
        st = StructureType(self.var_type.get())
        try:
            params = self.form.collect_values()
            self._last_params = params
        except ValueError as exc:
            messagebox.showerror("Erreur de saisie", str(exc))
            return
        work_dir = Path(self.var_work_dir.get())
        try:
            data_file = self.generator.generate(st, params, work_dir)
        except Exception as exc:
            messagebox.showerror("Erreur de génération", str(exc))
            return
        self.sketch.update_sketch(st, params, None)
        self._set_waiting(
            True,
            f"Calcul en cours ({st.engine_filename}) — veuillez patienter…")
        bins_dir = Path(self.var_bins_dir.get())

        def _worker() -> None:
            runner = EngineRunner(bins_dir)
            res: ExecutionResult = runner.run_engine(st, data_file, work_dir, params=params)
            self.after(0, lambda: self._on_run_finished(res, st, params))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_run_finished(self, res: ExecutionResult,
                          st: StructureType,
                          params: Dict[str, Any]) -> None:
        self._set_waiting(
            False,
            "Calcul terminé avec succès" if res.success
            else "Erreur lors du calcul")
        self._status_dot.configure(
            fg=C["success"] if res.success else C["danger"])
        self._last_result = res
        self._last_parsed = parse_engine_report(res.stdout or "")
        self._display_result(res, st, params, self._last_parsed)

    def _display_result(self, res: ExecutionResult, st: StructureType,
                         params: Dict[str, Any],
                         parsed: ParsedResults) -> None:
        self._set_text(self.txt_summary, format_execution_summary(res))
        self._set_text(self.txt_console,
                       (res.stdout or "").strip() or "(Aucune sortie)")
        self._refresh_files(res.generated_files)
        self.sketch.update_sketch(st, params, parsed)
        self._update_efforts_strip(parsed.metrics)

        for item in self.tree_moments.get_children():
            self.tree_moments.delete(item)
        for i, m in enumerate(parsed.moments):
            tag = "odd" if i % 2 else "even"
            self.tree_moments.insert("", tk.END, tags=(tag,),
                values=(m.zone, m.extremum, m.ch_perm,
                        m.ch_rout, m.sch_remb, m.combinaison))

        if parsed.metrics:
            self.var_metrics.set(
                "  |  ".join(
                    f"{k}: {v}" for k, v in parsed.metrics.items()))
        elif parsed.warnings:
            self.var_metrics.set(parsed.warnings[0])
        else:
            self.var_metrics.set(
                "Consultez l'onglet Rapport natif.")

        for item in self.tree_rebar.get_children():
            self.tree_rebar.delete(item)
        for i, r in enumerate(parsed.armatures):
            tag = "odd" if i % 2 else "even"
            self.tree_rebar.insert("", tk.END, tags=(tag,),
                values=(f"Acier {r.acier}", r.sec, r.d,
                        r.ec, r.longueur, r.nombre))
        offset = len(parsed.armatures)
        for i, e in enumerate(parsed.etriers):
            tag = "odd" if (i + offset) % 2 else "even"
            self.tree_rebar.insert("", tk.END, tags=(tag,),
                values=(e.nature, e.sec, e.d,
                        f"{e.ecl}/{e.ect}", e.longueur, e.nombre))

        self.nb_results.select(0)

    # ── Exports ──────────────────────────────────────────────────────────────
    def _on_export_txt(self) -> None:
        if not self._last_result or not self._last_result.stdout:
            messagebox.showinfo("Export TXT",
                                "Veuillez d'abord lancer un calcul.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Fichier texte", "*.txt")],
            initialfile=(
                f"{self._last_params.get('nom_fichier','DALOT')}_rapport.txt"),
        )
        if path:
            Path(path).write_text(
                self._last_result.stdout, encoding="utf-8")
            self.var_status.set(
                f"Rapport TXT exporté : {Path(path).name}")

    def _on_export_pdf(self) -> None:
        if not self._last_result or not self._last_parsed:
            messagebox.showinfo("Export PDF",
                                "Veuillez d'abord lancer un calcul.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("Document PDF", "*.pdf")],
            initialfile=(
                f"{self._last_params.get('nom_fichier','DALOT')}_note_calcul.pdf"),
        )
        if path:
            st = StructureType(self.var_type.get())
            export_pdf_report(
                Path(path), st, self._last_params,
                self._last_parsed, self._last_result.stdout or "")
            self.var_status.set(f"PDF exporté : {Path(path).name}")

    def _on_export_bq(self) -> None:
        if not HAS_OPENPYXL:
            messagebox.showerror("Module manquant", "openpyxl non installé.")
            return
        if not self._last_parsed:
            messagebox.showinfo("Export BQ",
                                "Lancez d'abord un calcul.")
            return
        nom  = self._last_params.get("nom_fichier", "DALOT")
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Classeur Excel", "*.xlsx")],
            initialfile=nom + "_avant_metre.xlsx",
        )
        if not path:
            return
        try:
            stype     = StructureType(self.var_type.get())
            armatures = [
                {
                    "acier_num":  int(r.acier),
                    "acier":      "Acier " + str(r.acier),
                    "diametre":   r.d,
                    "section":    r.sec,
                    "espacement": r.ec,
                    "longueur":   r.longueur,
                    "nombre":     r.nombre,
                }
                for r in self._last_parsed.armatures
            ]
            etriers = [
                {
                    "acier_num":  0,
                    "acier":      e.nature,
                    "diametre":   e.d,
                    "section":    e.sec,
                    "espacement": e.ecl,
                    "longueur":   e.longueur,
                    "nombre":     e.nombre,
                }
                for e in self._last_parsed.etriers
            ]
            bq_params = build_bq_params(
                self._last_params,
                parsed_metrics=(
                    self._last_parsed.metrics if self._last_parsed else {}),
            )
            export_bq_excel(
                path, stype.value, bq_params, armatures, etriers)
            self.var_status.set(
                f"Avant-métré Excel exporté : {Path(path).name}")
            messagebox.showinfo(
                "Export réussi",
                f"Avant-métré enregistré :\n{path}")
        except Exception as exc:
            messagebox.showerror("Erreur Export BQ", str(exc))

    def _refresh_files(self, files: List[Path]) -> None:
        self._generated_files = files
        self.lst_files.delete(0, tk.END)
        for f in files:
            self.lst_files.insert(tk.END, f"  {f.name}")

    def _on_file_selected(self, _event: tk.Event) -> None:
        sel = self.lst_files.curselection()
        if not sel:
            return
        path = self._generated_files[sel[0]]
        if path.is_file():
            self._set_text(self.txt_file_preview,
                           read_text_with_fallback(path))
