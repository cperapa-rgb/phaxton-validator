"""Estructura de carpetas y nombres segun ICH eCTD 3.2.2 (limites en rules/estructura.yaml, fuente en spec/)."""

from __future__ import annotations

import re
from typing import List

from .comun import hallazgo, recorrer, rel

NOMBRE = re.compile(r"^[a-z0-9-]+$")
RAIZ_PERMITIDA = {"index.xml", "index-md5.txt", "util", "m1", "m2", "m3", "m4", "m5"}


def run(ctx, rule: dict) -> List[dict]:
    return _CHECKS[rule["params"]["check"]](ctx, rule)


def _nombres(ctx, rule):
    out = []
    for p in recorrer(ctx.root):
        r = rel(ctx.root, p)
        if p.is_dir():
            partes = [p.name]
        else:
            partes = p.name.split(".")
            if len(partes) != 2:
                out.append(hallazgo(rule, r, "el fichero debe tener una y solo una extension (nombre.ext)"))
                continue
        for parte in partes:
            if not NOMBRE.fullmatch(parte):
                out.append(hallazgo(rule, r, f"caracteres no permitidos en {parte!r}: solo a-z, 0-9 y guion"))
        if len(p.name) > rule["params"]["max_nombre"]:
            out.append(hallazgo(rule, r, f"nombre de {len(p.name)} caracteres (maximo {rule['params']['max_nombre']})"))
    return out


def _ruta(ctx, rule):
    lim = rule["params"]["max_ruta"]
    return [hallazgo(rule, rel(ctx.root, p), f"ruta de {len(rel(ctx.root, p))} caracteres (maximo {lim})")
            for p in recorrer(ctx.root) if len(rel(ctx.root, p)) > lim]


def _raiz(ctx, rule):
    return [hallazgo(rule, p.name, "elemento inesperado en la raiz de la secuencia")
            for p in sorted(ctx.root.iterdir()) if p.name not in RAIZ_PERMITIDA]


_CHECKS = {"nombres": _nombres, "ruta": _ruta, "raiz": _raiz}
CHECKS = _CHECKS
