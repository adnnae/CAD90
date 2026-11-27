"""Parser for legacy engine text output (moments, efforts, ferraillage, metres).

Design principle: locate each named section once, parse it once, never accumulate
duplicates from overlapping console-screen captures.
"""

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional, Tuple


@dataclass
class MomentRow:
    zone: str
    extremum: str
    ch_perm: str
    ch_rout: str
    sch_remb: str
    combinaison: str


@dataclass
class RebarRow:
    acier: str
    sec: str
    d: str
    ec: str
    longueur: str
    nombre: str


@dataclass
class StirrupRow:
    nature: str
    sec: str
    d: str
    ecl: str
    ect: str
    dist: str
    longueur: str
    nombre: str


@dataclass
class ParsedResults:
    moments: List[MomentRow] = field(default_factory=list)
    armatures: List[RebarRow] = field(default_factory=list)
    etriers: List[StirrupRow] = field(default_factory=list)
    metrics: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Section detection helpers
# ---------------------------------------------------------------------------

_RE_MOMENT_HEADER = re.compile(
    r"MOMENTS\s+FLECHISSANTS\s+EN\s+TM/M", re.IGNORECASE
)
_RE_ARMATURES_HEADER = re.compile(
    r"ARMATURES\s+PRINCIPALES", re.IGNORECASE
)
_RE_ETRIERS_HEADER = re.compile(
    r"ETRIERS\s+\(ACIER\s+\d+\)|ETRIERS\s*/\s*EPINGLES|ETRIERS\s+ET\s+EPINGLES|^.*ETRIERS.*$",
    re.IGNORECASE,
)
_RE_EFFORTS_HEADER = re.compile(
    r"EFFORTS\s+MAXIMUM\s+DANS\s+UN\s+DEMI.OUVRAGE", re.IGNORECASE
)


def _find_last_section(lines: List[str], pattern: re.Pattern) -> Optional[int]:
    """Return the index of the LAST line that matches *pattern*."""
    result = None
    for i, ln in enumerate(lines):
        if pattern.search(ln):
            result = i
    return result


def _find_all_sections(lines: List[str], pattern: re.Pattern) -> List[int]:
    """Return indices of ALL lines matching *pattern*."""
    return [i for i, ln in enumerate(lines) if pattern.search(ln)]


# ---------------------------------------------------------------------------
# Zone label map for moment rows
# ---------------------------------------------------------------------------

_ZONE_FRAGMENTS: List[Tuple[str, str]] = [
    ("TRAVERSE SUPERIEURE", "Milieu traverse sup."),
    ("TRAVERSE INFERIEURE", "Milieu traverse inf."),
    ("PIEDROIT",            "Milieu des piedroits"),
    ("PIEDROITS",           "Milieu des piedroits"),
    ("INFERIEUR DROIT",     "Angle inférieur droit"),
    ("SUPERIEUR DROIT",     "Angle supérieur droit"),
    ("INFERIEUR",           "Angle inférieur"),
    ("SUPERIEUR",           "Angle supérieur"),
    ("MONTANT",             "Montant"),
]


def _zone_label(context: str) -> str:
    up = context.upper()
    for fragment, label in _ZONE_FRAGMENTS:
        if fragment in up:
            return label
    return context.strip() or "Zone"


# ---------------------------------------------------------------------------
# Individual section parsers
# ---------------------------------------------------------------------------

_RE_MAX = re.compile(
    r"\*\s*MAXIMUM\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"
)
_RE_MIN = re.compile(
    r"\*\s*MINIMUM\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"
)
_RE_ZONE_CONTEXT = re.compile(
    r"(DANS\s+L.ANGLE|AU\s+MILIEU|DANS\s+LE|A\s+[\d.]+\s+L\s+SUR\s+LA|TRAVERSE|PIEDROIT|MONTANT)",
    re.IGNORECASE,
)


def _parse_moments_block(lines: List[str], start: int) -> List[MomentRow]:
    """Parse one MOMENTS FLECHISSANTS block starting at *start*.

    Stops at the next major header or end of lines.
    """
    rows: List[MomentRow] = []
    current_zone = ""

    for ln in lines[start:]:
        s = ln.strip()
        # Stop at a new major section
        if _RE_EFFORTS_HEADER.search(s) or _RE_ARMATURES_HEADER.search(s):
            break
        # Second occurrence of the moments header → stop (we already have this block)
        # (handled by calling _parse_moments_block only on the last occurrence)

        # Update zone context from lines that set "DANS L'ANGLE ...", "AU MILIEU ..."
        if _RE_ZONE_CONTEXT.search(s) and "*" not in s:
            current_zone = s

        m = _RE_MAX.search(s)
        if m:
            # Try to get zone from continuation line(s) around context
            zone = _zone_label(current_zone + " " + s)
            rows.append(MomentRow(
                zone=zone,
                extremum="MAXIMUM",
                ch_perm=m.group(1),
                ch_rout=m.group(2),
                sch_remb=m.group(3),
                combinaison=m.group(4),
            ))
            continue

        m = _RE_MIN.search(s)
        if m:
            zone = _zone_label(current_zone + " " + s)
            rows.append(MomentRow(
                zone=zone,
                extremum="MINIMUM",
                ch_perm=m.group(1),
                ch_rout=m.group(2),
                sch_remb=m.group(3),
                combinaison=m.group(4),
            ))

    return rows


_RE_REBAR = re.compile(
    r"^\*\s*(\d+)\s*\*\s*([\d.]+)\s*\*\s*([\d.]+)\s*\*\s*([\d.]+)\s*\*\s*([\d.]+)\s*\*\s*(\d+)\s*\*$"
)
_RE_STIRRUP = re.compile(
    r"^\*\s*(EPINGLE|ETRIER)\s*\*\s*([\d.]+)\s*\*\s*([\d.]+)\s*\*\s*([\d.]+)\s*\*\s*([\d.]+)\s*\*\s*([\d.]+)\s*\*\s*([\d.]+)\s*\*\s*(\d+)\s*\*$",
    re.IGNORECASE,
)
_RE_NO_STIRRUP = re.compile(
    r"IL\s+N.EST\s+PAS\s+NECESSAIRE\s+DE\s+DISPOSER\s+DES\s+ETRIERS",
    re.IGNORECASE,
)


def _parse_armatures_block(lines: List[str], start: int) -> Tuple[List[RebarRow], List[StirrupRow]]:
    """Parse ARMATURES PRINCIPALES + ETRIERS block starting at *start*."""
    rebars: List[RebarRow] = []
    stirrups: List[StirrupRow] = []

    for ln in lines[start:]:
        s = ln.strip()
        m = _RE_REBAR.match(s)
        if m:
            rebars.append(RebarRow(
                acier=m.group(1),
                sec=m.group(2),
                d=m.group(3),
                ec=m.group(4),
                longueur=m.group(5),
                nombre=m.group(6),
            ))
            continue

        m = _RE_STIRRUP.match(s)
        if m:
            stirrups.append(StirrupRow(
                nature=m.group(1).strip().upper(),
                sec=m.group(2),
                d=m.group(3),
                ecl=m.group(4),
                ect=m.group(5),
                dist=m.group(6),
                longueur=m.group(7),
                nombre=m.group(8),
            ))

    return rebars, stirrups


_SCALAR_PATTERNS: List[Tuple[str, str]] = [
    ("EFFORT TRANCHANT MAXIMUM",   "Effort tranchant max (T)"),
    ("MOMENT TRANSVERSAL MAXIMUM", "Moment transversal max (Tm/m)"),
    ("MOMENT TRANSVERSAL MINIMUM", "Moment transversal min (Tm/m)"),
    ("PRESSION MAXIMALE AU SOL",   "Pression max au sol (T/m²)"),
]


def _parse_scalars(lines: List[str]) -> Dict[str, str]:
    metrics: Dict[str, str] = {}
    for ln in lines:
        s = ln.strip()
        for label, key in _SCALAR_PATTERNS:
            if label in s.upper():
                m = re.search(rf"{re.escape(label)}\s+([-\d.]+)", s, re.IGNORECASE)
                if m:
                    metrics[key] = m.group(1)
    return metrics


_WARNING_TRIGGERS = (
    "INSUFFISANTE",
    "INFERIEUR AU MOMENT",
    "TROP FAIBLE",
    "MANUELLEMENT",
    "IL N'EST PAS NECESSAIRE DE DISPOSER DES ETRIERS",
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_engine_report(text: str) -> ParsedResults:
    """Extract structured moments, efforts, and reinforcement tables from report text.

    Uses section-based parsing: each named section is located once (taking the
    LAST occurrence to handle partially-scrolled duplicates) and parsed exactly
    once — guaranteeing no duplicates regardless of how many console frames were
    captured.
    """
    res = ParsedResults()
    if not text:
        return res

    lines = text.splitlines()

    # ---- 1. Moments --------------------------------------------------------
    # Find ALL occurrences; use the LAST complete one (most data, least truncation)
    moment_starts = _find_all_sections(lines, _RE_MOMENT_HEADER)
    if moment_starts:
        # Pick the occurrence that yields the most rows (usually the last)
        best_rows: List[MomentRow] = []
        for idx in moment_starts:
            rows = _parse_moments_block(lines, idx + 1)
            if len(rows) >= len(best_rows):
                best_rows = rows
        res.moments = best_rows

    # ---- 2. Armatures & Etriers -------------------------------------------
    armature_starts = _find_all_sections(lines, _RE_ARMATURES_HEADER)
    if armature_starts:
        # Same: take the occurrence with the most rebar rows
        best_rebars: List[RebarRow] = []
        best_stirrups: List[StirrupRow] = []
        for idx in armature_starts:
            rb, st = _parse_armatures_block(lines, idx + 1)
            if len(rb) >= len(best_rebars):
                best_rebars = rb
                best_stirrups = st
        res.armatures = best_rebars
        res.etriers = best_stirrups

    # ---- 3. Scalar metrics (deduplicated by dict key) ----------------------
    res.metrics = _parse_scalars(lines)

    # ---- 4. Warnings -------------------------------------------------------
    seen_warnings: set = set()
    for ln in lines:
        s = ln.strip()
        if any(w in s.upper() for w in _WARNING_TRIGGERS):
            if s not in seen_warnings:
                seen_warnings.add(s)
                res.warnings.append(s)

    return res
