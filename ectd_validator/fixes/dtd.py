"""DOCTYPE de index.xml y util/dtd de la COPIA: apunta a la DTD oficial y la incluye intacta."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from ..checkers.backbone import DTD_EN_PAQUETE, DTD_OFICIAL, sha256_lf

DOCTYPE = re.compile(r'<!DOCTYPE\s+ectd:ectd\s+SYSTEM\s+"[^"]*"\s*>')
NUEVO = '<!DOCTYPE ectd:ectd SYSTEM "' + DTD_EN_PAQUETE + '">'


def reparar(copia: Path, hallazgos, log) -> None:
    reglas = {h["regla"] for h in hallazgos}
    destino = copia / DTD_EN_PAQUETE
    if ("BBN-003" in reglas and not destino.is_file()) or ("BBN-004" in reglas and destino.is_file()):
        antes = sha256_lf(destino) if destino.is_file() else "(ausente)"
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DTD_OFICIAL, destino)
        log.append({"fichero": DTD_EN_PAQUETE, "regla": "BBN-004" if antes != "(ausente)" else "BBN-003",
                    "antes": antes, "despues": sha256_lf(destino)})
    if "BBN-002" in reglas:
        index = copia / "index.xml"
        texto = index.read_text(encoding="utf-8")
        m = DOCTYPE.search(texto)
        if m:
            nuevo = texto[: m.start()] + NUEVO + texto[m.end():]
            antes = m.group(0)
        else:  # sin DOCTYPE: se inserta tras la declaracion XML (o al principio)
            decl = re.match(r"<[?]xml[^>]*[?]>\s*", texto)
            pos = decl.end() if decl else 0
            nuevo = texto[:pos] + NUEVO + chr(10) + texto[pos:]
            antes = "(sin DOCTYPE)"
        index.write_text(nuevo, encoding="utf-8", newline="")
        log.append({"fichero": "index.xml", "regla": "BBN-002", "antes": antes, "despues": NUEVO})
