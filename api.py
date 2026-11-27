"""API REST pour l'exécution sécurisée et isolée des moteurs de calcul CAD90 sous Render (Wine64)."""

from pathlib import Path
import tempfile
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.models import StructureType
from core.generator import DataFileGenerator
from core.runner import EngineRunner

app = FastAPI(
    title="CAD90 Engine Server",
    description="Serveur cloud privé d'exécution des moteurs de calcul patrimoniaux CAD90",
    version="2.0.0",
)

# Autoriser les requêtes cross-origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
BINS_DIR = BASE_DIR / "legacy_bins"

generator = DataFileGenerator()
runner = EngineRunner(BINS_DIR)


class CalculationRequest(BaseModel):
    structure_type: str  # "simple", "double", "triple"
    params: Dict[str, Any]


class CalculationResponse(BaseModel):
    success: bool
    stdout: str
    exit_code: int = 0
    error_message: str = ""
    file_contents: Dict[str, str] = {}


@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "CAD90 Calculation Engine Server",
        "commit": "debug-wine",
        "engines_available": [
            (BINS_DIR / "CASIMPLE_WIN64.EXE").is_file(),
            (BINS_DIR / "CADOUBLE_WIN64.EXE").is_file(),
            (BINS_DIR / "CATRIPLE_WIN64.EXE").is_file(),
        ],
    }


@app.get("/api/debug-run")
def debug_run():
    import subprocess, os, tempfile, shutil
    engine_path = BINS_DIR / "CASIMPLE_WIN64.EXE"
    with tempfile.TemporaryDirectory() as td:
        tw = Path(td)
        # copy sample DALOT01 if present or generate dummy
        data_file = tw / "DALOT01"
        generator.generate(StructureType.SIMPLE, {
            "nom_fichier": "DALOT01", "ouverture": 2.0, "gabarit": 2.0,
            "plate_forme": 10.0, "poids_superstructures": 0.24,
            "nb_cas_remblai": 1, "hauteurs_remblai": [1.0], "epaisseurs_cadre": [0.20],
            "densite_remblai": 1.8, "c1": 0.25, "c2": 0.5, "maj_c1": 1.3, "maj_c2": 1.4,
            "surcharge_remblai": 1.0, "pente_horiz": 1.0, "pente_vert": 1.0,
            "contrainte_beton_adm": 135.0, "contrainte_beton_eco": 100.0, "contrainte_beton_ref": 5.8,
            "contrainte_acier_adm": 2800.0, "contrainte_etrier_adm": 2800.0, "densite_beton": 2.5,
            "poisson": 0.15, "longueur_barre": 12.0, "equiv_acier_beton": 15.0, "enrobage": 3.0,
            "charges_routieres": 1, "indice_ferraillage": 1, "indice_resistance": 0, "contrainte_sol": 2.0,
        }, tw)
        
        env = dict(os.environ)
        env["WINEDEBUG"] = "-all"
        env["DISPLAY"] = ":99"
        
        # Test 1: Popen with stdin=subprocess.PIPE
        stdin_data = b"DALOT01\r\n1\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n\r\n"
        proc = subprocess.Popen(
            ["wine", str(engine_path.resolve())],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(tw),
            env=env,
        )
        try:
            out, err = proc.communicate(input=stdin_data, timeout=10)
            files = [f.name for f in tw.iterdir()]
            result_txt = (tw / "DALOT01_resultat.txt").read_text(errors="ignore") if (tw / "DALOT01_resultat.txt").is_file() else ""
            return {
                "exit_code": proc.returncode,
                "stdout_len": len(out),
                "stdout_sample": out.decode("latin1", errors="ignore")[:500],
                "stderr": err.decode("latin1", errors="ignore")[:500],
                "files_in_temp": files,
                "result_txt_len": len(result_txt),
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            return {"error": "Timeout expired in communicate"}
        except Exception as e:
            return {"error": str(e)}
    import subprocess, shutil, os
    res = {}
    res["wine_path"] = shutil.which("wine")
    res["wine64_path"] = shutil.which("wine64")
    res["wineboot"] = shutil.which("wineboot")
    
    # Check wine version
    try:
        w_ver = subprocess.run(["wine", "--version"], capture_output=True, text=True, timeout=5)
        res["wine_version"] = w_ver.stdout.strip() or w_ver.stderr.strip()
    except Exception as e:
        res["wine_version_err"] = str(e)

    # Check xvfb
    res["xvfb_path"] = shutil.which("Xvfb")
    res["display_env"] = os.environ.get("DISPLAY")

    # Check test run of CASIMPLE_WIN64.EXE
    engine_path = BINS_DIR / "CASIMPLE_WIN64.EXE"
    res["engine_exists"] = engine_path.is_file()
    if engine_path.is_file():
        env = dict(os.environ)
        env["WINEDEBUG"] = "+all"
        try:
            p = subprocess.run(
                ["wine", str(engine_path.resolve())],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(BINS_DIR),
                env=env,
            )
            res["test_returncode"] = p.returncode
            res["test_stdout"] = p.stdout[:500]
            res["test_stderr"] = p.stderr[:1000]
        except Exception as e:
            res["test_run_err"] = str(e)
            
    return res


@app.post("/api/calculate", response_model=CalculationResponse)
def calculate(req: CalculationRequest):
    try:
        st_enum = StructureType(req.structure_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Type d'ouvrage invalide: {req.structure_type}. Choix valides: simple, double, triple",
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        work_dir = Path(tmp_dir)
        try:
            # 1. Génération du fichier de données Fortran
            data_file = generator.generate(st_enum, req.params, work_dir)

            # 2. Exécution du moteur sous Wine64
            res = runner.run_engine(st_enum, data_file, work_dir)

            # 3. Récupération des fichiers texte générés
            file_contents: Dict[str, str] = {}
            for f in res.generated_files:
                if f.is_file() and f.suffix.lower() in (".txt", "", ".dat"):
                    try:
                        file_contents[f.name] = f.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        pass

            return CalculationResponse(
                success=res.success or bool(res.stdout),
                stdout=res.stdout or "",
                exit_code=res.exit_code or 0,
                error_message=res.error_message or "",
                file_contents=file_contents,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Erreur interne de calcul: {exc}")
