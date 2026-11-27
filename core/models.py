"""Domain models and parameter schema loader."""

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List


class StructureType(str, Enum):
    SIMPLE = "simple"
    DOUBLE = "double"
    TRIPLE = "triple"

    @property
    def label(self) -> str:
        return {
            StructureType.SIMPLE: "Dalot simple (1 alvéole)",
            StructureType.DOUBLE: "Dalot double (2 alvéoles)",
            StructureType.TRIPLE: "Dalot triple (3 alvéoles)",
        }[self]

    @property
    def engine_filename(self) -> str:
        return {
            StructureType.SIMPLE: "CASIMPLE_WIN64.EXE",
            StructureType.DOUBLE: "CADOUBLE_WIN64.EXE",
            StructureType.TRIPLE: "CATRIPLE_WIN64.EXE",
        }[self]


@dataclass
class ExecutionResult:
    """Result of running a legacy calculation engine."""
    success: bool
    structure_type: StructureType
    engine_path: str
    work_dir: str
    data_file_path: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    generated_files: List[Path] = field(default_factory=list)
    error_message: str = ""


class ParameterSchema:
    """Loads and filters parameter definitions from parameters.json."""

    def __init__(self, schema_path: Path):
        self.schema_path = schema_path
        with schema_path.open("r", encoding="utf-8") as f:
            self._raw: Dict[str, Any] = json.load(f)

    @property
    def sections(self) -> List[Dict[str, Any]]:
        return self._raw.get("sections", [])

    def sections_for(self, structure_type: StructureType) -> List[Dict[str, Any]]:
        """Return only sections and fields applicable to the given structure type."""
        result = []
        for sec in self.sections:
            fields = [
                fld for fld in sec.get("fields", [])
                if structure_type.value in fld.get("applies_to", ["simple", "double", "triple"])
            ]
            if fields:
                result.append({
                    "id": sec["id"],
                    "title": sec["title"],
                    "fields": fields,
                })
        return result
