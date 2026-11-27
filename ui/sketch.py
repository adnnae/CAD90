"""Croquis vectoriel dalot — thème clair professionnel."""

import tkinter as tk
from typing import Any, Dict, Optional

from core.models import StructureType
from core.parser import ParsedResults

_C = {
    "bg":       "#FFFFFF",
    "grid":     "#F1F5F9",
    "concrete": "#94A3B8",
    "inner":    "#F8FAFC",
    "remblai":  "#D4E6F1",
    "remblai_h":"#2980B9",
    "rebar":    "#DC2626",
    "stirrup":  "#2563EB",
    "dim":      "#64748B",
    "text":     "#334155",
    "accent":   "#2563EB",
    "outline":  "#1E3A5F",
    "legend_bg":"#F8FAFC",
}


class DalotSketchCanvas(tk.Canvas):

    def __init__(self, master: tk.Misc, **kwargs):
        super().__init__(
            master,
            bg=_C["bg"],
            highlightthickness=1,
            highlightbackground="#E2E8F0",
            **kwargs,
        )
        self._last_args: Optional[tuple] = None
        self.bind("<Configure>", lambda _e: self.redraw())

    def update_sketch(self, structure_type: StructureType,
                      params: Dict[str, Any],
                      parsed: Optional[ParsedResults] = None) -> None:
        self._last_args = (structure_type, params, parsed)
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        if not self._last_args:
            return
        st, params, parsed = self._last_args

        W = max(self.winfo_width(),  380)
        H = max(self.winfo_height(), 300)

        cells  = {StructureType.SIMPLE: 1,
                  StructureType.DOUBLE: 2,
                  StructureType.TRIPLE: 3}[st]
        ouv    = float(params.get("ouverture", 2.0))
        gab    = float(params.get("gabarit",   2.0))
        ep     = float((params.get("epaisseurs_cadre") or [0.20])[0])
        h_remb = float((params.get("hauteurs_remblai") or [1.0])[0])

        total_w_m = cells * ouv + (cells + 1) * ep
        remb_vis  = min(max(h_remb, 0.0), 1.8)
        total_h_m = gab + 2 * ep + remb_vis

        # Marges : gauche/droite pour cotations, haut/bas pour centrage
        mx = 76   # marge horizontale (cotations verticales)
        my = 40   # marge verticale

        scale  = min((W - 2 * mx) / max(total_w_m, 0.1),
                     (H - 2 * my) / max(total_h_m, 0.1))

        dw     = total_w_m * scale
        dh_fr  = (gab + 2 * ep) * scale
        dh_tot = total_h_m * scale   # remblai + cadre

        # Centrer verticalement le dessin complet (remblai + cadre)
        ox     = (W - dw) / 2
        oy_top_total = (H - dh_tot) / 2        # haut du remblai
        oy_top = oy_top_total + remb_vis * scale  # haut du cadre
        oy_bot = oy_top + dh_fr
        ep_px  = ep  * scale
        ouv_px = ouv * scale
        gab_px = gab * scale

        # ── Grille légère ──
        step = 40
        for x in range(0, W, step):
            self.create_line(x, 0, x, H, fill=_C["grid"], width=1)
        for y in range(0, H, step):
            self.create_line(0, y, W, y, fill=_C["grid"], width=1)

        # ── Remblai ──
        if remb_vis > 0:
            rh  = remb_vis * scale
            ry  = oy_top - rh
            self.create_rectangle(
                ox, ry, ox + dw, oy_top,
                fill=_C["remblai"], outline="")
            # Hachures diagonales
            step_h = 20
            x0 = int(ox) - int(rh)
            while x0 < ox + dw + step_h:
                xa, ya = max(x0, ox), ry
                xb, yb = x0 + int(rh), oy_top
                xb = min(xb, ox + dw)
                if xb > xa:
                    self.create_line(xa, ya, xb, yb,
                                     fill="#AED6F1", width=1)
                x0 += step_h
            self.create_line(ox - 14, ry, ox + dw + 14, ry,
                             fill=_C["remblai_h"], width=2, dash=(8, 4))
            self._dim_v(ox - 40, ry, oy_top,
                        f"H = {h_remb:.2f} m")

        # ── Cadre béton (ombre légère) ──
        self.create_rectangle(
            ox + 3, oy_top + 3, ox + dw + 3, oy_bot + 3,
            fill="#CBD5E1", outline="")
        self.create_rectangle(
            ox, oy_top, ox + dw, oy_bot,
            fill=_C["concrete"], outline=_C["outline"], width=2)

        # ── Alvéoles ──
        for c in range(cells):
            cx1 = ox + ep_px + c * (ouv_px + ep_px)
            cx2 = cx1 + ouv_px
            cy1 = oy_top + ep_px
            cy2 = cy1 + gab_px
            self.create_rectangle(
                cx1, cy1, cx2, cy2,
                fill=_C["inner"], outline="#94A3B8", width=1)
            lbl = f"Dalot {c+1}" if cells > 1 else "Dalot Simple"
            if cells == 2:
                lbl = f"Dalot Double – Alvéole {c+1}"
            elif cells == 3:
                lbl = f"Dalot Triple – Alvéole {c+1}"
            else:
                lbl = "Dalot Simple"
            self.create_text(
                (cx1 + cx2) / 2, (cy1 + cy2) / 2 - 9,
                text=lbl,
                font=("Segoe UI", 9, "bold"),
                fill=_C["accent"])
            self.create_text(
                (cx1 + cx2) / 2, (cy1 + cy2) / 2 + 9,
                text=f"{ouv:.2f} × {gab:.2f} m",
                font=("Segoe UI", 8),
                fill=_C["text"])

        # ── Aciers principaux ──
        pad = max(4.0, ep_px * 0.20)
        for y_bar in [oy_top + pad, oy_top + ep_px - pad,
                      oy_bot - ep_px + pad, oy_bot - pad]:
            w = 2.5 if y_bar in (oy_top + pad, oy_bot - pad) else 1.5
            self.create_line(ox + pad, y_bar, ox + dw - pad, y_bar,
                             fill=_C["rebar"], width=w)

        for w_i in range(cells + 1):
            wx1 = ox + w_i * (ouv_px + ep_px) + pad
            wx2 = ox + w_i * (ouv_px + ep_px) + ep_px - pad
            self.create_line(wx1, oy_top + pad, wx1, oy_bot - pad,
                             fill=_C["rebar"], width=2)
            self.create_line(wx2, oy_top + pad, wx2, oy_bot - pad,
                             fill=_C["rebar"], width=1.5)

        # ── Étriers ──
        for w_i in range(cells + 1):
            wx1 = ox + w_i * (ouv_px + ep_px) + pad + 2
            wx2 = ox + w_i * (ouv_px + ep_px) + ep_px - pad - 2
            y   = oy_top + ep_px + 10
            while y < oy_bot - ep_px - 6:
                self.create_line(wx1, y, wx2, y,
                                 fill=_C["stirrup"], width=1.2)
                y += 15

        # ── Cotations ──
        self._dim_h(ox, ox + dw, oy_bot + 24,
                    f"Largeur totale = {total_w_m:.2f} m  (e = {ep:.2f} m)")
        self._dim_v(ox + dw + 28, oy_top, oy_bot,
                    f"H = {gab + 2*ep:.2f} m")

        # ── Légende (ancrée en bas du canvas) ──
        lx, ly = 10, H - 22
        self.create_rectangle(lx - 2, ly - 10, lx + 320, ly + 12,
                              fill=_C["legend_bg"], outline=_C["grid"])
        self.create_line(lx + 2,  ly, lx + 22, ly,
                         fill=_C["rebar"], width=2.5)
        self.create_text(lx + 26, ly, anchor=tk.W,
                         text="Aciers principaux",
                         font=("Segoe UI", 8), fill=_C["text"])
        self.create_line(lx + 148, ly, lx + 168, ly,
                         fill=_C["stirrup"], width=1.5)
        self.create_text(lx + 172, ly, anchor=tk.W,
                         text="Étriers",
                         font=("Segoe UI", 8), fill=_C["text"])
        if parsed and parsed.armatures:
            n = len(parsed.armatures)
            self.create_text(lx + 236, ly, anchor=tk.W,
                text=f"● {n} acier(s)",
                font=("Segoe UI", 8, "bold"), fill=_C["accent"])

    def _dim_h(self, x1, x2, y, label) -> None:
        self.create_line(x1, y, x2, y, fill=_C["dim"],
                         arrow=tk.BOTH, arrowshape=(6, 8, 3), width=1)
        self.create_line(x1, y - 5, x1, y + 5, fill=_C["dim"], width=1)
        self.create_line(x2, y - 5, x2, y + 5, fill=_C["dim"], width=1)
        self.create_text((x1 + x2) / 2, y + 13,
                         text=label,
                         font=("Segoe UI", 8), fill=_C["dim"])

    def _dim_v(self, x, y1, y2, label) -> None:
        self.create_line(x, y1, x, y2, fill=_C["dim"],
                         arrow=tk.BOTH, arrowshape=(6, 8, 3), width=1)
        self.create_line(x - 5, y1, x + 5, y1, fill=_C["dim"], width=1)
        self.create_line(x - 5, y2, x + 5, y2, fill=_C["dim"], width=1)
        self.create_text(x + 8, (y1 + y2) / 2,
                         anchor=tk.W, text=label,
                         font=("Segoe UI", 8), fill=_C["dim"])
