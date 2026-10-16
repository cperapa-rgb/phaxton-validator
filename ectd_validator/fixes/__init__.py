"""Reparacion SIEMPRE en copia, NUNCA sobre el original.

`reparar(origen, destino)` copia el paquete, aplica los arreglos que saben hacer su trabajo, deja un log por cambio
(fichero, regla, antes -> despues), revalida la copia y comprueba que el original no cambio. Todo lo que sigue roto en la
copia queda en `no_reparados` con motivo e instruccion manual (se deriva de la revalidacion, no de una lista de reglas
"tratadas"). Cualquier fallo del proceso es FixError y la copia a medias se borra: nunca un 'reparado' mudo.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

from ..engine import AVISO_PREPARATORIO, VERSION, validar_paquete


class FixError(Exception):
    """El arreglo o la reparacion no pudo completarse."""


MANUAL = {
    "REF-001": "Restaure el fichero referenciado o elimine la hoja del backbone.",
    "REF-002": "Anada una hoja que referencie el fichero o eliminelo del paquete.",
    "BBN-001": "Corrija index.xml segun el mensaje de la DTD (elementos/atributos no admitidos).",
    "BBN-005": "Revise manualmente los caracteres U+200C/U+200D: pueden ser semanticos y no se eliminan solos.",
    "STR-001": "Renombre el fichero/carpeta (a-z, 0-9, guion; <=64) y actualice su hoja.",
    "STR-002": "Acorte los nombres de carpeta/fichero hasta que la ruta no supere el limite.",
    "STR-003": "Mueva o elimine el elemento inesperado de la raiz de la secuencia.",
    "PDF-001": "Regenere el PDF desde la fuente: no se puede leer.",
    "PDF-002": "Retire el cifrado con la contrasena de usuario y vuelva a incluir el PDF.",
    "PDF-003": "Reexporte el PDF en version 1.4-1.7.",
    "PDF-004": "Reexporte el PDF embebiendo las fuentes indicadas.",
    "PDF-005": "Reduzca el PDF (optimizacion de imagenes) o confirme el umbral con la agencia.",
    "CHK-004": "Reintente: los dos arbitros de MD5 no coinciden (revise el entorno).",
    "STF-001": "Regenere el STF con el generador: no cumple la DTD oficial ICH STF 2.2.",
    "STF-002": "Use un file-tag de la tabla de la STF spec 2.6.1 (o de la TCG de la FDA) con su info-type.",
    "STF-003": "Corrija el href del doc-content para que apunte a index.xml#<ID de una hoja existente>.",
    "STF-004": "Anada un doc-content con el file-tag que corresponda a la hoja sin etiquetar.",
    "STF-005": "Renombre el STF a stf-<study-id>.xml y actualice su hoja.",
    "STF-006": "Ponga version=\"STF version 2.2\" en la hoja del STF de index.xml.",
    "STF-007": "Copie la DTD oficial ich-stf-v2-2.dtd en util/dtd sin alterarla.",
    "STF-008": "Anada un STF del estudio (stf-<study-id>.xml) que etiquete los datasets.",
    "STF-009": "Alinee el STUDYID de ts.xpt con el study-id del STF, o declare SPREFID en TS con el study-id del STF.",
    "STF-010": "Anada ts.xpt al estudio y etiquetelo data-tabulation-dataset en el STF.",
    "STF-011": "Declare la fecha de inicio del estudio (SSTDTC, ISO 8601) en ts.xpt.",
}
# Reglas con arreglo automatico (cualquier otra regla DEBE estar en MANUAL: lo comprueba un test).
AUTOMATICAS = {"CHK-001", "CHK-002", "CHK-003", "BBN-002", "BBN-003", "BBN-004", "BBN-005", "PDF-002", "PDF-003"}
# Reglas cuyo texto de evidencia lleva numero de linea y se desplaza al editar: se comparan solo por regla.
POR_REGLA = {"BBN-001"}


def manifiesto(raiz: Path) -> Dict[str, str]:
    """SHA-256 de todos los ficheros bajo raiz (para demostrar que el original no cambio)."""
    out = {}
    for p in sorted(raiz.rglob("*")):
        if p.is_file():
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for bloque in iter(lambda: f.read(1 << 20), b""):
                    h.update(bloque)
            out[p.relative_to(raiz).as_posix()] = h.hexdigest()
    return out


def _destino_valido(origen: Path, destino: Path) -> None:
    o, d = origen.resolve(), destino.resolve()
    if d == o or o in d.parents or d in o.parents:
        raise FixError("el destino no puede ser, contener ni estar dentro del original")
    if d.exists() and (not d.is_dir() or any(d.iterdir())):
        raise FixError(f"el destino ya existe y no es una carpeta vacia: {destino}")


def _sin_enlaces(origen: Path) -> None:
    for p in origen.rglob("*"):
        if p.is_symlink():
            raise FixError(f"el original contiene un enlace simbolico ({p.relative_to(origen).as_posix()}): "
                           "no se copia por seguridad (podria arrastrar contenido de fuera del paquete)")


def _clave(h: dict) -> Tuple[str, str]:
    return (h["regla"], "" if h["regla"] in POR_REGLA else h["evidencia"])


def reparar(origen, destino) -> dict:
    from . import dtd, md5, pdf, xml  # import perezoso: pikepdf solo si se repara

    origen, destino = Path(origen), Path(destino)
    if not origen.is_dir():
        raise FixError(f"el original no es una carpeta: {origen}")
    _sin_enlaces(origen)
    antes = manifiesto(origen)
    inicial = validar_paquete(origen)
    if inicial["estado"] == "NO_VALIDABLE":
        raise FixError("el paquete no es validable (" + "; ".join(h["mensaje"] for h in inicial["hallazgos"]) + ")")
    _destino_valido(origen, destino)
    existia = destino.exists()
    try:
        shutil.copytree(origen, destino, dirs_exist_ok=True)
        if manifiesto(destino) != antes:
            raise FixError("la copia no coincide con el original validado (el original cambio durante la copia)")
        return _reparar_en_copia(origen, destino, antes, inicial, (dtd, md5, pdf, xml))
    except FixError:
        _limpiar(destino, existia)
        raise
    except (UnicodeError, LookupError, OSError, shutil.Error, ValueError) as e:
        _limpiar(destino, existia)
        raise FixError(f"fallo inesperado durante la reparacion: {type(e).__name__}: {e}") from e


def _limpiar(destino: Path, existia: bool) -> None:
    """Borra solo la COPIA a medias (el original no se toca)."""
    if not destino.exists():
        return
    if existia:  # el usuario aporto la carpeta vacia: se vacia, no se elimina
        for p in destino.iterdir():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    else:
        shutil.rmtree(destino)


def _reparar_en_copia(origen, destino, antes, inicial, modulos) -> dict:
    dtd, md5, pdf, xml = modulos
    log: List[dict] = []
    motivos: Dict[Tuple[str, str], str] = {}
    por_regla: Dict[str, List[dict]] = {}
    for h in inicial["hallazgos"]:
        por_regla.setdefault(h["regla"], []).append(h)

    def aplicar(fn, hall):
        try:
            fn(destino, hall, log)
        except FixError as e:
            for h in hall:
                motivos[_clave(h)] = str(e)
        except (UnicodeError, LookupError) as e:
            for h in hall:
                motivos[_clave(h)] = f"contenido no interpretable: {type(e).__name__}: {e}"

    # Contenido de ficheros -> XML -> DOCTYPE/DTD -> checksums (al final: dependen de todo lo anterior).
    for fn, reglas in ((pdf.reparar, ("PDF-002", "PDF-003")), (xml.reparar, ("BBN-005",)),
                       (dtd.reparar, ("BBN-002", "BBN-003", "BBN-004"))):
        hall = [h for r in reglas for h in por_regla.get(r, [])]
        if hall:
            aplicar(fn, hall)
    chk = [h for r in ("CHK-001", "CHK-002", "CHK-003") for h in por_regla.get(r, [])]
    if chk or log:  # los checksums dependen de ficheros cambiados aunque no tuvieran hallazgo propio
        aplicar(md5.reparar, chk)

    final = validar_paquete(destino)
    if final["estado"] == "NO_VALIDABLE":
        raise FixError("la copia reparada dejo de ser validable: " + "; ".join(h["mensaje"] for h in final["hallazgos"]))
    vigentes = {_clave(h) for h in final["hallazgos"]}
    no_reparados = []
    for h in final["hallazgos"]:
        motivo = motivos.get(_clave(h)) or (
            "el arreglo automatico no lo resolvio" if h["regla"] in AUTOMATICAS else "sin arreglo automatico en v0")
        no_reparados.append({"regla": h["regla"], "evidencia": h["evidencia"], "motivo": motivo,
                             "instruccion": MANUAL.get(h["regla"], "Revision manual.")})
    resueltos = [{"regla": h["regla"], "evidencia": h["evidencia"]} for h in inicial["hallazgos"]
                 if _clave(h) not in vigentes]
    if manifiesto(origen) != antes:
        raise FixError("INVARIANTE ROTO: el original cambio durante la reparacion")
    # Dogfooding (16-oct): recalcular el checksum de una hoja cuyo MD5 NO coincidia deja la copia 'VALIDO' aunque el
    # fichero haya cambiado sin querer. El log lo registra; esto lo dice ademas con todas las letras.
    alteradas = [c["objeto"] for c in log if c.get("regla") == "CHK-001"]
    advertencias = []
    if alteradas:
        advertencias.append(
            "CHK-001: se recalculo el MD5 de %d hoja(s) para que coincida con el contenido ACTUAL del fichero. Eso NO "
            "demuestra que el contenido sea el original: si el fichero se modifico sin querer, la copia VALIDA lo oculta. "
            "Compare con la fuente antes de enviar. Hojas: %s" % (len(alteradas), "; ".join(alteradas)))
    return {
        "herramienta": "ectd_validator", "version": VERSION, "original": str(origen), "copia": str(destino),
        "advertencias": advertencias,
        "estado_original": inicial["estado"], "estado_copia": final["estado"],
        "cambios": log, "no_reparados": no_reparados, "resueltos": resueltos,
        "original_intacto": True, "ficheros_original": len(antes),
        "validacion_original": inicial, "validacion_copia": final, "aviso": AVISO_PREPARATORIO,
    }
