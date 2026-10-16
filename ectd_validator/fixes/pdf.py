"""PDF de la COPIA con pikepdf (MPL-2.0): quita cifrado de permisos y sube la version a la minima aceptada.

Limites: pikepdf REESCRIBE el fichero entero (reordena objetos); un PDF firmado digitalmente NO se reescribe porque se
invalidaria la firma. La postcondicion se COMPRUEBA tras guardar (no cifrado y version >= minima), no solo se vuelca.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pikepdf

from . import FixError

MIN_VERSION = "1.4"


def _v(s: str):
    return tuple(int(x) for x in s.split("."))


def _firmado(pdf) -> bool:
    try:
        form = pdf.Root.get("/AcroForm")
        return form is not None and int(form.get("/SigFlags", 0)) != 0
    except (pikepdf.PdfError, TypeError, ValueError):
        return False


def reparar(copia: Path, hallazgos, log) -> None:
    errores = []
    for h in hallazgos:
        p = copia / h["evidencia"]
        if not p.is_file():
            errores.append(f"{h['evidencia']}: no existe en la copia")
            continue
        tmp = p.with_name(p.name + ".tmp-fix")
        try:
            with pikepdf.open(str(p)) as pdf:  # contrasena vacia: solo cifrado de permisos
                antes_v, antes_c = pdf.pdf_version, pdf.is_encrypted
                if _firmado(pdf):
                    errores.append(f"{h['evidencia']}: firmado digitalmente; reescribirlo invalidaria la firma")
                    continue
                if h["regla"] == "PDF-002" and not antes_c:
                    continue
                if h["regla"] == "PDF-003":
                    if _v(antes_v) > (1, 7):
                        errores.append(f"{h['evidencia']}: version {antes_v} > 1.7 no se rebaja automaticamente")
                        continue
                    if _v(antes_v) >= _v(MIN_VERSION):
                        continue
                pdf.save(str(tmp), encryption=False, min_version=MIN_VERSION)
            with pikepdf.open(str(tmp)) as chk:  # postcondicion comprobada, no solo registrada
                despues_v, despues_c = chk.pdf_version, chk.is_encrypted
            if despues_c or _v(despues_v) < _v(MIN_VERSION):
                errores.append(f"{h['evidencia']}: el resultado no cumple la postcondicion "
                               f"(version {despues_v}, cifrado={despues_c}); se descarta")
                continue
            shutil.move(str(tmp), str(p))
            log.append({"fichero": h["evidencia"], "regla": h["regla"],
                        "antes": f"version {antes_v}, cifrado={antes_c}",
                        "despues": f"version {despues_v}, cifrado={despues_c} (fichero reescrito por pikepdf)"})
        except pikepdf.PasswordError:
            errores.append(f"{h['evidencia']}: requiere contrasena de usuario; retire el cifrado con ella")
        except (pikepdf.PdfError, OSError) as e:
            errores.append(f"{h['evidencia']}: {type(e).__name__}: {e}")
        finally:
            if tmp.exists():
                tmp.unlink()
    if errores:
        raise FixError("; ".join(errores))
