"""CAD90Pro Web — Clone 100% fidèle de l'application de bureau Windows CAD90Pro."""

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
from core.results import format_execution_summary
from ui.web_sketch import generate_dalot_svg_exact

# Configuration pleine largeur
st.set_page_config(
    page_title="CAD90Pro — Ponts Cadres en Béton Armé",
    page_icon="🌉",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Style CSS pour répliquer au pixel près le thème clair de CAD90Pro
st.markdown(
    """
    <style>
    /* Reset & Clean Streamlit */
    #MainMenu, header, footer { visibility: hidden; }
    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 2rem !important;
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        max-width: 100% !important;
        background-color: #F8FAFC;
    }
    
    /* Top Accent Stripe */
    .top-accent {
        height: 3px;
        background-color: #2563EB;
        width: 100%;
        margin-bottom: 0px;
    }

    /* En-tête Principal */
    .cad90-header {
        background-color: #1E3A5F;
        padding: 10px 18px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #162032;
    }
    .cad90-logo-title {
        font-family: 'Segoe UI', Tahoma, sans-serif;
        font-size: 20px;
        font-weight: 700;
        color: #FFFFFF;
        display: inline-block;
    }
    .cad90-logo-pro {
        color: #93C5FD;
        font-weight: 700;
        font-size: 20px;
    }
    .cad90-badge {
        background-color: #2563EB;
        color: #FFFFFF;
        font-size: 9px;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 3px;
        margin-left: 8px;
        vertical-align: middle;
    }
    .cad90-subtitle {
        color: #85A7C8;
        font-size: 11px;
        font-family: 'Segoe UI', Tahoma, sans-serif;
        margin-top: 2px;
    }

    /* Panneaux des 3 colonnes */
    .panel-header {
        background-color: #1E3A5F;
        color: #FFFFFF;
        font-family: 'Segoe UI', Tahoma, sans-serif;
        font-size: 11px;
        font-weight: 700;
        padding: 7px 12px;
        letter-spacing: 0.5px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    .panel-body {
        background-color: #FFFFFF;
        border: 1px solid #CBD5E1;
        border-top: none;
        padding: 10px 12px;
        min-height: 580px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    /* Sections du formulaire */
    .section-title {
        background-color: #F1F5F9;
        color: #1E3A5F;
        font-family: 'Segoe UI', sans-serif;
        font-size: 11px;
        font-weight: 700;
        padding: 5px 8px;
        margin-top: 10px;
        margin-bottom: 8px;
        border-left: 3px solid #2563EB;
    }

    /* Cartes métriques sous le croquis */
    .metric-box {
        background-color: #EFF6FF;
        border: 1px solid #CBD5E1;
        border-radius: 4px;
        padding: 6px 8px;
        text-align: center;
    }
    .metric-lbl {
        font-size: 9px;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
    }
    .metric-val {
        font-size: 16px;
        font-weight: 700;
        color: #0F172A;
        margin: 2px 0;
    }
    .metric-unit {
        font-size: 9px;
        color: #64748B;
    }

    /* Barre d'état inférieure */
    .status-bar {
        background-color: #1E3A5F;
        color: #FFFFFF;
        padding: 8px 16px;
        font-size: 12px;
        font-family: 'Segoe UI', sans-serif;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-radius: 4px;
        margin-top: 10px;
    }

    /* Styliser les inputs Streamlit pour être compacts comme Tkinter */
    div[data-baseweb="input"] {
        min-height: 30px !important;
        font-size: 12px !important;
    }
    .stNumberInput, .stTextInput, .stSelectbox {
        margin-bottom: -10px !important;
    }
    label {
        font-size: 11px !important;
        color: #334155 !important;
        font-weight: 500 !important;
    }
    </style>
    <div class="top-accent"></div>
    """,
    unsafe_allow_html=True,
)

BASE_DIR = Path(__file__).resolve().parent
BINS_DIR = BASE_DIR / "legacy_bins"
SCHEMA_PATH = BASE_DIR / "config" / "parameters.json"

schema = ParameterSchema(SCHEMA_PATH)
generator = DataFileGenerator()
runner = EngineRunner(BINS_DIR)

# Gestion du type d'ouvrage en session
if "structure_type" not in st.session_state:
    st.session_state["structure_type"] = StructureType.SIMPLE

st_type = st.session_state["structure_type"]

# ══════════════════════════════════════════════════════════════════
# EN-TÊTE CAD90Pro
# ══════════════════════════════════════════════════════════════════
h_col1, h_col2, h_col3 = st.columns([4, 4.5, 1.5])

with h_col1:
    st.markdown(
        """
        <div style="background-color:#1E3A5F; padding:10px 14px; border-radius:4px; height:100%;">
            <span class="cad90-logo-title">CAD90</span><span class="cad90-logo-pro">Pro</span>
            <span class="cad90-badge">v2</span>
            <div class="cad90-subtitle">Dimensionnement des Ponts Cadres en Béton Armé</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with h_col2:
    st.markdown('<div style="background-color:#1E3A5F; padding:6px 12px; border-radius:4px; height:100%;">', unsafe_allow_html=True)
    st.caption("TYPE D'OUVRAGE")
    t_btn1, t_btn2, t_btn3 = st.columns(3)
    with t_btn1:
        if st.button("Dalot Simple", type="primary" if st_type == StructureType.SIMPLE else "secondary", use_container_width=True):
            st.session_state["structure_type"] = StructureType.SIMPLE
            st.rerun()
    with t_btn2:
        if st.button("Dalot Double", type="primary" if st_type == StructureType.DOUBLE else "secondary", use_container_width=True):
            st.session_state["structure_type"] = StructureType.DOUBLE
            st.rerun()
    with t_btn3:
        if st.button("Dalot Triple", type="primary" if st_type == StructureType.TRIPLE else "secondary", use_container_width=True):
            st.session_state["structure_type"] = StructureType.TRIPLE
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with h_col3:
    st.markdown('<div style="background-color:#1E3A5F; padding:12px 10px; border-radius:4px; height:100%; text-align:center;">', unsafe_allow_html=True)
    calc_pressed = st.button("▶  Calculer", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# CORPS EN 3 COLONNES
# ══════════════════════════════════════════════════════════════════
col_params, col_sketch, col_results = st.columns([3.3, 4.0, 4.7])

# ── COLONNE 1 : PARAMÈTRES DE L'OUVRAGE ─────────────────────────
with col_params:
    st.markdown('<div class="panel-header">PARAMÈTRES DE L\'OUVRAGE</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="section-title">GÉNÉRALITÉS & GÉOMÉTRIE</div>', unsafe_allow_html=True)
        nom_fichier = st.text_input("Nom du fichier de données (8 car. max)", value="DALOT01", max_chars=8)
        
        c_ouv, c_gab = st.columns(2)
        with c_ouv:
            ouv_val = st.number_input("Ouverture (m)", value=2.0, min_value=0.1, step=0.1, format="%.2f")
        with c_gab:
            gab_val = st.number_input("Gabarit (m)", value=2.0, min_value=0.1, step=0.1, format="%.2f")
            
        c_pf, c_ps = st.columns(2)
        with c_pf:
            pf_val = st.number_input("Plate-forme routière (m)", value=10.0, min_value=1.0, step=0.5, format="%.2f")
        with c_ps:
            ps_val = st.number_input("Poids superstructures (t/m²)", value=0.24, min_value=0.0, step=0.01, format="%.2f")

        nb_cas_val = st.number_input("Nombre de cas de hauteurs de remblai (1 à 21)", value=1, min_value=1, max_value=21, step=1)
        
        st.caption("Hauteurs de remblai & épaisseurs par cas :")
        hauteurs_list = []
        epaisseurs_list = []
        for c_idx in range(int(nb_cas_val)):
            c_h, c_e = st.columns(2)
            with c_h:
                h_c = st.number_input(f"Cas {c_idx+1} Remblai (m)", value=1.0 + c_idx*0.5, step=0.1, key=f"cas_h_{c_idx}")
                hauteurs_list.append(float(h_c))
            with c_e:
                e_c = st.number_input(f"Cas {c_idx+1} Épaisseur (m)", value=0.20 + c_idx*0.05, step=0.05, key=f"cas_e_{c_idx}")
                epaisseurs_list.append(float(e_c))

        st.markdown('<div class="section-title">CARACTÉRISTIQUES DU REMBLAI</div>', unsafe_allow_html=True)
        r_c1, r_c2 = st.columns(2)
        with r_c1:
            dens_remb = st.number_input("Densité du remblai y (t/m³)", value=1.8, step=0.1)
            c1_val = st.number_input("Coeff. poussée minimal c1", value=0.25, step=0.05)
            maj_c1_val = st.number_input("Majoration poids lié à c1", value=1.3, step=0.05)
            pente_h_val = st.number_input("Pente remblai - distance H", value=1.0, step=0.1)
        with r_c2:
            surch_remb = st.number_input("Surcharge de remblai (t/m²)", value=1.0, step=0.1)
            c2_val = st.number_input("Coeff. poussée maximal c2", value=0.50, step=0.05)
            maj_c2_val = st.number_input("Majoration poids lié à c2", value=1.4, step=0.05)
            pente_v_val = st.number_input("Pente remblai - distance V", value=1.0, step=0.1)

        st.markdown('<div class="section-title">MATÉRIAUX (BÉTON ARMÉ & ACIERS)</div>', unsafe_allow_html=True)
        m_c1, m_c2 = st.columns(2)
        with m_c1:
            fc_adm = st.number_input("Contrainte adm. comp. béton (kg/cm²)", value=135.0, step=5.0)
            fc_ref = st.number_input("Contrainte réf. béton (kg/cm²)", value=5.8, step=0.1)
            fe_adm = st.number_input("Contrainte traction acier (kg/cm²)", value=2800.0, step=100.0)
            dens_beton = st.number_input("Densité du béton (t/m³)", value=2.50, step=0.05)
            l_barre = st.number_input("Longueur barre (m)", value=12.0, step=1.0)
        with m_c2:
            fc_eco = st.number_input("Contrainte comp. éco. béton (kg/cm²)", value=100.0, step=5.0)
            fe_etr = st.number_input("Contrainte adm. étriers (kg/cm²)", value=2800.0, step=100.0)
            poisson_val = st.number_input("Coeff. de Poisson", value=0.15, step=0.01)
            equiv_val = st.number_input("Équivalence acier/béton", value=15.0, step=1.0)
            enrob_val = st.number_input("Enrobage des aciers (cm)", value=3.0, step=0.5)

        st.markdown('<div class="section-title">OPTIONS DE CALCUL & SOL</div>', unsafe_allow_html=True)
        ch_rout_sel = st.selectbox("Charges routières", options=[1, 0], format_func=lambda x: "Routières (A(L) + Bc + Bt + Br)" if x == 1 else "Sans charges routières")
        ind_ferr_sel = st.selectbox("Indice ferraillage", options=[1, 0], format_func=lambda x: "Ferraillage automatique" if x == 1 else "Moments uniquement")
        ind_res_sel = st.selectbox("Indice résistance sol", options=[0, 1], format_func=lambda x: "Non vérifiée / standard" if x == 0 else "Sol élastique")
        sol_adm_val = st.number_input("Contrainte adm. sol (bars)", value=2.0, step=0.1)

# Préparation du dictionnaire de paramètres complet
params = {}
for sec in schema.sections_for(st_type):
    for fld in sec.get("fields", []):
        params[fld["id"]] = fld.get("default")

params.update({
    "nom_fichier": nom_fichier or "DALOT01",
    "ouverture": float(ouv_val),
    "gabarit": float(gab_val),
    "plate_forme": float(pf_val),
    "poids_superstructures": float(ps_val),
    "nb_cas_remblai": int(nb_cas_val),
    "hauteurs_remblai": hauteurs_list,
    "epaisseurs_cadre": epaisseurs_list,
    "densite_remblai": float(dens_remb),
    "c1": float(c1_val),
    "c2": float(c2_val),
    "maj_c1": float(maj_c1_val),
    "maj_c2": float(maj_c2_val),
    "surcharge_remblai": float(surch_remb),
    "pente_horiz": float(pente_h_val),
    "pente_vert": float(pente_v_val),
    "contrainte_beton_adm": float(fc_adm),
    "contrainte_beton_eco": float(fc_eco),
    "contrainte_beton_ref": float(fc_ref),
    "contrainte_acier_adm": float(fe_adm),
    "contrainte_etrier_adm": float(fe_etr),
    "densite_beton": float(dens_beton),
    "poisson": float(poisson_val),
    "longueur_barre": float(l_barre),
    "equiv_acier_beton": float(equiv_val),
    "enrobage": float(enrob_val),
    "charges_routieres": int(ch_rout_sel),
    "indice_ferraillage": int(ind_ferr_sel),
    "indice_resistance": int(ind_res_sel),
    "contrainte_sol": float(sol_adm_val),
})

# Exécution du calcul si le bouton "Calculer" a été cliqué
if calc_pressed:
    with st.spinner("Calcul en cours — veuillez patienter..."):
        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir)
            try:
                data_file = generator.generate(st_type, params, work_dir)
                exec_res = runner.run_engine(st_type, data_file, work_dir)
                if exec_res.success or exec_res.stdout:
                    parsed = parse_engine_report(exec_res.stdout)
                    st.session_state["calc_results"] = exec_res
                    st.session_state["parsed_results"] = parsed
                    st.session_state["active_params"] = params
                else:
                    st.error(f"Erreur d'exécution du moteur : {exec_res.error_message}")
            except Exception as exc:
                st.error(f"Erreur de calcul : {exc}")

parsed_data = st.session_state.get("parsed_results")
exec_data = st.session_state.get("calc_results")

# ── COLONNE 2 : CROQUIS & MODÉLISATION ──────────────────────────
with col_sketch:
    st.markdown('<div class="panel-header">CROQUIS & MODÉLISATION</div>', unsafe_allow_html=True)
    with st.container(border=True):
        # Rendu SVG identique à l'IHM Windows
        svg_code = generate_dalot_svg_exact(st_type, params, parsed_data, W=520, H=420)
        st.markdown(svg_code, unsafe_allow_html=True)
        
        st.markdown("<hr style='margin:10px 0; border:none; border-top:1px solid #CBD5E1;'>", unsafe_allow_html=True)
        
        # Bande d'efforts clés (4 cartes métriques identiques)
        metrics = parsed_data.metrics if parsed_data else {}
        m1, m2, m3, m4 = st.columns(4)
        
        with m1:
            v1 = metrics.get("Effort tranchant max (T)", "—")
            st.markdown(f'<div class="metric-box"><div class="metric-lbl">Effort tranchant</div><div class="metric-val">{v1}</div><div class="metric-unit">T</div></div>', unsafe_allow_html=True)
        with m2:
            v2 = metrics.get("Moment transversal max (Tm/m)", "—")
            st.markdown(f'<div class="metric-box"><div class="metric-lbl">Moment trans. max</div><div class="metric-val">{v2}</div><div class="metric-unit">Tm/m</div></div>', unsafe_allow_html=True)
        with m3:
            v3 = metrics.get("Moment transversal min (Tm/m)", "—")
            st.markdown(f'<div class="metric-box"><div class="metric-lbl">Moment trans. min</div><div class="metric-val">{v3}</div><div class="metric-unit">Tm/m</div></div>', unsafe_allow_html=True)
        with m4:
            v4 = metrics.get("Pression max au sol (T/m²)", "—")
            st.markdown(f'<div class="metric-box"><div class="metric-lbl">Pression au sol</div><div class="metric-val">{v4}</div><div class="metric-unit">T/m²</div></div>', unsafe_allow_html=True)

# ── COLONNE 3 : ANALYSE & RÉSULTATS ─────────────────────────────
with col_results:
    st.markdown('<div class="panel-header">ANALYSE & RÉSULTATS</div>', unsafe_allow_html=True)
    with st.container(border=True):
        res_tab1, res_tab2, res_tab3, res_tab4, res_tab5 = st.tabs([
            "Moments & Efforts",
            "Ferraillage",
            "Rapport natif",
            "Résumé",
            "Fichiers générés",
        ])

        with res_tab1:
            if parsed_data and parsed_data.moments:
                df_moments = pd.DataFrame([
                    {
                        "Zone": m.zone,
                        "Extremum": m.extremum,
                        "Ch. Perm.": m.ch_perm,
                        "Ch. Rout.": m.ch_rout,
                        "Sch. Remb.": m.sch_remb,
                        "Combinaison": m.combinaison,
                    }
                    for m in parsed_data.moments
                ])
                st.dataframe(df_moments, use_container_width=True, hide_index=True)
            else:
                st.info("Lancez un calcul pour afficher les moments et efforts.")

        with res_tab2:
            if parsed_data and parsed_data.armatures:
                df_rebar = pd.DataFrame([
                    {
                        "Acier / Nature": r.acier,
                        "Section": r.sec,
                        "Diamètre": r.d,
                        "Espacement": r.ec,
                        "Longueur (m)": r.longueur,
                        "Nombre": r.nombre,
                    }
                    for r in parsed_data.armatures
                ])
                st.dataframe(df_rebar, use_container_width=True, hide_index=True)
            else:
                st.info("Lancez un calcul pour afficher la nomenclature de ferraillage.")

        with res_tab3:
            if exec_data and exec_data.stdout:
                st.text_area("Sortie écran moteur", value=exec_data.stdout, height=450)
            else:
                st.info("Le journal d'exécution apparaîtra ici.")

        with res_tab4:
            if exec_data and parsed_data:
                summary_text = format_execution_summary(exec_data, parsed_data)
                st.text_area("Résumé", value=summary_text, height=450)
            else:
                st.info("Le résumé d'exécution apparaîtra ici.")

        with res_tab5:
            if exec_data and exec_data.generated_files:
                for gf in exec_data.generated_files:
                    st.write(f"📁 {gf.name}")
            else:
                st.info("Aucun fichier généré pour le moment.")

# ══════════════════════════════════════════════════════════════════
# BARRE D'ÉTAT INFÉRIEURE
# ══════════════════════════════════════════════════════════════════
sb_col1, sb_col2, sb_col3, sb_col4, sb_col5 = st.columns([4, 1.5, 1.5, 1.5, 1.5])

with sb_col1:
    status_text = "● Calcul terminé" if parsed_data else "● Prêt"
    status_color = "#16A34A" if parsed_data else "#2563EB"
    st.markdown(f'<div style="background-color:#1E3A5F; padding:8px 12px; border-radius:4px; color:#FFFFFF; font-size:12px;"><span style="color:{status_color}; font-size:14px;">●</span> {status_text}</div>', unsafe_allow_html=True)

with sb_col2:
    # Génération Données
    with tempfile.TemporaryDirectory() as d_tmp:
        df_p = Path(d_tmp) / params["nom_fichier"]
        generator.generate(st_type, params, Path(d_tmp))
        if df_p.is_file():
            with open(df_p, "rb") as f:
                st.download_button("Générer données", data=f.read(), file_name=df_p.name, use_container_width=True)

with sb_col3:
    # Exporter BQ Excel
    if parsed_data and HAS_OPENPYXL:
        with tempfile.TemporaryDirectory() as b_tmp:
            ex_p = Path(b_tmp) / f"Metre_Ferraillage_{params['nom_fichier']}.xlsx"
            ok, _ = export_bq_excel(ex_p, st_type, params, parsed_data)
            if ok and ex_p.is_file():
                with open(ex_p, "rb") as f:
                    st.download_button("Avant-métré Excel", data=f.read(), file_name=ex_p.name, use_container_width=True)
    else:
        st.button("Avant-métré Excel", disabled=True, use_container_width=True)

with sb_col4:
    # Exporter TXT
    if exec_data and exec_data.stdout:
        st.download_button("Exporter TXT", data=exec_data.stdout, file_name=f"{params['nom_fichier']}_resultat.txt", use_container_width=True)
    else:
        st.button("Exporter TXT", disabled=True, use_container_width=True)

with sb_col5:
    # Exporter PDF
    if parsed_data:
        with tempfile.TemporaryDirectory() as p_tmp:
            pdf_p = Path(p_tmp) / f"Note_Calcul_{params['nom_fichier']}.pdf"
            export_pdf_report(pdf_p, st_type, params, parsed_data)
            if pdf_p.is_file():
                with open(pdf_p, "rb") as f:
                    st.download_button("Exporter PDF", data=f.read(), file_name=pdf_p.name, use_container_width=True)
    else:
        st.button("Exporter PDF", disabled=True, use_container_width=True)
