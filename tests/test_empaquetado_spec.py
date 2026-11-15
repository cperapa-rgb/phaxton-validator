"""Todo fichero de spec/ y rules/ tiene que viajar en el paquete instalado (pip): una hoja de estilo que existe en el arbol y no en
la instalacion rompia a los consumidores en CI (15-nov-2026)."""
import fnmatch
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def test_package_data_cubre_todos_los_ficheros_de_spec_y_rules():
    patrones = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]["package-data"]["ectd_validator"]
    for carpeta in ("spec", "rules"):
        for f in (RAIZ / "ectd_validator" / carpeta).iterdir():
            if f.is_file() and f.name != "__pycache__":
                rel = f"{carpeta}/{f.name}"
                assert any(fnmatch.fnmatch(rel, p) for p in patrones), f"{rel} no esta en package-data: no viajaria en la instalacion"
