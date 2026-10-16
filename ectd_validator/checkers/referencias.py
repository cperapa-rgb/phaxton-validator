"""Toda hoja apunta a un fichero existente dentro del paquete; todo fichero esta referenciado o es huerfano."""

from __future__ import annotations

from typing import List

from .comun import hallazgo, ficheros_documento, rel


def run(ctx, rule: dict) -> List[dict]:
    return _CHECKS[rule["params"]["check"]](ctx, rule)


def _existe(ctx, rule):
    out = []
    for leaf in ctx.leaves:
        if not leaf["href"]:
            out.append(hallazgo(rule, "leaf ID=%s" % (leaf["id"] or "(sin ID)"), "la hoja no tiene xlink:href"))
            continue
        p = ctx.resolver(leaf["href"])
        if p is None:
            out.append(hallazgo(rule, leaf["href"], "el href cae fuera del paquete"))
        elif not p.is_file():
            out.append(hallazgo(rule, leaf["href"], "el href apunta a un fichero que no existe"))
    return out


def _huerfanos(ctx, rule):
    referenciados = set()
    for leaf in ctx.leaves:
        p = ctx.resolver(leaf["href"])
        if p is not None:
            referenciados.add(p)
    return [hallazgo(rule, rel(ctx.root, p), "fichero huerfano: ninguna hoja del backbone lo referencia")
            for p in ficheros_documento(ctx.root) if p.resolve() not in referenciados]


_CHECKS = {"existe": _existe, "huerfanos": _huerfanos}
CHECKS = _CHECKS
