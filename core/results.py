"""Result collector, screen deduplicator, and decoder for legacy engine outputs."""

from pathlib import Path
from typing import List

from .models import ExecutionResult

# Lines that are interactive prompts – never part of the report
_PROMPT_NOISE = (
    "nom de votre fichier",
    "sortie de resultats",
    "1 = ecran",
    "2 = imprimante",
    "entrez votre choix",
    "taper return",
    "stop - program terminated",
    "stop - program",
)


def read_text_with_fallback(path: Path) -> str:
    """Read a legacy output file trying UTF-8, CP850 (DOS), CP1252, and Latin1."""
    raw = path.read_bytes()
    for enc in ("utf-8", "cp850", "cp1252", "latin1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1", errors="replace")


def _is_noise(line: str) -> bool:
    low = line.strip().lower()
    return any(low.startswith(p) for p in _PROMPT_NOISE)


def _clean_lines(screen: str) -> List[str]:
    """Strip prompt noise and trailing blank lines from a single captured screen."""
    lines = [ln.rstrip() for ln in screen.splitlines() if not _is_noise(ln)]
    # Drop leading blank lines
    while lines and not lines[0]:
        lines.pop(0)
    # Drop trailing blank lines
    while lines and not lines[-1]:
        lines.pop()
    return lines


def merge_console_screens(screens: List[str]) -> str:
    """Merge overlapping scrolled console captures into one clean, deduplicated report.

    Strategy
    --------
    Each captured screen is a fixed-size snapshot of the console buffer. When the
    engine scrolls, the new snapshot overlaps with the previous one: the bottom N
    lines of the previous screen reappear at the top of the next screen.

    Algorithm:
    1. Clean each screen individually (remove prompts, blank padding).
    2. Append each screen to the running merged list by finding the longest
       suffix of `merged` that is a prefix of the new screen (overlap), then
       appending only the non-overlapping tail.
    3. After merging all screens, perform a final deduplication pass that removes
       any contiguous block that has already appeared earlier in the report.
    """
    merged: List[str] = []

    for raw_screen in screens:
        lines = _clean_lines(raw_screen)
        if not lines:
            continue

        if not merged:
            merged.extend(lines)
            continue

        # Find the longest overlap where suffix of merged == prefix of lines
        max_k = min(len(merged), len(lines))
        overlap = 0
        for k in range(max_k, 0, -1):
            if merged[-k:] == lines[:k]:
                overlap = k
                break

        if overlap > 0:
            # Normal scroll: just append the new part
            merged.extend(lines[overlap:])
            continue

        # No exact overlap found – try partial scroll: search for the first line
        # of the new screen somewhere in the last 40 lines of merged, then validate
        # that subsequent lines also match.
        tail_start = max(0, len(merged) - 40)
        tail = merged[tail_start:]
        first_new = lines[0]
        best_pos = -1
        for ti, tl in enumerate(tail):
            if tl == first_new:
                # Validate subsequent lines
                matched = 0
                while matched < len(lines) and ti + matched < len(tail):
                    if tail[ti + matched] == lines[matched]:
                        matched += 1
                    else:
                        break
                if matched >= min(3, len(lines)):
                    # Good enough match; check that merged ends at this sequence
                    if tail_start + ti + matched == len(merged):
                        best_pos = matched
                        break

        if best_pos > 0:
            merged.extend(lines[best_pos:])
        else:
            # Truly new content (different section); append with a blank separator
            merged.append("")
            merged.extend(lines)

    # ---- Final deduplication pass ----------------------------------------
    # Remove any block of lines that has already appeared verbatim earlier.
    # We work with non-empty lines only to find duplicate sections.
    merged = _deduplicate_sections(merged)

    return "\n".join(merged).strip()


def _deduplicate_sections(lines: List[str]) -> List[str]:
    """Remove duplicate contiguous blocks.

    The engine output is divided by section headers (lines of '*' characters or
    all-caps titles). Whenever the same section header appears twice, we keep
    only the LAST occurrence (most complete capture).
    """
    # Identify section boundaries: lines that look like report headers
    # (contain "PONTS CADRES", "ARMATURES", "EFFORTS", "MOMENTS", "COFFRAGE", etc.)
    _SECTION_MARKERS = (
        "PONTS CADRES EN BETON ARME",
        "RAPPEL DES DONNEES",
        "EFFORTS MAXIMUM DANS UN DEMI-OUVRAGE",
        "MOMENTS FLECHISSANTS EN TM/M",
        "ARMATURES PRINCIPALES",
        "ETRIERS",
        "COFFRAGE,METRES",
        "COUPLES D'EFFORTS",
    )

    # Split lines into blocks delimited by section markers
    blocks: List[List[str]] = []
    current: List[str] = []
    for ln in lines:
        stripped = ln.strip()
        is_marker = any(m in stripped.upper() for m in _SECTION_MARKERS)
        if is_marker and current:
            blocks.append(current)
            current = [ln]
        else:
            current.append(ln)
    if current:
        blocks.append(current)

    # Keep only the last occurrence of each section (identified by first non-empty line)
    seen_first: dict = {}
    for i, block in enumerate(blocks):
        key = next((ln.strip() for ln in block if ln.strip()), None)
        if key:
            seen_first[key] = i  # overwrite → keeps last occurrence

    kept_indices = set(seen_first.values())
    # Always keep blocks that have no recognisable key
    for i, block in enumerate(blocks):
        key = next((ln.strip() for ln in block if ln.strip()), None)
        if not key:
            kept_indices.add(i)

    result: List[str] = []
    for i, block in enumerate(blocks):
        if i in kept_indices:
            result.extend(block)

    return result


def format_execution_summary(result: ExecutionResult) -> str:
    """Build a human-readable execution report."""
    lines: List[str] = [
        f"Type d'ouvrage : {result.structure_type.label}",
        f"Moteur         : {result.engine_path}",
        f"Dossier travail: {result.work_dir}",
        f"Fichier données: {result.data_file_path}",
        f"Statut         : {'SUCCÈS' if result.success else 'ERREUR'}",
    ]
    if result.exit_code is not None:
        lines.append(f"Code retour    : {result.exit_code}")
    if result.error_message:
        lines.append(f"Message        : {result.error_message}")
    if result.generated_files:
        lines.append("Fichiers générés :")
        for f in result.generated_files:
            lines.append(f"  - {f.name} ({f.stat().st_size} octets)")
    return "\n".join(lines)
