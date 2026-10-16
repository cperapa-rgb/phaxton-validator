"""PDFs del backbone (pypdf): abre, no cifrado, version, fuentes embebidas, tamano anomalo.

La especificacion ICH 3.2.2 pide embeber toda fuente que no sea Times New Roman, Arial o Courier (o de la familia
Acrobat). Rangos de version y tamano maximo son de guias regionales, no de ICH: se marcan como avisos parametrizables.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from .comun import NoAplicable, hallazgo

# Familias exentas: Times New Roman, Arial y Courier (spec 3.2.2) mas las base-14 que Acrobat trae (Helvetica, Times,
# Courier, Symbol, ZapfDingbats). Lista explicita con borde: "Timesheet" NO queda exento.
EXENTA = re.compile(r"^(timesnewroman|times|arial|helvetica|couriernew|courier)(-|,|ps|mt|$)|^(symbol|zapfdingbats)$")
ERRORES_LECTURA = (PyPdfError, ValueError, KeyError, TypeError, OSError, AttributeError, RecursionError, IndexError)
VERSION = re.compile(r"^%PDF-(\d+)[.](\d+)")


def run(ctx, rule: dict) -> List[dict]:
    referenciados = [lf for lf in ctx.leaves if (lf["href"] or "").lower().endswith(".pdf")]
    pdfs = _pdfs(ctx)
    if not referenciados:
        raise NoAplicable("el backbone no referencia ningun PDF: no hay material que inspeccionar")
    if not pdfs:
        raise NoAplicable(f"{len(referenciados)} PDF referenciados pero ninguno accesible (ver REF-001): "
                          "no hay material que inspeccionar")
    return _CHECKS[rule["params"]["check"]](ctx, rule, pdfs)


def _pdfs(ctx) -> List[Tuple[str, "object"]]:
    out = []
    for leaf in ctx.leaves:
        href = leaf["href"] or ""
        if href.lower().endswith(".pdf"):
            p = ctx.resolver(href)
            if p is not None and p.is_file():
                out.append((href, p))
    return out


def _abrir(p):
    """(reader, error). Un fallo de lectura es un hallazgo, nunca una excepcion que escape ni un 'ok' mudo."""
    try:
        r = PdfReader(str(p), strict=False)
        if not r.is_encrypted:  # un PDF cifrado se reporta como cifrado (PDF-002), no como ilegible
            len(r.pages)  # fuerza el parseo de la estructura
        return r, None
    except ERRORES_LECTURA as e:
        return None, f"{type(e).__name__}: {e}"


def _abre(ctx, rule, pdfs):
    out = []
    for href, p in pdfs:
        _, err = _abrir(p)
        if err:
            out.append(hallazgo(rule, href, "no se puede abrir como PDF: " + err))
    return out


def _lectores(pdfs):
    for href, p in pdfs:
        r, err = _abrir(p)
        if r is not None:
            yield href, p, r


def _cifrado(ctx, rule, pdfs):
    return [hallazgo(rule, href, "el PDF esta cifrado (el agente no puede abrirlo ni indexarlo)")
            for href, _p, r in _lectores(pdfs) if r.is_encrypted]


def _version(ctx, rule, pdfs):
    lo = tuple(rule["params"]["min"])
    hi = tuple(rule["params"]["max"])
    out = []
    for href, p, r in _lectores(pdfs):
        m = VERSION.match(r.pdf_header or "")
        if not m:
            out.append(hallazgo(rule, href, f"cabecera PDF no reconocible: {r.pdf_header!r}"))
            continue
        v = (int(m.group(1)), int(m.group(2)))
        try:  # /Version del catalogo puede elevar la version tras actualizaciones incrementales
            cat = re.match(r"^(\d+)[.](\d+)$", str(r.trailer["/Root"].get("/Version", "")).lstrip("/"))
            if cat:
                v = max(v, (int(cat.group(1)), int(cat.group(2))))
        except ERRORES_LECTURA:
            pass  # sin catalogo legible se queda la cabecera; PDF-001 ya cubre un catalogo ilegible
        if not (lo <= v <= hi):
            out.append(hallazgo(rule, href, f"version PDF {v[0]}.{v[1]} fuera de {lo[0]}.{lo[1]}-{hi[0]}.{hi[1]}"))
    return out


def _fuentes_no_embebidas(r) -> Set[str]:
    """Nombres de fuentes sin FontFile* (salvo exentas y Type3). Recorre paginas y XObjects de formulario."""
    faltan: Set[str] = set()
    vistos: Set[int] = set()

    def fuente(f):
        f = f.get_object()
        sub = str(f.get("/Subtype", ""))
        if sub == "/Type3":
            return
        base = str(f.get("/BaseFont", "/(sin nombre)")).lstrip("/")
        if sub == "/Type0":
            desc = f.get("/DescendantFonts")
            if not desc or not len(desc.get_object()):
                raise ValueError(f"fuente Type0 {base} sin DescendantFonts")  # estructura danada: no se puede inspeccionar
            f = desc.get_object()[0].get_object()
        fd = f.get("/FontDescriptor")
        fd = fd.get_object() if fd is not None else None
        embebida = fd is not None and any(k in fd for k in ("/FontFile", "/FontFile2", "/FontFile3"))
        nombre = re.sub(r"^[A-Z]{6}[+]", "", base)
        if not embebida and not EXENTA.match(nombre.lower().replace(" ", "")):
            faltan.add(nombre)

    def recursos(res, profundidad=0):
        if res is None or profundidad > 4:
            return
        res = res.get_object()
        for f in (res.get("/Font") or {}).values():
            fuente(f)
        for xo in (res.get("/XObject") or {}).values():
            xo = xo.get_object()
            if id(xo) in vistos:
                continue
            vistos.add(id(xo))
            if str(xo.get("/Subtype", "")) == "/Form":
                recursos(xo.get("/Resources"), profundidad + 1)

    for page in r.pages:
        recursos(page.get("/Resources"))
    return faltan


def _fuentes(ctx, rule, pdfs):
    out = []
    for href, _p, r in _lectores(pdfs):
        if r.is_encrypted:
            continue  # lo cubre PDF-002; no se puede inspeccionar
        try:
            faltan = _fuentes_no_embebidas(r)
        except ERRORES_LECTURA as e:  # estructura de fuentes danada: hallazgo de error, nunca excepcion ni verde
            h = hallazgo(rule, href, f"no se pudieron inspeccionar las fuentes: {type(e).__name__}: {e}")
            h["severidad"] = "error"
            out.append(h)
            continue
        for nombre in sorted(faltan):
            out.append(hallazgo(rule, href, f"fuente no embebida: {nombre}"))
    return out


def _tamano(ctx, rule, pdfs):
    lim = rule["params"]["max_mb"] * 1024 * 1024
    out = []
    for href, p in pdfs:
        n = p.stat().st_size
        if n == 0:
            out.append(hallazgo(rule, href, "el PDF esta vacio (0 bytes)"))
        elif n > lim:
            out.append(hallazgo(rule, href, f"{n / 1048576:.1f} MB supera el umbral de {rule['params']['max_mb']} MB"))
    return out


_CHECKS = {"abre": _abre, "cifrado": _cifrado, "version": _version, "fuentes": _fuentes, "tamano": _tamano}
CHECKS = _CHECKS
