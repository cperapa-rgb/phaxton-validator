"""Coherencia SDTM <-> ADaM dentro del paquete: lo que un validador puede comprobar SIN licencia ni reglas ADaM ajenas.

Compara los datasets ADaM del paquete (ADNCA, ADPP) con los SDTM de los que dicen derivarse (DM, PC, EX, PP) en la MISMA carpeta
de estudio, leyendo todos con el lector XPT propio del validador (independiente de quien los escribio). No valida conformidad
CDISC (eso exige reglas ADaM que ningun motor libre trae): comprueba que los datos de los dos lados se cuentan la misma historia.

Sin ADaM, o sin el dataset SDTM contra el que se cruza, la regla NO se ejecuta (NoAplicable): nunca cuenta como verde. Un XPT
que no se puede leer es un hallazgo, no un silencio.
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .comun import NoAplicable, hallazgo, rel
from .stf import leer_xpt

ADAM = ("adnca", "adpp")
SDTM = ("dm", "pc", "ex", "pp")
MAX_POR_REGLA = 20          # un fallo sistematico no inunda el informe: se muestran N y se declara el total


def run(ctx, rule: dict) -> List[dict]:
    return _CHECKS[rule["params"]["check"]](ctx, rule)


def _estudio(carpeta: str) -> str:
    """Raiz del estudio: el layout de datos de la FDA separa SDTM (<estudio>/tabulations/sdtm) y ADaM (<estudio>/analysis/adam/datasets)
    en carpetas distintas; ambos pertenecen al mismo estudio. Fuera de ese layout, la carpeta del fichero es el estudio."""
    for sufijo in ("/tabulations/sdtm", "/analysis/adam/datasets"):
        if carpeta.endswith(sufijo):
            return carpeta[: -len(sufijo)]
    return carpeta


def _carpetas(ctx) -> Dict[str, Dict[str, Path]]:
    """carpeta -> {nombre sin extension en minuscula: ruta} de los .xpt de M4/M5 que son SDTM o ADaM conocidos."""
    out: Dict[str, Dict[str, Path]] = defaultdict(dict)
    for h in ctx.leaves:
        href = h["href"] or ""
        if not href.startswith(("m4/", "m5/")) or not href.lower().endswith(".xpt"):
            continue
        nombre = href.rsplit("/", 1)[-1][:-4].lower()
        if nombre not in ADAM + SDTM:
            continue
        p = ctx.resolver(href)
        if p is not None and p.is_file():
            out[_estudio(href.rsplit("/", 1)[0])][nombre] = p
    return out


def _leer(ctx, rule, p: Path, hallazgos: List[dict]) -> Optional[Tuple[List[str], List[dict]]]:
    try:
        return leer_xpt(p)
    except ValueError as e:
        hallazgos.append(hallazgo(rule, rel(ctx.root, p), "no se puede leer el XPT para cruzarlo: %s" % e))
        return None


def _iguales(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def _entero(v) -> Optional[int]:
    return None if v is None else int(round(v))


def _recortar(out: List[dict], rule, evidencia: str) -> List[dict]:
    if len(out) <= MAX_POR_REGLA:
        return out
    return out[:MAX_POR_REGLA] + [hallazgo(rule, evidencia, "... y %d hallazgos mas de la misma regla (se muestran %d)" % (len(out) - MAX_POR_REGLA, MAX_POR_REGLA))]


def _estudios_con(ctx, adam: Tuple[str, ...], sdtm: Tuple[str, ...], que: str):
    """Carpetas con algun ADaM de `adam` y TODOS los `sdtm` pedidos; sin ninguna, la regla no aplica y se dice por que."""
    c = [(d, ds) for d, ds in _carpetas(ctx).items() if any(a in ds for a in adam) and all(s in ds for s in sdtm)]
    if not c:
        raise NoAplicable("ninguna carpeta de estudio tiene a la vez %s y %s: %s no se evalua" % ("/".join(adam).upper(), "+".join(sdtm).upper(), que))
    return c


def _usubjid(ctx, rule):
    """Todo USUBJID de ADNCA/ADPP existe en DM de su estudio."""
    out = []
    for carpeta, ds in _estudios_con(ctx, ADAM, ("dm",), "la existencia del sujeto en DM"):
        leido = _leer(ctx, rule, ds["dm"], out)
        if leido is None:
            continue
        dm = {str(f.get("USUBJID", "")).strip() for f in leido[1]}
        for a in ADAM:
            if a not in ds:
                continue
            la = _leer(ctx, rule, ds[a], out)
            if la is None:
                continue
            if "USUBJID" not in la[0]:
                out.append(hallazgo(rule, rel(ctx.root, ds[a]), "%s no tiene la variable USUBJID" % a.upper()))
                continue
            for u in sorted({str(f.get("USUBJID", "")).strip() for f in la[1]} - dm):
                out.append(hallazgo(rule, rel(ctx.root, ds[a]), "USUBJID %r de %s no existe en DM" % (u, a.upper())))
    return _recortar(out, rule, carpeta)


def _studyid(ctx, rule):
    """Un solo STUDYID en toda la carpeta de estudio (SDTM y ADaM)."""
    out = []
    n = 0
    for carpeta, ds in _carpetas(ctx).items():
        if not any(a in ds for a in ADAM) or len(ds) < 2:
            continue
        n += 1
        por: Dict[str, set] = {}
        for nombre, p in sorted(ds.items()):
            leido = _leer(ctx, rule, p, out)
            if leido is None:
                continue
            if "STUDYID" not in leido[0]:
                out.append(hallazgo(rule, rel(ctx.root, p), "%s no tiene la variable STUDYID" % nombre.upper()))
                continue
            por[nombre] = {str(f.get("STUDYID", "")).strip() for f in leido[1]}
        todos = set().union(*por.values()) if por else set()
        if len(todos) > 1:
            det = "; ".join("%s=%s" % (k.upper(), sorted(v)) for k, v in sorted(por.items()))
            out.append(hallazgo(rule, carpeta, "STUDYID distinto entre los datasets del estudio: %s" % det))
    if n == 0:
        raise NoAplicable("ninguna carpeta de estudio tiene un ADaM junto a algun SDTM: la coherencia de STUDYID no se evalua")
    return out


def _trazas(ctx, rule, adam, origen_dom, origen_seq, valor_origen, aval_adam="AVAL"):
    """ADaM[SRCDOM=origen_dom] -> SDTM por (USUBJID, SRCSEQ == <DOM>SEQ); AVAL == valor numerico del origen."""
    out = []
    for carpeta, ds in _estudios_con(ctx, (adam,), (origen_dom.lower(),), "la trazabilidad %s -> %s" % (adam.upper(), origen_dom)):
        la = _leer(ctx, rule, ds[adam], out)
        lo = _leer(ctx, rule, ds[origen_dom.lower()], out)
        if la is None or lo is None:
            continue
        faltan = [v for v in ("USUBJID", "SRCDOM", "SRCSEQ", "AVAL") if v not in la[0]]
        if faltan:
            out.append(hallazgo(rule, rel(ctx.root, ds[adam]), "%s no tiene las variables de trazabilidad %s" % (adam.upper(), ", ".join(faltan))))
            continue
        base = {}
        for f in lo[1]:
            base[(str(f.get("USUBJID", "")).strip(), _entero(f.get(origen_seq)))] = f
        n = 0
        for f in la[1]:
            if str(f.get("SRCDOM", "")).strip() != origen_dom:
                continue
            n += 1
            clave = (str(f.get("USUBJID", "")).strip(), _entero(f.get("SRCSEQ")))
            o = base.get(clave)
            ev = rel(ctx.root, ds[adam])
            if o is None:
                out.append(hallazgo(rule, ev, "%s (USUBJID %r, SRCSEQ %s) apunta a un registro que no existe en %s" % (adam.upper(), clave[0], clave[1], origen_dom)))
                continue
            esperado = valor_origen(o)
            if not _iguales(f.get(aval_adam), esperado):
                out.append(hallazgo(rule, ev, "%s (USUBJID %r, SRCSEQ %s): AVAL=%s pero %s tiene %s" % (adam.upper(), clave[0], clave[1], f.get(aval_adam), origen_dom, esperado)))
            if adam == "adpp" and str(f.get("PARAMCD", "")).strip() != str(o.get("PPTESTCD", "")).strip():
                out.append(hallazgo(rule, ev, "ADPP (USUBJID %r, SRCSEQ %s): PARAMCD=%r pero PP.PPTESTCD=%r" % (
                    clave[0], clave[1], str(f.get("PARAMCD", "")).strip(), str(o.get("PPTESTCD", "")).strip())))
        if n == 0:
            out.append(hallazgo(rule, rel(ctx.root, ds[adam]), "%s no tiene ningun registro con SRCDOM=%s: no hay nada que trazar" % (adam.upper(), origen_dom)))
    return _recortar(out, rule, adam)


def _adnca_pc(ctx, rule):
    return _trazas(ctx, rule, "adnca", "PC", "PCSEQ", lambda o: o.get("PCSTRESN"))


def _adnca_ex(ctx, rule):
    return _trazas(ctx, rule, "adnca", "EX", "EXSEQ", lambda o: o.get("EXDOSE"))


def _adpp_pp(ctx, rule):
    return _trazas(ctx, rule, "adpp", "PP", "PPSEQ", lambda o: o.get("PPSTRESN"))


_CHECKS = {"usubjid": _usubjid, "studyid": _studyid, "adnca_pc": _adnca_pc, "adnca_ex": _adnca_ex, "adpp_pp": _adpp_pp}
CHECKS = _CHECKS
