"""Coherencia SDTM <-> ADaM dentro del paquete: lo que un validador puede comprobar SIN licencia ni reglas ADaM ajenas.

Compara los datasets ADaM del paquete (ADNCA, ADPP) con los SDTM de los que dicen derivarse (DM, PC, EX, PP) en el MISMO estudio,
leyendo todos con el lector XPT propio del validador (independiente de quien los escribio). No valida conformidad CDISC (eso
exige reglas ADaM que ningun motor libre trae): comprueba que los datos de los dos lados se cuentan la misma historia.

Sin material la regla NO se ejecuta (NoAplicable). Un estudio que no se puede evaluar mientras otro si, se DECLARA con un aviso
(nunca se omite en silencio). Un XPT que no se puede leer es un hallazgo, no un silencio.
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
MAX_POR_REGLA = 20          # un fallo sistematico no inunda el informe: por fichero se muestran N y se declara el total
# ADaM -> SRCDOM -> (dataset SDTM, variable de secuencia, variable numerica que AVAL debe igualar)
ORIGEN = {"adnca": {"PC": ("pc", "PCSEQ", "PCSTRESN"), "EX": ("ex", "EXSEQ", "EXDOSE")},
          "adpp": {"PP": ("pp", "PPSEQ", "PPSTRESN")}}


def run(ctx, rule: dict) -> List[dict]:
    return _CHECKS[rule["params"]["check"]](ctx, rule)


def _estudio(carpeta: str) -> str:
    """Raiz del estudio: el layout de datos de la FDA separa SDTM (<estudio>/tabulations/sdtm) y ADaM (<estudio>/analysis/adam/datasets)
    en carpetas distintas; ambos pertenecen al mismo estudio. Fuera de ese layout, la carpeta del fichero es el estudio."""
    for sufijo in ("/tabulations/sdtm", "/analysis/adam/datasets"):
        if carpeta.endswith(sufijo):
            return carpeta[: -len(sufijo)]
    return carpeta


def _carpetas(ctx) -> Dict[str, Dict[str, List[Path]]]:
    """estudio -> {nombre sin extension en minuscula: [rutas]} de los .xpt de M4/M5 que son SDTM o ADaM conocidos."""
    out: Dict[str, Dict[str, List[Path]]] = defaultdict(lambda: defaultdict(list))
    for h in ctx.leaves:
        href = h["href"] or ""
        if not href.startswith(("m4/", "m5/")) or not href.lower().endswith(".xpt"):
            continue
        nombre = href.rsplit("/", 1)[-1][:-4].lower()
        if nombre not in ADAM + SDTM:
            continue
        p = ctx.resolver(href)
        if p is not None and p.is_file():
            out[_estudio(href.rsplit("/", 1)[0])][nombre].append(p)
    return out


def _omitido(rule, evidencia: str, motivo: str) -> dict:
    """Un estudio que no se pudo evaluar se DECLARA (aviso): omitirlo en silencio seria un verde por ausencia."""
    h = hallazgo(rule, evidencia, "estudio NO evaluado por esta regla: %s" % motivo)
    h["severidad"] = "aviso"
    return h


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


def _clave(usubjid, seq):
    """(USUBJID, secuencia entera exacta) o None si la secuencia falta o no es un entero (nunca se redondea)."""
    if seq is None or seq != int(seq):
        return None
    return (str(usubjid), int(seq))


def _recortar(out: List[dict], rule) -> List[dict]:
    """Por fichero: N hallazgos y el total del resto (un estudio masivamente roto no oculta a otro)."""
    por = defaultdict(list)
    for h in out:
        por[h["evidencia"]].append(h)
    res = []
    for ev, hs in por.items():
        res.extend(hs[:MAX_POR_REGLA])
        if len(hs) > MAX_POR_REGLA:
            res.append(hallazgo(rule, ev, "... y %d hallazgos mas de la misma regla (se muestran %d)" % (len(hs) - MAX_POR_REGLA, MAX_POR_REGLA)))
    return res


def _uno(ctx, rule, ds: Dict[str, List[Path]], nombre: str, out: List[dict]) -> Optional[Path]:
    """La ruta unica del dataset en el estudio; con dos del mismo nombre el cruce es ambiguo y se declara."""
    ps = ds.get(nombre, [])
    if len(ps) > 1:
        out.append(hallazgo(rule, rel(ctx.root, ps[0]), "hay %d ficheros %s.xpt en el mismo estudio: el cruce es ambiguo" % (len(ps), nombre)))
        return None
    return ps[0] if ps else None


def _usubjid(ctx, rule):
    """Todo USUBJID de ADNCA/ADPP existe en DM de su estudio."""
    out = []
    n = 0
    for estudio, ds in sorted(_carpetas(ctx).items()):
        adam = [a for a in ADAM if a in ds]
        if not adam:
            continue
        if "dm" not in ds:
            out.append(_omitido(rule, estudio, "no hay dm.xpt junto al %s" % "/".join(a.upper() for a in adam)))
            continue
        pdm = _uno(ctx, rule, ds, "dm", out)
        ldm = _leer(ctx, rule, pdm, out) if pdm else None
        if ldm is None:
            continue
        if "USUBJID" not in ldm[0]:
            out.append(hallazgo(rule, rel(ctx.root, pdm), "DM no tiene la variable USUBJID"))
            continue
        n += 1
        dm = {str(f.get("USUBJID", "")) for f in ldm[1]}
        for a in adam:
            pa = _uno(ctx, rule, ds, a, out)
            la = _leer(ctx, rule, pa, out) if pa else None
            if la is None:
                continue
            if "USUBJID" not in la[0]:
                out.append(hallazgo(rule, rel(ctx.root, pa), "%s no tiene la variable USUBJID" % a.upper()))
                continue
            for u in sorted({str(f.get("USUBJID", "")) for f in la[1]} - dm):
                out.append(hallazgo(rule, rel(ctx.root, pa), "USUBJID %r de %s no existe en DM" % (u, a.upper())))
    if n == 0 and all(h["severidad"] == "aviso" for h in out):
        raise NoAplicable("; ".join(h["mensaje"] for h in out) or "ninguna carpeta de estudio tiene a la vez ADNCA/ADPP y DM: la existencia del sujeto en DM no se evalua")
    return _recortar(out, rule)


def _studyid(ctx, rule):
    """Un solo STUDYID en toda la carpeta de estudio (SDTM y ADaM)."""
    out = []
    n = 0
    for estudio, ds in sorted(_carpetas(ctx).items()):
        if not any(a in ds for a in ADAM):
            continue
        if len(ds) < 2:
            out.append(_omitido(rule, estudio, "el estudio solo tiene %s: nada con que comparar el STUDYID" % "/".join(sorted(ds)).upper()))
            continue
        n += 1
        por: Dict[str, set] = {}
        for nombre in sorted(ds):
            p = _uno(ctx, rule, ds, nombre, out)
            leido = _leer(ctx, rule, p, out) if p else None
            if leido is None:
                continue
            if "STUDYID" not in leido[0]:
                out.append(hallazgo(rule, rel(ctx.root, p), "%s no tiene la variable STUDYID" % nombre.upper()))
                continue
            por[nombre] = {str(f.get("STUDYID", "")) for f in leido[1]}
        todos = set().union(*por.values()) if por else set()
        if len(todos) > 1:
            det = "; ".join("%s=%s" % (k.upper(), sorted(v)) for k, v in sorted(por.items()))
            out.append(hallazgo(rule, estudio, "STUDYID distinto entre los datasets del estudio: %s" % det))
    if n == 0:
        raise NoAplicable("ninguna carpeta de estudio tiene un ADaM junto a algun SDTM: la coherencia de STUDYID no se evalua")
    return _recortar(out, rule)


def _trazas(ctx, rule, adam, dom):
    """ADaM[SRCDOM=dom] -> SDTM por (USUBJID, SRCSEQ == <DOM>SEQ); AVAL == valor numerico del origen."""
    nombre_o, var_seq, var_val = ORIGEN[adam][dom]
    permitidos = set(ORIGEN[adam])
    primera = next(iter(ORIGEN[adam])) == dom      # los SRCDOM fuera del conjunto se senalan UNA vez por dataset: en la primera regla de su ADaM
    out = []
    n_evaluados = 0
    for estudio, ds in sorted(_carpetas(ctx).items()):
        if adam not in ds:
            continue
        pa = _uno(ctx, rule, ds, adam, out)
        la = _leer(ctx, rule, pa, out) if pa else None
        if la is None:
            continue
        ev = rel(ctx.root, pa)
        faltan = [v for v in ("USUBJID", "SRCDOM", "SRCSEQ", "AVAL") + (("PARAMCD",) if adam == "adpp" else ()) if v not in la[0]]
        if faltan:
            out.append(hallazgo(rule, ev, "%s no tiene las variables de trazabilidad %s" % (adam.upper(), ", ".join(faltan))))
            continue
        if primera:
            for f in la[1]:
                d = str(f.get("SRCDOM", ""))
                if d not in permitidos:
                    out.append(hallazgo(rule, ev, "%s (USUBJID %r): SRCDOM=%r no es uno de %s; el registro no se puede trazar" % (
                        adam.upper(), str(f.get("USUBJID", "")), d, sorted(permitidos))))
        filas = [f for f in la[1] if str(f.get("SRCDOM", "")) == dom]
        if not filas:
            continue            # este ADaM no tiene registros de este origen: la regla no aplica a este estudio
        if nombre_o not in ds:
            out.append(hallazgo(rule, ev, "%s tiene %d registros con SRCDOM=%s y el estudio no tiene %s.xpt: no hay a que apuntar" % (
                adam.upper(), len(filas), dom, nombre_o)))
            continue
        po = _uno(ctx, rule, ds, nombre_o, out)
        lo = _leer(ctx, rule, po, out) if po else None
        if lo is None:
            continue
        faltan_o = [v for v in ("USUBJID", var_seq, var_val) + (("PPTESTCD",) if adam == "adpp" else ()) if v not in lo[0]]
        if faltan_o:
            out.append(hallazgo(rule, rel(ctx.root, po), "%s no tiene las variables %s que el cruce necesita" % (dom, ", ".join(faltan_o))))
            continue
        n_evaluados += 1
        base = {}
        for f in lo[1]:
            k = _clave(f.get("USUBJID", ""), f.get(var_seq))
            if k is None:
                out.append(hallazgo(rule, rel(ctx.root, po), "%s (USUBJID %r): %s ausente o no entero, no sirve de clave" % (dom, str(f.get("USUBJID", "")), var_seq)))
            elif k in base:
                out.append(hallazgo(rule, rel(ctx.root, po), "%s tiene repetida la clave (USUBJID %r, %s %s): el cruce seria ambiguo" % (dom, k[0], var_seq, k[1])))
            else:
                base[k] = f
        for f in filas:
            clave = _clave(f.get("USUBJID", ""), f.get("SRCSEQ"))
            if clave is None:
                out.append(hallazgo(rule, ev, "%s (USUBJID %r): SRCSEQ=%s ausente o no entero" % (adam.upper(), str(f.get("USUBJID", "")), f.get("SRCSEQ"))))
                continue
            o = base.get(clave)
            if o is None:
                out.append(hallazgo(rule, ev, "%s (USUBJID %r, SRCSEQ %s) apunta a un registro que no existe en %s" % (adam.upper(), clave[0], clave[1], dom)))
                continue
            esperado = o.get(var_val)
            if not _iguales(f.get("AVAL"), esperado):
                out.append(hallazgo(rule, ev, "%s (USUBJID %r, SRCSEQ %s): AVAL=%s pero %s.%s=%s" % (adam.upper(), clave[0], clave[1], f.get("AVAL"), dom, var_val, esperado)))
            if adam == "adpp" and str(f.get("PARAMCD", "")) != str(o.get("PPTESTCD", "")):
                out.append(hallazgo(rule, ev, "ADPP (USUBJID %r, SRCSEQ %s): PARAMCD=%r pero PP.PPTESTCD=%r" % (
                    clave[0], clave[1], str(f.get("PARAMCD", "")), str(o.get("PPTESTCD", "")))))
    if n_evaluados == 0 and not out:
        raise NoAplicable("ningun estudio tiene %s con registros SRCDOM=%s: la trazabilidad %s -> %s no se evalua" % (adam.upper(), dom, adam.upper(), dom))
    return _recortar(out, rule)


def _adnca_pc(ctx, rule):
    return _trazas(ctx, rule, "adnca", "PC")


def _adnca_ex(ctx, rule):
    return _trazas(ctx, rule, "adnca", "EX")


def _adpp_pp(ctx, rule):
    return _trazas(ctx, rule, "adpp", "PP")


_CHECKS = {"usubjid": _usubjid, "studyid": _studyid, "adnca_pc": _adnca_pc, "adnca_ex": _adnca_ex, "adpp_pp": _adpp_pp}
CHECKS = _CHECKS
