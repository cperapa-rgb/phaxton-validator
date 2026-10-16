"""Utilidades compartidas por los checkers (sin dependencias fuera del paquete)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, List

# Ficheros de la secuencia que no son documentos del backbone.
SISTEMA = {"index.xml", "index-md5.txt"}


class NoAplicable(Exception):
    """El checker no tiene material que inspeccionar: la regla NO se ejecuto (nunca cuenta como verde)."""


def hallazgo(rule: dict, evidencia: str, mensaje: str) -> dict:
    return {"regla": rule["id"], "codigo_oficial": rule.get("codigo_oficial"), "severidad": rule["severidad"],
            "evidencia": evidencia, "mensaje": mensaje, "accion": "pendiente"}


def recorrer(root: Path) -> Iterator[Path]:
    """Todas las rutas (ficheros y carpetas) bajo root, orden estable."""
    for p in sorted(root.rglob("*")):
        yield p


def rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def ficheros_documento(root: Path) -> List[Path]:
    """Ficheros que deberian estar referenciados por una hoja: todo menos index.xml, index-md5.txt y util/."""
    out = []
    for p in recorrer(root):
        if not p.is_file():
            continue
        r = rel(root, p)
        if r in SISTEMA or r.startswith("util/"):
            continue
        out.append(p)
    return out
