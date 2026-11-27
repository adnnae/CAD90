"""Générateur SVG fidèle à 100% au composant Tkinter DalotSketchCanvas."""

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


def generate_dalot_svg_exact(
    structure_type: StructureType,
    params: Dict[str, Any],
    parsed: Optional[ParsedResults] = None,
    W: int = 560,
    H: int = 420,
) -> str:
    cells = {StructureType.SIMPLE: 1, StructureType.DOUBLE: 2, StructureType.TRIPLE: 3}[structure_type]
    ouv = float(params.get("ouverture", 2.0))
    gab = float(params.get("gabarit", 2.0))
    ep = float((params.get("epaisseurs_cadre") or [0.20])[0])
    h_remb = float((params.get("hauteurs_remblai") or [1.0])[0])

    total_w_m = cells * ouv + (cells + 1) * ep
    remb_vis = min(max(h_remb, 0.0), 1.8)
    total_h_m = gab + 2 * ep + remb_vis

    mx = 76
    my = 40

    scale = min((W - 2 * mx) / max(total_w_m, 0.1), (H - 2 * my) / max(total_h_m, 0.1))

    dw = total_w_m * scale
    dh_fr = (gab + 2 * ep) * scale
    dh_tot = total_h_m * scale

    ox = (W - dw) / 2
    oy_top_total = (H - dh_tot) / 2
    oy_top = oy_top_total + remb_vis * scale
    oy_bot = oy_top + dh_fr
    ep_px = ep * scale
    ouv_px = ouv * scale
    gab_px = gab * scale

    svg: list[str] = [
        f'<svg width="100%" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="background:#FFFFFF; font-family:\'Segoe UI\', sans-serif;">',
        '<defs>',
        '  <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">',
        '    <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="#64748B"/>',
        '  </marker>',
        '</defs>',
    ]

    # Grille légère
    for x in range(0, W, 40):
        svg.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="{_C["grid"]}" stroke-width="1"/>')
    for y in range(0, H, 40):
        svg.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{_C["grid"]}" stroke-width="1"/>')

    # Remblai
    if remb_vis > 0:
        rh = remb_vis * scale
        ry = oy_top - rh
        svg.append(f'<rect x="{ox}" y="{ry}" width="{dw}" height="{rh}" fill="{_C["remblai"]}" stroke="none"/>')
        
        # Hachures diagonales
        step_h = 20
        x0 = int(ox) - int(rh)
        while x0 < ox + dw + step_h:
            xa, ya = max(x0, ox), ry
            xb, yb = x0 + int(rh), oy_top
            xb = min(xb, ox + dw)
            if xb > xa:
                svg.append(f'<line x1="{xa}" y1="{ya}" x2="{xb}" y2="{yb}" stroke="#AED6F1" stroke-width="1"/>')
            x0 += step_h

        svg.append(f'<line x1="{ox - 14}" y1="{ry}" x2="{ox + dw + 14}" y2="{ry}" stroke="{_C["remblai_h"]}" stroke-width="2" stroke-dasharray="8,4"/>')

        # Cotation H remblai gauche
        dim_x = ox - 40
        svg.append(f'<line x1="{dim_x}" y1="{ry}" x2="{dim_x}" y2="{oy_top}" stroke="{_C["dim"]}" stroke-width="1" marker-start="url(#arrow)" marker-end="url(#arrow)"/>')
        svg.append(f'<line x1="{dim_x - 5}" y1="{ry}" x2="{dim_x + 5}" y2="{ry}" stroke="{_C["dim"]}" stroke-width="1"/>')
        svg.append(f'<line x1="{dim_x - 5}" y1="{oy_top}" x2="{dim_x + 5}" y2="{oy_top}" stroke="{_C["dim"]}" stroke-width="1"/>')
        svg.append(f'<text x="{dim_x - 8}" y="{(ry + oy_top)/2 + 4}" fill="{_C["dim"]}" font-size="10" text-anchor="end">H = {h_remb:.2f} m</text>')

    # Cadre béton (ombre légère + corps)
    svg.append(f'<rect x="{ox + 3}" y="{oy_top + 3}" width="{dw}" height="{dh_fr}" fill="#CBD5E1" stroke="none"/>')
    svg.append(f'<rect x="{ox}" y="{oy_top}" width="{dw}" height="{dh_fr}" fill="{_C["concrete"]}" stroke="{_C["outline"]}" stroke-width="2"/>')

    # Alvéoles
    for c in range(cells):
        cx1 = ox + ep_px + c * (ouv_px + ep_px)
        cx2 = cx1 + ouv_px
        cy1 = oy_top + ep_px
        cy2 = cy1 + gab_px
        svg.append(f'<rect x="{cx1}" y="{cy1}" width="{ouv_px}" height="{gab_px}" fill="{_C["inner"]}" stroke="#94A3B8" stroke-width="1"/>')

        lbl = "Dalot Simple"
        if cells == 2:
            lbl = f"Dalot Double – Alvéole {c+1}"
        elif cells == 3:
            lbl = f"Dalot Triple – Alvéole {c+1}"

        svg.append(f'<text x="{(cx1 + cx2)/2}" y="{(cy1 + cy2)/2 - 8}" fill="{_C["accent"]}" font-size="11" font-weight="bold" text-anchor="middle">{lbl}</text>')
        svg.append(f'<text x="{(cx1 + cx2)/2}" y="{(cy1 + cy2)/2 + 12}" fill="{_C["text"]}" font-size="10" text-anchor="middle">{ouv:.2f} × {gab:.2f} m</text>')

    # Aciers principaux (barres rouges)
    pad = max(4.0, ep_px * 0.20)
    for y_bar in [oy_top + pad, oy_top + ep_px - pad, oy_bot - ep_px + pad, oy_bot - pad]:
        sw = 2.5 if y_bar in (oy_top + pad, oy_bot - pad) else 1.5
        svg.append(f'<line x1="{ox + pad}" y1="{y_bar}" x2="{ox + dw - pad}" y2="{y_bar}" stroke="{_C["rebar"]}" stroke-width="{sw}"/>')

    for w_i in range(cells + 1):
        wx1 = ox + w_i * (ouv_px + ep_px) + pad
        wx2 = ox + w_i * (ouv_px + ep_px) + ep_px - pad
        svg.append(f'<line x1="{wx1}" y1="{oy_top + pad}" x2="{wx1}" y2="{oy_bot - pad}" stroke="{_C["rebar"]}" stroke-width="2"/>')
        svg.append(f'<line x1="{wx2}" y1="{oy_top + pad}" x2="{wx2}" y2="{oy_bot - pad}" stroke="{_C["rebar"]}" stroke-width="1.5"/>')

    # Étriers (bleus)
    for w_i in range(cells + 1):
        wx1 = ox + w_i * (ouv_px + ep_px) + pad + 2
        wx2 = ox + w_i * (ouv_px + ep_px) + ep_px - pad - 2
        y = oy_top + ep_px + 10
        while y < oy_bot - ep_px - 6:
            svg.append(f'<line x1="{wx1}" y1="{y}" x2="{wx2}" y2="{y}" stroke="{_C["stirrup"]}" stroke-width="1.2"/>')
            y += 15

    # Cotation horizontale bas
    dim_y = oy_bot + 24
    svg.append(f'<line x1="{ox}" y1="{dim_y}" x2="{ox + dw}" y2="{dim_y}" stroke="{_C["dim"]}" stroke-width="1" marker-start="url(#arrow)" marker-end="url(#arrow)"/>')
    svg.append(f'<line x1="{ox}" y1="{dim_y - 5}" x2="{ox}" y2="{dim_y + 5}" stroke="{_C["dim"]}" stroke-width="1"/>')
    svg.append(f'<line x1="{ox + dw}" y1="{dim_y - 5}" x2="{ox + dw}" y2="{dim_y + 5}" stroke="{_C["dim"]}" stroke-width="1"/>')
    svg.append(f'<text x="{ox + dw/2}" y="{dim_y + 14}" fill="{_C["dim"]}" font-size="10" text-anchor="middle">Largeur totale = {total_w_m:.2f} m  (e = {ep:.2f} m)</text>')

    # Cotation verticale droite
    dim_rx = ox + dw + 28
    svg.append(f'<line x1="{dim_rx}" y1="{oy_top}" x2="{dim_rx}" y2="{oy_bot}" stroke="{_C["dim"]}" stroke-width="1" marker-start="url(#arrow)" marker-end="url(#arrow)"/>')
    svg.append(f'<line x1="{dim_rx - 5}" y1="{oy_top}" x2="{dim_rx + 5}" y2="{oy_top}" stroke="{_C["dim"]}" stroke-width="1"/>')
    svg.append(f'<line x1="{dim_rx - 5}" y1="{oy_bot}" x2="{dim_rx + 5}" y2="{oy_bot}" stroke="{_C["dim"]}" stroke-width="1"/>')
    svg.append(f'<text x="{dim_rx + 8}" y="{(oy_top + oy_bot)/2 + 4}" fill="{_C["dim"]}" font-size="10" text-anchor="start">H = {gab + 2*ep:.2f} m</text>')

    # Légende en bas
    lx, ly = 16, H - 20
    svg.append(f'<rect x="{lx - 4}" y="{ly - 12}" width="310" height="22" fill="{_C["legend_bg"]}" stroke="{_C["grid"]}" rx="3"/>')
    svg.append(f'<line x1="{lx + 4}" y1="{ly}" x2="{lx + 24}" y2="{ly}" stroke="{_C["rebar"]}" stroke-width="2.5"/>')
    svg.append(f'<text x="{lx + 28}" y="{ly + 4}" fill="{_C["text"]}" font-size="10">Aciers principaux</text>')
    svg.append(f'<line x1="{lx + 138}" y1="{ly}" x2="{lx + 158}" y2="{ly}" stroke="{_C["stirrup"]}" stroke-width="1.5"/>')
    svg.append(f'<text x="{lx + 162}" y="{ly + 4}" fill="{_C["text"]}" font-size="10">Étriers</text>')

    if parsed and parsed.armatures:
        n = len(parsed.armatures)
        svg.append(f'<text x="{lx + 225}" y="{ly + 4}" fill="{_C["accent"]}" font-size="10" font-weight="bold">● {n} acier(s)</text>')

    svg.append('</svg>')
    return "\n".join(svg)
