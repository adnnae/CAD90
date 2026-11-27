"""Zero-dependency pure-Python PDF 1.4 calculation note generator (A4)."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .models import StructureType
from .parser import ParsedResults


def _pdf_escape(text: str) -> str:
    # Convert to WinAnsi (cp1252) safe ASCII/Latin1 and escape PDF parens
    safe = text.encode("cp1252", errors="replace").decode("latin1")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_sketch_ops(
    structure_type: StructureType,
    params: Dict[str, Any],
    x0: float,
    y0: float,
    box_w: float,
    box_h: float,
) -> List[str]:
    """Emit PDF vector drawing commands for the dalot cross-section & rebars."""
    ops: List[str] = []
    cells = {StructureType.SIMPLE: 1, StructureType.DOUBLE: 2, StructureType.TRIPLE: 3}[structure_type]
    ouv = float(params.get("ouverture", 2.0))
    gab = float(params.get("gabarit", 2.0))
    ep = float((params.get("epaisseurs_cadre") or [0.20])[0])
    h_remb = float((params.get("hauteurs_remblai") or [1.0])[0])

    total_w_m = cells * ouv + (cells + 1) * ep
    total_h_m = gab + 2 * ep + min(h_remb, 1.5)
    scale = min((box_w - 40) / max(total_w_m, 0.5), (box_h - 40) / max(total_h_m, 0.5))

    dw = total_w_m * scale
    dh_frame = (gab + 2 * ep) * scale
    ox = x0 + (box_w - dw) / 2
    oy = y0 + 20

    # Backfill rectangle above frame
    if h_remb > 0:
        rh = min(h_remb, 1.5) * scale
        ops.append("0.92 0.94 0.96 rg")
        ops.append(f"{ox:.1f} {oy + dh_frame:.1f} {dw:.1f} {rh:.1f} re f")
        ops.append("0.45 0.50 0.58 RG 0.6 w")
        ops.append(f"{ox:.1f} {oy + dh_frame + rh:.1f} m {ox + dw:.1f} {oy + dh_frame + rh:.1f} l S")

    # Outer concrete frame
    ops.append("0.82 0.85 0.89 rg 0.15 0.22 0.35 RG 1.2 w")
    ops.append(f"{ox:.1f} {oy:.1f} {dw:.1f} {dh_frame:.1f} re B")

    # Inner cells (white)
    ep_px = ep * scale
    ouv_px = ouv * scale
    gab_px = gab * scale
    ops.append("1 1 1 rg 0.15 0.22 0.35 RG 1.0 w")
    for c in range(cells):
        cx = ox + ep_px + c * (ouv_px + ep_px)
        cy = oy + ep_px
        ops.append(f"{cx:.1f} {cy:.1f} {ouv_px:.1f} {gab_px:.1f} re B")

    # Reinforcement lines (red)
    ops.append("0.80 0.15 0.15 RG 1.4 w")
    pad = max(2.5, ep_px * 0.25)
    # Top & bottom longitudinal bars
    ops.append(f"{ox + pad:.1f} {oy + pad:.1f} m {ox + dw - pad:.1f} {oy + pad:.1f} l S")
    ops.append(f"{ox + pad:.1f} {oy + dh_frame - pad:.1f} m {ox + dw - pad:.1f} {oy + dh_frame - pad:.1f} l S")
    # Vertical wall bars
    for w_idx in range(cells + 1):
        wx = ox + w_idx * (ouv_px + ep_px) + pad
        ops.append(f"{wx:.1f} {oy + pad:.1f} m {wx:.1f} {oy + dh_frame - pad:.1f} l S")

    # Caption
    ops.append("0.10 0.15 0.25 rg")
    ops.append(
        f"BT /F1 8 Tf {ox:.1f} {y0 + 6:.1f} Td "
        f"({_pdf_escape(f'Ouvrage: {structure_type.label} | O={ouv:.2f}m | G={gab:.2f}m | e={ep:.2f}m | H_remblai={h_remb:.2f}m')}) Tj ET"
    )
    return ops


def export_pdf_report(
    output_path: Path,
    structure_type: StructureType,
    params: Dict[str, Any],
    parsed: ParsedResults,
    raw_text: str,
) -> Path:
    """Generate a multi-page A4 PDF calculation note and return its path."""
    pages_ops: List[List[str]] = []

    # ---- Page 1: Header, Schematic, Moments & Ferraillage Tables ----
    ops: List[str] = []
    # Header banner
    ops.append("0.06 0.09 0.16 rg 0 770 595 72 re f")
    ops.append("1 1 1 rg")
    ops.append("BT /F2 15 Tf 36 812 Td (NOTE DE CALCUL - PONT CADRE EN BETON ARME) Tj ET")
    ops.append(
        f"BT /F1 9 Tf 36 792 Td ({_pdf_escape(structure_type.label + '  |  Genere le ' + datetime.now().strftime('%d/%m/%Y %H:%M'))}) Tj ET"
    )

    # Schematic box
    ops.append("0.97 0.98 0.99 rg 0.80 0.84 0.90 RG 0.8 w 36 595 523 160 re B")
    ops.append("0.10 0.15 0.25 rg BT /F2 10 Tf 46 740 Td (1. MODELISATION ET FERRAILLAGE DE PRINCIPE) Tj ET")
    ops.extend(_build_sketch_ops(structure_type, params, 46, 602, 503, 130))

    y = 575.0
    # Moments table
    ops.append("0.10 0.15 0.25 rg BT /F2 10 Tf 36 575 Td (2. REPARTITION DES MOMENTS FLECHISSANTS (Tm/m)) Tj ET")
    y -= 16
    ops.append("0.12 0.22 0.38 rg 36 555 523 16 re f")
    ops.append("1 1 1 rg BT /F2 8 Tf 42 560 Td (Zone) Tj 180 560 Td (Extremum) Tj 260 560 Td (Ch.Perm) Tj 330 560 Td (Ch.Rout) Tj 400 560 Td (Sch.Remb) Tj 475 560 Td (Combinaison) Tj ET")
    y = 542.0
    ops.append("0 0 0 rg")
    for idx, m in enumerate(parsed.moments[:12]):
        if idx % 2 == 1:
            ops.append(f"0.96 0.97 0.98 rg 36 {y - 3:.1f} 523 13 re f 0 0 0 rg")
        ops.append(
            f"BT /F1 8 Tf 42 {y:.1f} Td ({_pdf_escape(m.zone)}) Tj "
            f"180 {y:.1f} Td ({_pdf_escape(m.extremum)}) Tj "
            f"265 {y:.1f} Td ({_pdf_escape(m.ch_perm)}) Tj "
            f"335 {y:.1f} Td ({_pdf_escape(m.ch_rout)}) Tj "
            f"405 {y:.1f} Td ({_pdf_escape(m.sch_remb)}) Tj "
            f"480 {y:.1f} Td ({_pdf_escape(m.combinaison)}) Tj ET"
        )
        y -= 13

    # Key efforts summary
    y -= 10
    ops.append(f"0.10 0.15 0.25 rg BT /F2 10 Tf 36 {y:.1f} Td (3. EFFORTS COMPLEMENTAIRES & SOL) Tj ET")
    y -= 14
    for k, v in parsed.metrics.items():
        ops.append(f"0 0 0 rg BT /F1 8.5 Tf 42 {y:.1f} Td ({_pdf_escape(f'{k}: {v}')}) Tj ET")
        y -= 12

    # Ferraillage table
    y -= 8
    ops.append(f"0.10 0.15 0.25 rg BT /F2 10 Tf 36 {y:.1f} Td (4. TABLEAU DE FERRAILLAGE) Tj ET")
    y -= 16
    if parsed.armatures:
        ops.append(f"0.12 0.22 0.38 rg 36 {y - 4:.1f} 523 15 re f")
        ops.append(
            f"1 1 1 rg BT /F2 8 Tf 42 {y:.1f} Td (Acier) Tj 110 {y:.1f} Td (Sec) Tj 180 {y:.1f} Td (D) Tj 250 {y:.1f} Td (EC) Tj 330 {y:.1f} Td (Longueur) Tj 430 {y:.1f} Td (Nombre) Tj ET"
        )
        y -= 14
        ops.append("0 0 0 rg")
        for r in parsed.armatures[:10]:
            ops.append(
                f"BT /F1 8 Tf 42 {y:.1f} Td ({_pdf_escape(r.acier)}) Tj 110 {y:.1f} Td ({_pdf_escape(r.sec)}) Tj "
                f"180 {y:.1f} Td ({_pdf_escape(r.d)}) Tj 250 {y:.1f} Td ({_pdf_escape(r.ec)}) Tj "
                f"330 {y:.1f} Td ({_pdf_escape(r.longueur)}) Tj 430 {y:.1f} Td ({_pdf_escape(r.nombre)}) Tj ET"
            )
            y -= 12
    else:
        ops.append(f"0.35 0.35 0.35 rg BT /F1 8.5 Tf 42 {y:.1f} Td (Aucun tableau d'armatures principales dans cette sortie.) Tj ET")
        y -= 12

    pages_ops.append(ops)

    # ---- Page 2+: Full raw calculation note ----
    raw_lines = raw_text.splitlines()
    chunk_size = 58
    for start in range(0, max(1, len(raw_lines)), chunk_size):
        p_ops = [
            "0.10 0.15 0.25 rg BT /F2 10 Tf 36 805 Td (ANNEXE - RAPPORT COMPLET DU MOTEUR DE CALCUL) Tj ET",
            "0 0 0 rg",
        ]
        py = 785.0
        for ln in raw_lines[start:start + chunk_size]:
            p_ops.append(f"BT /F3 7.5 Tf 36 {py:.1f} Td ({_pdf_escape(ln[:105])}) Tj ET")
            py -= 12.5
        pages_ops.append(p_ops)

    # Assemble PDF 1.4 objects
    objects: List[bytes] = []

    def add_obj(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    f1 = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    f2 = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    f3 = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    font_res = f"<< /F1 {f1} 0 R /F2 {f2} 0 R /F3 {f3} 0 R >>".encode("ascii")

    page_ids: List[int] = []
    pages_placeholder_idx = len(objects)
    objects.append(b"")  # placeholder for /Pages
    pages_obj_id = pages_placeholder_idx + 1

    for p_ops in pages_ops:
        stream_data = "\n".join(p_ops).encode("latin1", errors="replace")
        content_id = add_obj(
            f"<< /Length {len(stream_data)} >>\nstream\n".encode("ascii") + stream_data + b"\nendstream"
        )
        page_id = add_obj(
            f"<< /Type /Page /Parent {pages_obj_id} 0 R /MediaBox [0 0 595 842] /Resources << /Font {font_res.decode('ascii')} >> /Contents {content_id} 0 R >>".encode("ascii")
        )
        page_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[pages_placeholder_idx] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
    catalog_id = add_obj(f"<< /Type /Catalog /Pages {pages_obj_id} 0 R >>".encode("ascii"))

    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: List[int] = [0]
    for idx, obj in enumerate(objects, 1):
        offsets.append(len(buf))
        buf.extend(f"{idx} 0 obj\n".encode("ascii"))
        buf.extend(obj)
        buf.extend(b"\nendobj\n")

    xref_pos = len(buf)
    buf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets[1:]:
        buf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    buf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )

    output_path.write_bytes(bytes(buf))
    return output_path
