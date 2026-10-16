"""MD5 por hoja vs backbone + index-md5.txt. Arbitro B: md5sum / openssl / certutil del sistema."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")
FORMATO_INDEX_MD5 = re.compile(r"^([0-9a-fA-F]{32})([ ]+[*]?index[.]xml)?$")
HEX32_EN_TEXTO = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{32})(?![0-9a-fA-F])")


def md5_hashlib(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


class ArbitroError(RuntimeError):
    """El arbitro externo fallo o dio salida ininterpretable: el paquete NO se puede dar por verificado."""


_PREFIJOS = {"md5sum": ["md5sum"], "openssl": ["openssl", "md5"], "certutil": ["certutil", "-hashfile"]}


def arbitros_disponibles() -> List[Tuple[str, List[str]]]:
    # certutil solo es el de Windows (-hashfile): en Linux `certutil` es la herramienta NSS y no calcula hashes (CI, 16-oct)
    return [(n, p) for n, p in _PREFIJOS.items() if shutil.which(p[0]) and (n != "certutil" or sys.platform == "win32")]


def arbitro_externo() -> Optional[Tuple[str, List[str]]]:
    """(nombre, argv-prefijo) del primer arbitro disponible, o None. Solo busca; no traga errores."""
    disp = arbitros_disponibles()
    return disp[0] if disp else None


def md5_externo(nombre: str, prefijo: List[str], p: Path) -> str:
    cmd = prefijo + [str(p), "MD5"] if nombre == "certutil" else prefijo + [str(p)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
    except (subprocess.TimeoutExpired, OSError) as e:
        raise ArbitroError(f"arbitro {nombre} no respondio sobre {p}: {e}") from e
    if r.returncode != 0:
        raise ArbitroError(f"arbitro {nombre} fallo (rc={r.returncode}) sobre {p}: {r.stderr.strip()}")
    if nombre == "certutil":
        for linea in r.stdout.splitlines():
            s = linea.strip().replace(" ", "")
            if HEX32.match(s):
                return s.lower()
    else:
        m = HEX32_EN_TEXTO.search(r.stdout)
        if m:
            return m.group(1).lower()
    raise ArbitroError(f"arbitro {nombre}: salida no interpretable para {p}: {r.stdout!r}")


def _hallazgo(rule: dict, evidencia: str, mensaje: str) -> dict:
    return {"regla": rule["id"], "codigo_oficial": rule.get("codigo_oficial"), "severidad": rule["severidad"],
            "evidencia": evidencia, "mensaje": mensaje, "accion": "pendiente"}


def run(ctx, rule: dict) -> List[dict]:
    return _CHECKS[rule["params"]["check"]](ctx, rule)


def _leaf_declarado(ctx, rule):
    out = []
    for leaf in ctx.leaves:
        if not leaf["md5"]:
            out.append(_hallazgo(rule, str(leaf["href"]), "la hoja no declara checksum"))
        elif not HEX32.match(leaf["md5"]):
            out.append(_hallazgo(rule, str(leaf["href"]),
                                 f"checksum no es un MD5 hexadecimal de 32: {leaf['md5']!r}"))
        if (leaf["md5_tipo"] or "").lower() != "md5":
            out.append(_hallazgo(rule, str(leaf["href"]), f"checksum-type debe ser md5, es {leaf['md5_tipo']!r}"))
    return out


def _leaf_md5(ctx, rule):
    out = []
    for leaf in ctx.leaves:
        if not leaf["md5"] or not HEX32.match(leaf["md5"]):
            continue  # lo cubre CHK-002
        p = ctx.resolver(leaf["href"])
        if p is None or not p.is_file():
            continue  # inexistente o fuera del paquete: lo cubre REF-001
        real = md5_hashlib(p)
        if real.lower() != leaf["md5"].lower():
            out.append(_hallazgo(rule, str(leaf["href"]), f"MD5 declarado {leaf['md5'].lower()} != calculado {real}"))
    return out


def _index_md5(ctx, rule):
    f = ctx.root / "index-md5.txt"
    if not f.is_file():
        return [_hallazgo(rule, "index-md5.txt", "no existe index-md5.txt en la secuencia")]
    txt = f.read_text(encoding="utf-8", errors="replace").strip()
    m = FORMATO_INDEX_MD5.match(txt)  # formato estricto: UNA linea, un MD5 y, opcional, el nombre
    if not m:
        return [_hallazgo(rule, "index-md5.txt", "formato invalido: se espera una sola linea con un MD5 de 32 hex")]
    real = md5_hashlib(ctx.index_path)
    if m.group(1).lower() != real:
        return [_hallazgo(rule, "index-md5.txt", f"declara {m.group(1).lower()} pero index.xml tiene {real}")]
    return []


def _arbitro(ctx, rule):
    arb = arbitro_externo()
    if arb is None:
        ctx.arbitros["md5"] = {"estado": "ARBITRO_UNICO", "detalle": "sin md5sum/openssl/certutil: solo hashlib"}
        return []
    nombre, prefijo = arb
    ctx.arbitros["md5"] = {"estado": "DOS_ARBITROS", "arbitro_b": nombre}
    out = []
    ficheros = [(leaf["href"], ctx.resolver(leaf["href"])) for leaf in ctx.leaves] + [("index.xml", ctx.index_path)]
    for href, p in ficheros:
        if p is None or not p.is_file():
            continue
        a, b = md5_hashlib(p), md5_externo(nombre, prefijo, p)
        if a != b:
            out.append(_hallazgo(rule, str(href), f"hashlib {a} != {nombre} {b}"))
    return out


_CHECKS = {"leaf_declarado": _leaf_declarado, "leaf_md5": _leaf_md5, "index_md5": _index_md5, "arbitro": _arbitro}


CHECKS = _CHECKS
