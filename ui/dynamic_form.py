"""Dynamic scrollable Tkinter form — thème clair professionnel.

Comportement spécial pour nb_cas_remblai :
  Quand l'utilisateur change nb_cas_remblai (N), les champs
  hauteurs_remblai et epaisseurs_cadre affichent automatiquement
  N lignes de saisie individuelles (une par cas).
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List

_BG    = "#FFFFFF"   # fond panneau
_BG2   = "#F8FAFC"   # fond input / section
_FG    = "#0F172A"   # texte principal
_DIM   = "#334155"   # texte label
_MUT   = "#64748B"   # texte muet / en-tête section
_ACC   = "#2563EB"   # accent
_BRD   = "#E2E8F0"   # bordure
_SEC   = "#F1F5F9"   # fond titre section


class DynamicForm(ttk.Frame):
    """Renders form sections and validates user inputs dynamically."""

    def __init__(self, master: tk.Misc, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(style="TFrame")
        self._vars: Dict[str, tk.Variable] = {}
        self._fields: List[Dict[str, Any]] = []
        self._choice_maps: Dict[str, Dict[str, Any]] = {}

        self._cas_frames: Dict[str, tk.Frame] = {}
        self._cas_vars: Dict[str, List[tk.StringVar]] = {}

        self._canvas = tk.Canvas(
            self, highlightthickness=0, bg=_BG, bd=0)
        self._scrollbar = ttk.Scrollbar(
            self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=_BG)

        self._inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")))

        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._inner, anchor=tk.NW)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        # Scroll molette — lié au canvas ET propagé depuis tous les enfants
        def _on_wheel(event):
            self._canvas.yview_scroll(-1 * (event.delta // 120), "units")

        self._canvas.bind("<MouseWheel>", _on_wheel)
        self._canvas.bind("<Enter>",
            lambda e: self._canvas.bind_all("<MouseWheel>", _on_wheel))
        self._canvas.bind("<Leave>",
            lambda e: self._canvas.unbind_all("<MouseWheel>"))

        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_canvas_resize(self, event: tk.Event) -> None:
        self._canvas.itemconfigure(
            self._canvas_window, width=event.width)

    def _get_nb_cas(self) -> int:
        try:
            return max(1, min(21, int(
                self._vars["nb_cas_remblai"].get())))
        except Exception:
            return 1

    def _rebuild_cas_rows(self, field_id: str,
                          n: int, default_val: float) -> None:
        frame = self._cas_frames.get(field_id)
        if frame is None:
            return

        existing = []
        if field_id in self._cas_vars:
            existing = [v.get() for v in self._cas_vars[field_id]]

        for child in frame.winfo_children():
            child.destroy()

        new_vars: List[tk.StringVar] = []
        for i in range(n):
            prev = existing[i] if i < len(existing) else str(default_val)
            var  = tk.StringVar(value=prev)
            new_vars.append(var)

            row = tk.Frame(frame, bg=_BG)
            row.pack(fill=tk.X, pady=1, padx=(2, 0))

            tk.Label(
                row,
                text=f"Cas {i + 1}",
                width=6, anchor=tk.W,
                bg=_BG, fg=_MUT,
                font=("Segoe UI", 8),
            ).pack(side=tk.LEFT)

            tk.Entry(
                row, textvariable=var, width=10,
                bg=_BG2, fg=_FG,
                relief=tk.SOLID, bd=1,
                font=("Segoe UI", 9),
                highlightthickness=0,
            ).pack(side=tk.LEFT, padx=(0, 4), ipady=3)

        self._cas_vars[field_id] = new_vars
        self._inner.update_idletasks()
        self._canvas.configure(
            scrollregion=self._canvas.bbox("all"))

    def _on_nb_cas_change(self, *_) -> None:
        n = self._get_nb_cas()
        self._rebuild_cas_rows("hauteurs_remblai",  n, 1.0)
        self._rebuild_cas_rows("epaisseurs_cadre",  n, 0.20)

    def build(self, sections: List[Dict[str, Any]]) -> None:
        for child in self._inner.winfo_children():
            child.destroy()
        self._vars.clear()
        self._fields.clear()
        self._choice_maps.clear()
        self._cas_frames.clear()
        self._cas_vars.clear()

        for sec in sections:
            # ── En-tête de section ────────────────────────────────────────
            sec_hdr = tk.Frame(self._inner, bg=_SEC)
            sec_hdr.pack(fill=tk.X, pady=(10, 0))

            tk.Label(
                sec_hdr,
                text=sec["title"].upper(),
                bg=_SEC, fg=_MUT,
                font=("Segoe UI", 8, "bold"),
                anchor=tk.W,
            ).pack(side=tk.LEFT, padx=10, pady=5)

            # ── Corps de section ──────────────────────────────────────────
            sec_body = tk.Frame(self._inner, bg=_BG)
            sec_body.pack(fill=tk.X, padx=8, pady=(2, 0))
            sec_body.columnconfigure(1, weight=1)

            row_idx = 0
            for fld in sec.get("fields", []):
                self._fields.append(fld)
                fid     = fld["id"]
                ftype   = fld.get("type", "string")
                default = fld.get("default", "")

                # ── float_list dynamique ──────────────────────────────────
                if ftype == "float_list" and fid in (
                        "hauteurs_remblai", "epaisseurs_cadre"):
                    tk.Label(
                        sec_body,
                        text=fld["label"],
                        bg=_BG, fg=_DIM,
                        font=("Segoe UI", 8),
                        wraplength=240, justify=tk.LEFT, anchor=tk.W,
                    ).grid(row=row_idx, column=0, columnspan=2,
                           sticky=tk.W, pady=(4, 1))
                    row_idx += 1

                    frame = tk.Frame(sec_body, bg=_BG)
                    frame.grid(row=row_idx, column=0,
                               columnspan=2, sticky=tk.EW, pady=(0, 4))
                    self._cas_frames[fid] = frame

                    dv = 1.0 if fid == "hauteurs_remblai" else 0.20
                    self._rebuild_cas_rows(fid, 1, dv)
                    row_idx += 1
                    continue

                # ── Champ normal ─────────────────────────────────────────
                tk.Label(
                    sec_body,
                    text=fld["label"],
                    bg=_BG, fg=_DIM,
                    font=("Segoe UI", 8),
                    wraplength=180, justify=tk.LEFT, anchor=tk.W,
                ).grid(row=row_idx, column=0,
                       sticky=tk.W, padx=(0, 8), pady=2)

                if ftype == "choice":
                    choices = fld.get("choices", [])
                    display = [c["label"] for c in choices]
                    self._choice_maps[fid] = {
                        c["label"]: c["value"] for c in choices}
                    def_lbl = next(
                        (c["label"] for c in choices
                         if c["value"] == default),
                        display[0] if display else "")
                    var    = tk.StringVar(value=def_lbl)
                    widget = ttk.Combobox(
                        sec_body, textvariable=var,
                        values=display, state="readonly",
                        font=("Segoe UI", 9))
                else:
                    var    = tk.StringVar(value=str(default))
                    widget = tk.Entry(
                        sec_body, textvariable=var,
                        bg=_BG2, fg=_FG,
                        relief=tk.SOLID, bd=1,
                        font=("Segoe UI", 9),
                        highlightthickness=0)

                widget.grid(row=row_idx, column=1,
                            sticky=tk.EW, pady=2, ipady=3)
                self._vars[fid] = var

                if fid == "nb_cas_remblai":
                    var.trace_add("write", self._on_nb_cas_change)

                row_idx += 1

        # Séparateur bas
        tk.Frame(self._inner, bg=_BRD, height=1).pack(
            fill=tk.X, pady=(10, 0))

        self._on_nb_cas_change()

    def collect_values(self) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {}
        nb_cas = self._get_nb_cas()

        for fld in self._fields:
            fid   = fld["id"]
            label = fld["label"]
            ftype = fld.get("type", "string")

            # ── Listes dynamiques ─────────────────────────────────────────
            if ftype == "float_list" and fid in (
                    "hauteurs_remblai", "epaisseurs_cadre"):
                values = []
                for i, var in enumerate(
                        self._cas_vars.get(fid, [])):
                    raw = var.get().strip().replace(",", ".")
                    if not raw:
                        raise ValueError(
                            f"'{label}' — Cas {i+1} est vide.")
                    try:
                        v = float(raw)
                    except ValueError:
                        raise ValueError(
                            f"'{label}' — Cas {i+1} : '{raw}' invalide.")
                    if fid == "hauteurs_remblai" and v < 0:
                        raise ValueError(
                            f"'{label}' — Cas {i+1} : hauteur >= 0.")
                    if fid == "epaisseurs_cadre" and v <= 0:
                        raise ValueError(
                            f"'{label}' — Cas {i+1} : épaisseur > 0.")
                    values.append(v)
                if len(values) != nb_cas:
                    raise ValueError(
                        f"'{label}' : attendu {nb_cas}, obtenu {len(values)}.")
                parsed[fid] = values
                continue

            # ── Champs normaux ────────────────────────────────────────────
            raw = self._vars[fid].get().strip()
            if fld.get("required") and raw == "":
                raise ValueError(f"'{label}' est obligatoire.")

            if ftype == "choice":
                parsed[fid] = self._choice_maps[fid][raw]
            elif ftype == "int":
                val = int(raw)
                if "min" in fld and val < fld["min"]:
                    raise ValueError(f"'{label}' >= {fld['min']}.")
                if "max" in fld and val > fld["max"]:
                    raise ValueError(f"'{label}' <= {fld['max']}.")
                parsed[fid] = val
            elif ftype == "float":
                val = float(raw.replace(",", "."))
                if "min" in fld and val < fld["min"]:
                    raise ValueError(f"'{label}' >= {fld['min']}.")
                parsed[fid] = val
            elif ftype == "float_list":
                items = [float(x.strip().replace(",", "."))
                         for x in raw.split(",") if x.strip()]
                if not items:
                    raise ValueError(
                        f"'{label}' doit contenir au moins une valeur.")
                parsed[fid] = items
            else:
                ml = fld.get("max_length")
                if ml and len(raw) > ml:
                    raise ValueError(
                        f"'{label}' max {ml} caractères.")
                parsed[fid] = raw

        return parsed
