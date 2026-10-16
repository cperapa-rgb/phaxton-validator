"""Recalcula el MD5 de cada hoja en el backbone de la COPIA y reescribe index-md5.txt.

Edicion TEXTUAL de las etiquetas <leaf>: reserializar con lxml pierde el DOCTYPE (visto: la revalidacion lo cazo).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote

NL = chr(10)
LEAF = re.compile(r"<leaf\s[^>]*>")
ATTR = r'(?<![\w:-]){n}\s*=\s*"([^"]*)"'
HREF = re.compile(r'(?:xlink:)?href\s*=\s*"([^"]*)"')


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _poner(tag: str, nombre: str, valor: str) -> str:
    patron = re.compile(ATTR.format(n=re.escape(nombre)))
    if patron.search(tag):
        return patron.sub(lambda m: f'{nombre}="{valor}"', tag, count=1)
    return tag.replace("<leaf", f'<leaf {nombre}="{valor}"', 1)


def reparar(copia: Path, hallazgos, log) -> None:
    from . import FixError

    index = copia / "index.xml"
    texto = index.read_text(encoding="utf-8")
    previo_idx = hashlib.md5(index.read_bytes()).hexdigest()
    cambios = []

    def arreglar(m):
        tag = m.group(0)
        if "'" in tag:
            raise FixError("etiqueta <leaf> con atributos entre comillas simples: edicion textual no soportada")
        h = HREF.search(tag)
        if not h:
            return tag
        href = h.group(1)
        f = (copia / unquote(href)).resolve()
        try:
            f.relative_to(copia.resolve())
        except ValueError:
            return tag  # fuera del paquete: nunca se hashea
        if not f.is_file():
            return tag  # ausente: lo reporta REF-001, no se inventa un hash
        nuevo = _md5(f)
        c = re.search(ATTR.format(n="checksum"), tag)
        t = re.search(ATTR.format(n="checksum-type"), tag)
        if c and c.group(1) == nuevo and t and t.group(1).lower() == "md5":
            return tag
        tipo_antes = t.group(1) if t else "(sin checksum-type)"
        cambios.append({"fichero": "index.xml", "objeto": f"hoja {href}", "regla": "CHK-001" if c else "CHK-002",
                        "antes": f"{c.group(1) if c else '(sin checksum)'} [{tipo_antes}]",
                        "despues": f"{nuevo} [md5]"})
        tag = _poner(tag, "checksum", nuevo)
        return _poner(tag, "checksum-type", "md5")

    nuevo_texto = LEAF.sub(arreglar, texto)
    if cambios:
        index.write_text(nuevo_texto, encoding="utf-8", newline="")
        log.extend(cambios)
    f = copia / "index-md5.txt"
    previo = f.read_text(encoding="utf-8", errors="replace").strip() if f.is_file() else None
    nuevo = _md5(index)
    if previo != nuevo:
        f.write_text(nuevo + NL, encoding="utf-8", newline="")
        log.append({"fichero": "index-md5.txt", "regla": "CHK-003", "antes": previo or "(ausente)", "despues": nuevo})
