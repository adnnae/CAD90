"""CAD90Pro Web — Interface web pour le calcul et ferraillage des dalots en béton armé."""

from pathlib import Path
import tempfile
import streamlit as st
import pandas as pd

from core.models import StructureType, ParameterSchema
from core.generator import DataFileGenerator
from core.runner import EngineRunner
from core.parser import parse_engine_report
from core.pdf_export import export_pdf_report
from core.bq_export import export_bq_excel, HAS_OPENPYXL
from ui.web_sketch import generate_dalot_svg

# Configuration de la page
st.set_page_config(
    page_title="CAD90Pro — Dalots & Ponts Cadres",
    page_icon="🌉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Thème CSS moderne
st.markdown(
    """
    <style>
    .main-title {
        color: #1E3A5F;
        font-size: 26px;
        font-weight: 700;
        margin-bottom: 2px;
    }
    .sub-title {
        color: #64748B;
        font-size: 14px;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    .metric-val {
        font-size: 20px;
        font-weight: 700;
        color: #2563EB;
    }
    .metric-lbl {
        font-size: 12px;
        color: #64748B;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

BASE_DIR = Path(__file__).resolve().parent
BINS_DIR = BASE_DIR / "legacy_bins"
SCHEMA_PATH = BASE_DIR / "config" / "parameters.json"

schema = ParameterSchema(SCHEMA_PATH)
generator = DataFileGenerator()
runner = EngineRunner(BINS_DIR)

# En-tête
st.markdown('<div class="main-title">CAD90Pro — Calcul de Cadres & Dalots en Béton Armé</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Logiciel d\'ingénierie des ouvrages d\'art hydrauliques & routiers (Moteur SETRA CAD90)</div>', unsafe_allow_html=True)

# Barre latérale : Paramètres
st.sidebar.header("📐 Paramètres de l'Ouvrage")

st_type_choice = st.sidebar.selectbox(
    "Type de dalot",
    options=[StructureType.SIMPLE, StructureType.DOUBLE, StructureType.TRIPLE],
    format_func=lambda x: x.label,
)

nom_fichier = st.sidebar.text_input("Nom du fichier / Référence", value="DALOT01", max_chars=8)

st.sidebar.subheader("Géométrie (m)")
col_g1, col_g2 = st.sidebar.columns(2)
with col_g1:
    ouverture = st.number_input("Ouverture (m)", min_value=0.5, max_value=20.0, value=2.0, step=0.1)
with col_g2:
    gabarit = st.number_input("Gabarit (m)", min_value=0.5, max_value=20.0, value=2.0, step=0.1)

plate_forme = st.sidebar.number_input("Largeur plate-forme (m)", min_value=1.0, max_value=50.0, value=10.0, step=0.5)
poids_sup = st.sidebar.number_input("Poids superstructures (t/m²)", min_value=0.0, max_value=5.0, value=0.24, step=0.01)

st.sidebar.subheader("Remblais & Épaisseurs")
nb_cas = st.sidebar.number_input("Nombre de cas de remblai", min_value=1, max_value=6, value=1, step=1)

hauteurs_remblai = []
epaisseurs_cadre = []

for i in range(int(nb_cas)):
    c_r1, c_r2 = st.sidebar.columns(2)
    with c_r1:
        h = st.number_input(f"H. remblai {i+1} (m)", min_value=0.0, max_value=30.0, value=1.0 + i * 0.5, step=0.1, key=f"h_{i}")
        hauteurs_remblai.append(h)
    with c_r2:
        ep = st.number_input(f"Épaisseur {i+1} (m)", min_value=0.1, max_value=3.0, value=0.20 + i * 0.05, step=0.05, key=f"ep_{i}")
        epaisseurs_cadre.append(ep)

with st.sidebar.expander("⚙️ Options avancées"):
    charges_rout = st.selectbox("Charges routières", options=[1, 0], format_func=lambda x: "Routières (A(L) + Bc + Bt + Br)" if x == 1 else "Sans charges routières")
    indice_ferr = st.selectbox("Ferraillage", options=[1, 0], format_func=lambda x: "Calcul automatique du ferraillage" if x == 1 else "Moments uniquement")
    indice_res = st.selectbox("Résistance du sol", options=[0, 1], format_func=lambda x: "Non vérifiée / standard" if x == 0 else "Vérification sol élastique")
    contrainte_sol = st.number_input("Contrainte admissible sol (bars)", min_value=0.1, max_value=20.0, value=2.0, step=0.1)

# Construction du dictionnaire de paramètres
params = {
    "nom_fichier": nom_fichier or "DALOT01",
    "ouverture": ouverture,
    "gabarit": gabarit,
    "plate_forme": plate_forme,
    "poids_superstructures": poids_sup,
    "nb_cas_remblai": int(nb_cas),
    "hauteurs_remblai": hauteurs_remblai,
    "epaisseurs_cadre": epaisseurs_cadre,
    "charges_routieres": charges_rout,
    "indice_ferraillage": indice_ferr,
    "indice_resistance": indice_res,
    "contrainte_sol": contrainte_sol,
    "portance_minimale": 0.0,
    "remblai_type": 0,
    "type_fissuration": 0,
    "coeff_majoration_dynamique": 1.0,
    "angle_frottement_interne": 30.0,
    "poids_volumique_terre": 2.0,
    "poids_volumique_beton": 2.5,
    "largeur_roulante": 7.0,
    "classe_pont": 1,
    "largeur_trottoir_gauche": 1.5,
    "largeur_trottoir_droit": 1.5,
    "charge_trottoir": 0.15,
    "presence_remblai": 1,
    "epaisseur_chaussee": 0.10,
    "contrainte_traction_acier": 400.0,
    "resistance_compression_beton": 25.0,
    "enrobage": 3.0,
}

# Zone principale
col_sketch, col_actions = st.columns([3, 1])

with col_sketch:
    st.subheader("Coupe Transversale Estimée")
    svg_code = generate_dalot_svg(st_type_choice, params)
    st.markdown(svg_code, unsafe_allow_html=True)

with col_actions:
    st.subheader("Action")
    st.write("Vérifiez les cotes et lancez le calcul automatique.")
    calculate_btn = st.button("🚀 Lancer le Calcul CAD90", type="primary", use_container_width=True)

# Déroulement du calcul
if calculate_btn:
    with st.spinner("Exécution du moteur de calcul Fortran CAD90 en cours..."):
        with tempfile.TemporaryDirectory() as tmp_work_dir:
            work_dir = Path(tmp_work_dir)
            try:
                # 1. Génération du fichier de cartes Fortran
                data_file = generator.generate(st_type_choice, params, work_dir)
                
                # 2. Exécution du moteur 64 bits
                res = runner.run_engine(st_type_choice, data_file, work_dir)
                
                if not res.success and not res.stdout:
                    st.error(f"Erreur d'exécution : {res.error_message}")
                else:
                    # 3. Parsing des résultats
                    parsed = parse_engine_report(res.stdout)
                    st.session_state["calc_results"] = res
                    st.session_state["parsed_results"] = parsed
                    st.session_state["calc_params"] = params
                    st.session_state["calc_st_type"] = st_type_choice
                    st.success("Calcul terminé avec succès !")
            except Exception as exc:
                st.error(f"Une erreur s'est produite lors du calcul : {exc}")

# Affichage des résultats s'ils sont en session
if "parsed_results" in st.session_state:
    parsed = st.session_state["parsed_results"]
    res = st.session_state["calc_results"]
    calc_params = st.session_state["calc_params"]
    calc_st_type = st.session_state["calc_st_type"]

    st.markdown("---")
    st.header("📊 Résultats & Ferraillage")

    # Métriques clés
    if parsed.metrics:
        m_cols = st.columns(min(4, len(parsed.metrics)))
        for idx, (k, v) in enumerate(list(parsed.metrics.items())[:4]):
            with m_cols[idx % 4]:
                st.markdown(
                    f'<div class="metric-card"><div class="metric-lbl">{k}</div><div class="metric-val">{v}</div></div>',
                    unsafe_allow_html=True,
                )

    # Onglets de restitution
    tab_arm, tab_etr, tab_mom, tab_pdf, tab_raw = st.tabs([
        "Armatures Principales",
        "Étriers & Épingles",
        "Moments Fléchissants",
        "Téléchargements (PDF & Excel)",
        "Journal Moteur Brut",
    ])

    with tab_arm:
        if parsed.armatures:
            data = [
                {
                    "Repère / Acier": r.acier,
                    "Section (cm²/m)": r.sec,
                    "Diamètre (mm)": r.d,
                    "Espacement (cm)": r.ec,
                    "Longueur (m)": r.longueur,
                    "Nombre de barres": r.nombre,
                }
                for r in parsed.armatures
            ]
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        else:
            st.info("Aucune armature principale détectée dans ce cas.")

    with tab_etr:
        if parsed.etriers:
            data_etr = [
                {
                    "Nature": e.nature,
                    "Section": e.sec,
                    "Diamètre (mm)": e.d,
                    "Esp. Long.": e.ecl,
                    "Esp. Transv.": e.ect,
                    "Distance": e.dist,
                    "Longueur": e.longueur,
                    "Nombre": e.nombre,
                }
                for e in parsed.etriers
            ]
            st.dataframe(pd.DataFrame(data_etr), use_container_width=True)
        else:
            st.info("Aucun étrier détecté.")

    with tab_mom:
        if parsed.moments:
            data_mom = [
                {
                    "Zone de l'ouvrage": m.zone,
                    "Extremum": m.extremum,
                    "Ch. Permanente": m.ch_perm,
                    "Ch. Routière": m.ch_rout,
                    "Surch. Remblai": m.sch_remb,
                    "Combinaison Max": m.combinaison,
                }
                for m in parsed.moments
            ]
            st.dataframe(pd.DataFrame(data_mom), use_container_width=True)
        else:
            st.info("Aucun moment fléchissant calculé.")

    with tab_pdf:
        st.subheader("Exporter les rapports de calcul")
        c_p1, c_p2 = st.columns(2)

        with c_p1:
            st.markdown("### 📄 Note de Calcul PDF")
            st.write("Génère une note technique A4 conforme avec coupe transversale et tableaux de ferraillage.")
            with tempfile.TemporaryDirectory() as p_tmp:
                pdf_path = Path(p_tmp) / f"Note_Calcul_{calc_params['nom_fichier']}.pdf"
                export_pdf_report(pdf_path, calc_st_type, calc_params, parsed)
                if pdf_path.is_file():
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            label="📥 Télécharger la Note PDF",
                            data=f.read(),
                            file_name=pdf_path.name,
                            mime="application/pdf",
                            use_container_width=True,
                        )

        with c_p2:
            st.markdown("### 📊 Bordereau Quantitatif (Excel BQ)")
            st.write("Génère l'avant-métré des armatures avec les formules de calcul et poids d'acier.")
            if HAS_OPENPYXL:
                with tempfile.TemporaryDirectory() as b_tmp:
                    excel_path = Path(b_tmp) / f"Metre_Ferraillage_{calc_params['nom_fichier']}.xlsx"
                    ok, msg = export_bq_excel(excel_path, calc_st_type, calc_params, parsed)
                    if ok and excel_path.is_file():
                        with open(excel_path, "rb") as f:
                            st.download_button(
                                label="📥 Télécharger le Fichier Excel (BQ)",
                                data=f.read(),
                                file_name=excel_path.name,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                            )
                    else:
                        st.warning(f"Export Excel : {msg}")
            else:
                st.warning("openpyxl non installé.")

    with tab_raw:
        st.text_area("Texte brut issu du moteur CAD90", value=res.stdout, height=350)
