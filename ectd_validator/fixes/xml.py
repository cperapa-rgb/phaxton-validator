"""index.xml de la COPIA: BOM, caracteres invisibles retirables y codificacion declarada distinta de UTF-8.

U+200C/U+200D (ZWNJ/ZWJ) son semanticos en algunos alfabetos: NO se eliminan; quedan como pendiente manual.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..checkers.backbone import INVISIBLES_RETIRABLES

DECL = re.compile(r"^(<[?]xml[^>]*encoding=[\"'])([^\"']+)([\"'])", re.I)


def _contexto(texto: str, i: int) -> str:
    return texto[max(0, i - 15): i].replace(chr(10), " ") + "[?]" + texto[i + 1: i + 16].replace(chr(10), " ")


def reparar(copia: Path, hallazgos, log) -> None:
    index = copia / "index.xml"
    crudo = index.read_bytes()
    cambios = []
    if crudo.startswith(bytes([0xEF, 0xBB, 0xBF])):
        crudo = crudo[3:]
        cambios.append("BOM UTF-8 al inicio")
    m = DECL.match(crudo.decode("latin-1"))
    codificacion = m.group(2).lower() if m else "utf-8"
    texto = crudo.decode(codificacion)  # UnicodeError/LookupError los gestiona el orquestador (queda pendiente)
    if codificacion not in ("utf-8", "utf8"):
        texto = DECL.sub(lambda mm: mm.group(1) + "UTF-8" + mm.group(3), texto, count=1)
        cambios.append(f"codificacion {codificacion} -> UTF-8 (contenido reconvertido)")
    for c in INVISIBLES_RETIRABLES:
        pos = [i for i, ch in enumerate(texto) if ch == c]
        if pos:
            ejemplo = "; ".join(f"offset {i}: {_contexto(texto, i)}" for i in pos[:5])
            cambios.append(f"U+{ord(c):04X} x{len(pos)} eliminado ({ejemplo})")
            texto = texto.replace(c, "")
    if not cambios:
        return
    index.write_bytes(texto.encode("utf-8"))
    log.append({"fichero": "index.xml", "regla": "BBN-005", "antes": " | ".join(cambios), "despues": "UTF-8 limpio"})
