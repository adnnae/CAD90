"""
bq_export.py – Génération de l'avant-métré (BQ) ferraillage dans le modèle Excel.

Principe d'injection :
  Les aciers 1..N du moteur CAD90 correspondent exactement aux lignes 10..10+(N-1)
  du tableau de nomenclature dans chaque feuille corps.

  Pour chaque acier CAD90 (numéro i = 1..N) :
    → Ligne Excel = 10 + (i - 1)
    → C  = diamètre  (mm)
    → J  = espacement (cm)
    → K  = nombre de barres        ← valeur FIXE (écrase la valeur exemple)
    → L  = longueur unitaire (m)   ← valeur FIXE (écrase la valeur exemple)

  Les repères biais (1a, 2a, Bis...) et les aciers de répartition (11, 12, 13...)
  ont des formules Excel qui se recalculent automatiquement quand on injecte
  Ouverture / Gabarit / Épaisseur / L dans les cellules de paramètres.

Structure des lignes de données par type :
  Simple : aciers structuraux lignes 10–19  (10 aciers max)
  Double : aciers structuraux lignes 10–21  (12 aciers max)
  Triple : aciers structuraux lignes 10–21  (12 aciers max)
"""

import shutil
from pathlib import Path
from datetime import datetime

try:
    import openpyxl
    from openpyxl import load_workbook
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = _DIR / "config" / "template_bq.xlsx"
if not TEMPLATE_PATH.is_file():
    # Fallback to brain user uploaded template if present
    _fallback = Path(r"C:\Users\ad\.gemini\antigravity\brain\c14f72bc-450e-489e-8537-05e6a4351847\.user_uploaded\media_1795634603859_44eed55f.xlsx")
    if _fallback.is_file():
        TEMPLATE_PATH = _fallback

# Poids linéiques HA (kg/m) par diamètre mm
POIDS_HA = {
    6:  0.222,
    8:  0.395,
    10: 0.617,
    12: 0.888,
    14: 1.208,
    16: 1.578,
    20: 2.466,
    25: 3.853,
}

# Mapping feuilles par type : (corps, têtes)
SHEET_MAP = {
    "simple": ("ferr corps simple",  "ferr tetes simple"),
    "double": ("ferr corps double",  "ferr tetesdouble"),
    "triple": ("ferr corps triple",  "ferr tetes triple"),
}

# Toutes les feuilles connues dans le template
_ALL_SHEETS = {s for pair in SHEET_MAP.values() for s in pair}

# Première ligne de données aciers structuraux (repère 1) dans chaque feuille corps
_FIRST_DATA_ROW = 10

# Nombre max d'aciers structuraux injectables par type
# Au-delà, le template n'a plus de lignes prévues pour les aciers structuraux
_MAX_STRUCTURAL_REBARS = {
    "simple": 10,   # lignes 10–19
    "double": 12,   # lignes 10–21
    "triple": 12,   # lignes 10–21
}

# Ligne des paramètres géométriques par type (Ouv/Gab/Ep/L)
_CORPS_PARAM_ROW = {
    "simple": 6,
    "double": 4,
    "triple": 6,
}


def _safe_float(val, default=0.0):
    try:
        return float(str(val).strip())
    except Exception:
        return default


def _safe_int(val, default=0):
    try:
        return int(float(str(val).strip()))
    except Exception:
        return default


def _set_cell(ws, row, col, value):
    """Écrit une valeur dans une cellule en gérant les plages fusionnées."""
    from openpyxl.utils import get_column_letter
    coord = f"{get_column_letter(col)}{row}"
    for mr in ws.merged_cells.ranges:
        if coord in mr:
            master = f"{get_column_letter(mr.min_col)}{mr.min_row}"
            ws[master] = value
            return
    ws.cell(row=row, column=col, value=value)


# ── Colonnes du tableau de nomenclature ─────────────────────────────────────
# B=repère, C=diamètre, D=schéma, E..I=dimensions, J=espacement, K=nombre, L=longueur unitaire
_COL_REPERE  = 2   # B
_COL_DIAM    = 3   # C
_COL_ESP     = 10  # J
_COL_NBRE    = 11  # K
_COL_LONG    = 12  # L


def _inject_structural_rebars(ws, armatures, stype):
    """
    Injecte les aciers structuraux CAD90 (1..N) dans les lignes du template.

    Acier CAD90 numéro i  →  ligne Excel = _FIRST_DATA_ROW + (i - 1)
    Colonnes mises à jour : C (diamètre mm), J (espacement cm), K (nombre), L (longueur m)
    """
    max_rebars = _MAX_STRUCTURAL_REBARS.get(stype, 12)

    for arm in armatures:
        idx = _safe_int(arm.get("acier_num", 0))
        if idx < 1 or idx > max_rebars:
            continue

        row = _FIRST_DATA_ROW + (idx - 1)

        diam  = _safe_float(arm.get("diametre",   0))
        esp   = _safe_float(arm.get("espacement", 0))
        nbre  = _safe_int(arm.get("nombre",   0))
        long_ = _safe_float(arm.get("longueur",   0))

        # Espacement en cm dans le template (CAD90 donne en m → ×100, arrondi entier)
        esp_cm = round(esp * 100) if esp < 1.0 else round(esp)

        _set_cell(ws, row, _COL_DIAM, diam)
        _set_cell(ws, row, _COL_ESP,  esp_cm)
        _set_cell(ws, row, _COL_NBRE, nbre)
        _set_cell(ws, row, _COL_LONG, round(long_, 3))


def _write_params_corps(ws, params, row):
    """Injecte Ouverture/Gabarit/Épaisseur/Longueur dans la ligne de paramètres."""
    _set_cell(ws, row, 4,  _safe_float(params.get("ouverture",       2.0)))   # D
    _set_cell(ws, row, 9,  _safe_float(params.get("gabarit",         2.0)))   # I
    _set_cell(ws, row, 14, _safe_float(params.get("epaisseur",       0.20)))  # N
    _set_cell(ws, row, 18, _safe_float(params.get("longueur_ouvrage", 12.0))) # R


def _write_params_tetes(ws, params):
    """Injecte les paramètres géométriques dans la feuille têtes."""
    _set_cell(ws, 5, 2,  _safe_float(params.get("ouverture",           2.0)))
    _set_cell(ws, 5, 4,  _safe_float(params.get("gabarit",             2.0)))
    _set_cell(ws, 5, 6,  _safe_float(params.get("epaisseur",           0.20)))
    _set_cell(ws, 5, 9,  _safe_float(params.get("hauteur_parafouille", 1.0)))
    _set_cell(ws, 5, 13, _safe_float(params.get("angle_biais",         90.0)))


# ── Point d'entrée principal ─────────────────────────────────────────────────

def export_bq_excel(output_path: str, structure_type_name: str, params: dict,
                    armatures: list, etriers: list,
                    template_path: str = None) -> str:
    """
    Génère le fichier Excel avant-métré en injectant les données CAD90
    directement dans les bonnes cellules du template.

    Les formules Excel existantes (longueurs biais, aciers répartition,
    totaux par diamètre, poids...) se recalculent automatiquement.

    Args:
        output_path         : chemin du .xlsx de sortie
        structure_type_name : 'simple' | 'double' | 'triple'
        params              : dict avec ouverture, gabarit, epaisseur, longueur_ouvrage...
        armatures           : liste de dicts depuis _on_export_bq()
                              clés : acier_num, diametre, espacement, longueur, nombre
        etriers             : liste de dicts étriers (non injectés dans le corps)
        template_path       : chemin optionnel vers le template Excel
    """
    if not HAS_OPENPYXL:
        raise ImportError("openpyxl non installé. Lancez : pip install openpyxl")

    tpl = Path(template_path) if template_path else TEMPLATE_PATH
    if not tpl.exists():
        raise FileNotFoundError(f"Template introuvable : {tpl}")

    stype = structure_type_name.lower()
    if stype not in SHEET_MAP:
        raise ValueError(f"Type inconnu : '{stype}'. Attendu : simple, double ou triple.")

    sheet_corps, sheet_tetes = SHEET_MAP[stype]

    # Copie du template
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tpl, out)
    wb = load_workbook(out)

    # Supprimer les feuilles des autres types
    sheets_to_keep = {sheet_corps, sheet_tetes}
    for name in list(wb.sheetnames):
        if name in _ALL_SHEETS and name not in sheets_to_keep:
            del wb[name]

    # ── Feuille CORPS ─────────────────────────────────────────────────────────
    if sheet_corps not in wb.sheetnames:
        raise KeyError(f"Feuille '{sheet_corps}' absente. Disponibles : {wb.sheetnames}")
    ws_corps = wb[sheet_corps]

    # 1. Paramètres géométriques → les formules de dimensions se recalculent
    param_row = _CORPS_PARAM_ROW[stype]
    _write_params_corps(ws_corps, params, param_row)

    # 2. Aciers structuraux CAD90 → lignes 10..10+(N-1)
    _inject_structural_rebars(ws_corps, armatures, stype)

    # 3. En-tête
    nom    = params.get("nom_fichier", "DALOT01")
    ouv    = params.get("ouverture",  "?")
    gab    = params.get("gabarit",    "?")
    now    = datetime.now().strftime("%d/%m/%Y %H:%M")
    header = f"OH : DALOT {stype.upper()} ({ouv}x{gab}) – {nom} – généré le {now}"
    _set_cell(ws_corps, 2, 2, header)

    # ── Feuille TETES ─────────────────────────────────────────────────────────
    if sheet_tetes not in wb.sheetnames:
        raise KeyError(f"Feuille '{sheet_tetes}' absente. Disponibles : {wb.sheetnames}")
    ws_tetes = wb[sheet_tetes]
    _write_params_tetes(ws_tetes, params)
    _set_cell(ws_tetes, 2, 1, header)

    wb.save(out)
    wb.close()
    return str(out)


# ── Helpers appelés depuis ui/app.py ─────────────────────────────────────────

def build_bq_params(app_params: dict, parsed_metrics: dict = None) -> dict:
    """
    Transforme les paramètres GUI vers le dict attendu par export_bq_excel.
    - epaisseur  : lit 'epaisseurs_cadre' (liste) → premier élément
    - longueur   : lit les metrics du parser (ligne COFFRAGE,METRES)
    """
    metrics = parsed_metrics or {}

    epaisseurs_cadre = app_params.get("epaisseurs_cadre", None)
    if isinstance(epaisseurs_cadre, (list, tuple)) and len(epaisseurs_cadre) > 0:
        epaisseur = _safe_float(epaisseurs_cadre[0], 0.20)
    else:
        epaisseur = _safe_float(app_params.get("epaisseur", 0.20), 0.20)

    longueur_ouvrage = _safe_float(
        metrics.get("Longueur de l'ouvrage (m)")
        or app_params.get("longueur_ouvrage")
        or app_params.get("plate_forme")
        or 12.0
    )

    return {
        "nom_fichier":          app_params.get("nom_fichier", "DALOT01"),
        "ouverture":            _safe_float(app_params.get("ouverture",           2.0)),
        "gabarit":              _safe_float(app_params.get("gabarit",             2.0)),
        "epaisseur":            epaisseur,
        "longueur_ouvrage":     longueur_ouvrage,
        "hauteur_parafouille":  _safe_float(app_params.get("hauteur_parafouille", 1.0)),
        "angle_biais":          _safe_float(app_params.get("angle_biais",         90.0)),
    }
