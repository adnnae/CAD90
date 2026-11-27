"""Générateur SVG pour la coupe transversale du dalot (Streamlit & Web)."""

from typing import Any, Dict, Optional
from core.models import StructureType
from core.parser import ParsedResults


def generate_dalot_svg(
    structure_type: StructureType,
    params: Dict[str, Any],
    parsed: Optional[ParsedResults] = None,
    width: int = 700,
    height: int = 340,
) -> str:
    cells = {StructureType.SIMPLE: 1, StructureType.DOUBLE: 2, StructureType.TRIPLE: 3}[structure_type]
    ouv = float(params.get("ouverture", 2.0))
    gab = float(params.get("gabarit", 2.0))
    ep = float((params.get("epaisseurs_cadre") or [0.20])[0])
    h_remb = float((params.get("hauteurs_remblai") or [1.0])[0])

    total_w = cells * ouv + (cells + 1) * ep
    total_h = gab + 2 * ep + min(h_remb, 2.0)

    pad_x = 70
    pad_y = 50
    avail_w = width - 2 * pad_x
    avail_h = height - 2 * pad_y

    scale = min(avail_w / max(total_w, 0.5), avail_h / max(total_h, 0.5))

    dw = total_w * scale
    dh_cadre = (gab + 2 * ep) * scale
    ox = pad_x + (avail_w - dw) / 2
    oy = height - pad_y - dh_cadre

    svg_parts = [
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px;">',
        '<defs>',
        '  <pattern id="soilPattern" width="10" height="10" patternUnits="userSpaceOnUse">',
        '    <path d="M 0 10 L 10 0 M 0 0 L 10 10" stroke="#CBD5E1" stroke-width="0.8"/>',
        '  </pattern>',
        '</defs>',
    ]

    # Remblai
    if h_remb > 0:
        rh = min(h_remb, 2.0) * scale
        ry = oy - rh
        svg_parts.append(
            f'<rect x="{ox}" y="{ry}" width="{dw}" height="{rh}" fill="#EFF6FF" stroke="#93C5FD" stroke-width="1.5"/>'
        )
        svg_parts.append(
            f'<rect x="{ox}" y="{ry}" width="{dw}" height="{rh}" fill="url(#soilPattern)" opacity="0.3"/>'
        )
        svg_parts.append(
            f'<text x="{ox + dw/2}" y="{ry + rh/2 + 4}" fill="#2563EB" font-size="12" font-family="sans-serif" font-weight="600" text-anchor="middle">Remblai: {h_remb:.2f} m</text>'
        )

    # Cadre béton extérieur
    svg_parts.append(
        f'<rect x="{ox}" y="{oy}" width="{dw}" height="{dh_cadre}" fill="#94A3B8" stroke="#1E3A5F" stroke-width="2"/>'
    )

    # Alvéoles intérieures
    ep_px = ep * scale
    ouv_px = ouv * scale
    gab_px = gab * scale

    for c in range(cells):
        cx = ox + ep_px + c * (ouv_px + ep_px)
        cy = oy + ep_px
        svg_parts.append(
            f'<rect x="{cx}" y="{cy}" width="{ouv_px}" height="{gab_px}" fill="#F8FAFC" stroke="#1E3A5F" stroke-width="1.5"/>'
        )
        svg_parts.append(
            f'<text x="{cx + ouv_px/2}" y="{cy + gab_px/2 - 5}" fill="#1E3A5F" font-size="13" font-family="sans-serif" font-weight="bold" text-anchor="middle">Alvéole {c+1}</text>'
        )
        svg_parts.append(
            f'<text x="{cx + ouv_px/2}" y="{cy + gab_px/2 + 15}" fill="#64748B" font-size="11" font-family="sans-serif" text-anchor="middle">{ouv:.2f} × {gab:.2f} m</text>'
        )

    # Cotes extérieures
    # Épaisseur
    svg_parts.append(
        f'<text x="{ox - 10}" y="{oy + dh_cadre/2}" fill="#64748B" font-size="11" font-family="sans-serif" text-anchor="end">H={gab + 2*ep:.2f}m</text>'
    )
    svg_parts.append(
        f'<text x="{ox + dw/2}" y="{oy + dh_cadre + 25}" fill="#64748B" font-size="11" font-family="sans-serif" text-anchor="middle">Largeur totale = {total_w:.2f}m (Épaisseur d={ep:.2f}m)</text>'
    )

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)
