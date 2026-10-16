"""index.xml contra la DTD oficial de ICH (versionada en spec/), y coherencia con util/dtd del paquete."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import List

from lxml import etree

from .comun import hallazgo

DTD_OFICIAL = Path(__file__).resolve().parent.parent / "spec" / "ich-ectd-3-2.dtd"
DTD_EN_PAQUETE = "util/dtd/ich-ectd-3-2.dtd"
INVISIBLES_RETIRABLES = (chr(0x200B), chr(0x2060), chr(0xFEFF))
INVISIBLES_SEMANTICOS = (chr(0x200C), chr(0x200D))  # ZWNJ/ZWJ: pueden ser significativos; no se retiran solos
INVISIBLES = INVISIBLES_RETIRABLES + INVISIBLES_SEMANTICOS


def sha256_lf(p: Path) -> str:
    """SHA-256 con fines de linea normalizados a LF (autocrlf cambia CRLF entre equipos)."""
    return hashlib.sha256(p.read_bytes().replace(bytes([13, 10]), bytes([10]))).hexdigest()


def run(ctx, rule: dict) -> List[dict]:
    return _CHECKS[rule["params"]["check"]](ctx, rule)


def _dtd_valida(ctx, rule):
    if not DTD_OFICIAL.is_file():
        raise FileNotFoundError(f"falta la DTD versionada del validador: {DTD_OFICIAL}")  # nunca verde por ausencia
    dtd = etree.DTD(str(DTD_OFICIAL))
    # Se re-parsea sin DOCTYPE externo: la DTD que arbitra es la versionada, no la que traiga el paquete.
    if dtd.validate(ctx.tree):
        return []
    errores = [hallazgo(rule, f"index.xml:{e.line}", e.message) for e in dtd.error_log.filter_from_errors()]
    if not errores:  # validate()==False sin errores legibles: jamas verde
        errores = [hallazgo(rule, "index.xml", "no valida contra la DTD (sin detalle): " + str(dtd.error_log))]
    return errores


def _doctype(ctx, rule):
    url = ctx.tree.docinfo.system_url or ""
    if not url.endswith(DTD_EN_PAQUETE):
        return [hallazgo(rule, "index.xml", f"el DOCTYPE debe apuntar a {DTD_EN_PAQUETE}, apunta a {url!r}")]
    return []


def _dtd_presente(ctx, rule):
    if not (ctx.root / DTD_EN_PAQUETE).is_file():
        return [hallazgo(rule, DTD_EN_PAQUETE, "el paquete no incluye la DTD en util/dtd")]
    return []


def _dtd_intacta(ctx, rule):
    p = ctx.root / DTD_EN_PAQUETE
    if p.is_file() and sha256_lf(p) != sha256_lf(DTD_OFICIAL):
        return [hallazgo(rule, DTD_EN_PAQUETE, "la DTD del paquete difiere de la oficial ICH 3.2 (no debe alterarse)")]
    return []


def _xml_limpio(ctx, rule):
    crudo = ctx.index_path.read_bytes()
    out = []
    if crudo.startswith(bytes([0xEF, 0xBB, 0xBF])):
        out.append(hallazgo(rule, "index.xml", "el fichero empieza con BOM UTF-8"))
    cabecera = crudo[:200].decode("latin-1")
    m = re.match(r"<[?]xml[^>]*encoding=[\"']([^\"']+)", cabecera.lstrip(chr(0xEF) + chr(0xBB) + chr(0xBF)))
    if m and m.group(1).lower().replace("_", "-") not in ("utf-8", "utf8"):
        out.append(hallazgo(rule, "index.xml", f"codificacion declarada {m.group(1)}: se espera UTF-8"))
    try:
        texto = crudo.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        return out + [hallazgo(rule, "index.xml", f"no es UTF-8 valido: {e}")]
    n = sum(texto.count(c) for c in INVISIBLES_RETIRABLES)
    if n:
        out.append(hallazgo(rule, "index.xml", f"{n} caracteres invisibles retirables (U+200B/2060/FEFF)"))
    s = sum(texto.count(c) for c in INVISIBLES_SEMANTICOS)
    if s:
        out.append(hallazgo(rule, "index.xml", f"{s} caracteres U+200C/U+200D (posiblemente semanticos): revision manual"))
    return out


_CHECKS = {"xml_limpio": _xml_limpio, "dtd_valida": _dtd_valida, "doctype": _doctype, "dtd_presente": _dtd_presente, "dtd_intacta": _dtd_intacta}
CHECKS = _CHECKS
