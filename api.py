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
        "engines_available": [
            (BINS_DIR / "CASIMPLE_WIN64.EXE").is_file(),
            (BINS_DIR / "CADOUBLE_WIN64.EXE").is_file(),
            (BINS_DIR / "CATRIPLE_WIN64.EXE").is_file(),
        ],
    }


@app.get("/api/debug")
def debug_wine():
    import subprocess
    cmds = [
        ["which", "wine"],
        ["which", "wine32"],
        ["which", "wine64"],
        ["wine", "--version"],
        ["ls", "-la", str(BINS_DIR)],
    ]
    results = {}
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            results[" ".join(cmd)] = {"stdout": r.stdout.strip(), "stderr": r.stderr.strip(), "code": r.returncode}
        except Exception as e:
            results[" ".join(cmd)] = str(e)
    return results


@app.get("/api/test_run")
def test_wine_run():
    import subprocess
    cmd = ["wine", str(BINS_DIR / "CASIMPLE_WIN64.EXE")]
    try:
        p = subprocess.Popen(
            cmd,
            cwd=str(BINS_DIR),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        inputs = b"DALOT01\r\n1\r\n\r\n\r\n\r\n"
        out, err = p.communicate(input=inputs, timeout=10)
        return {
            "stdout": out.decode("latin1", errors="replace"),
            "stderr": err.decode("latin1", errors="replace"),
            "code": p.returncode,
        }
    except Exception as e:
        return {"error": str(e)}


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
