"""Informe HTML y PDF DERIVADOS del JSON de hallazgos (fuente unica): nada se escribe aparte del dict.

El aviso preparatorio va en el pie de CADA pagina del PDF y al final del HTML. `contiene_aviso` es el guard que usan los
tests y los integradores para verificar su presencia en el artefacto ya renderizado.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Dict, List, Optional

from .engine import AVISO_PREPARATORIO

ESTADOS = {
    "VALIDO": "Valido", "VALIDO_CON_AVISOS": "Valido con avisos",
    "CON_ERRORES": "Con errores", "NO_VALIDABLE": "No validable",
}


def _normalizar(t: str) -> str:
    return " ".join(t.split())


def contiene_aviso(texto: str) -> bool:
    """True si el texto contiene el aviso preparatorio COMPLETO (se ignora el espaciado)."""
    return _normalizar(AVISO_PREPARATORIO) in _normalizar(html.unescape(texto))


def _tabla_hallazgos(informe: dict) -> List[List[str]]:
    return [[h["regla"], str(h.get("codigo_oficial") or "propio"), h["severidad"], str(h["evidencia"]),
             h["mensaje"], h.get("accion", "pendiente")] for h in informe["hallazgos"]]


def a_html(informe: dict, reparacion: Optional[dict] = None) -> str:
    e = html.escape
    filas = "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in f) + "</tr>" for f in _tabla_hallazgos(informe))
    no_ej = "".join(f"<li><b>{e(r['regla'])}</b>: {e(r['motivo'])}</li>" for r in informe["reglas_no_ejecutadas"])
    arb = "".join(f"<li>{e(k)}: {e(json.dumps(v, ensure_ascii=False))}</li>" for k, v in informe["arbitros"].items())
    valida = "".join(f"<li>{e(x)}</li>" for x in informe["alcance"]["valida"])
    no_valida = "".join(f"<li>{e(x)}</li>" for x in informe["alcance"]["no_valida"])
    rep = ""
    if reparacion:
        cambios = "".join(
            f"<tr><td>{e(c['fichero'])}</td><td>{e(c['regla'])}</td><td>{e(str(c['antes']))}</td>"
            f"<td>{e(str(c['despues']))}</td></tr>" for c in reparacion["cambios"])
        pend = "".join(f"<li><b>{e(n['regla'])}</b> {e(str(n['evidencia']))}: {e(n['instruccion'])}</li>"
                       for n in reparacion["no_reparados"])
        rep = (f"<h2>Reparacion (en copia)</h2><p>Copia: {e(reparacion['copia'])}. Estado: "
               f"{e(ESTADOS.get(reparacion['estado_original'], ''))} &rarr; {e(ESTADOS.get(reparacion['estado_copia'], ''))}."
               f" El original no se modifica.</p><table><tr><th>Fichero</th><th>Regla</th><th>Antes</th><th>Despues</th></tr>"
               f"{cambios}</table><h3>Pendiente manual</h3><ul>{pend or '<li>(nada)</li>'}</ul>")
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        "<title>Informe de validacion eCTD</title>"
        "<style>body{font-family:system-ui,sans-serif;margin:2rem;color:#1b1f23}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #c8cdd2;padding:.35rem .5rem;text-align:left;font-size:.9rem}"
        ".estado{font-weight:600}footer{margin-top:2rem;padding-top:1rem;border-top:2px solid #888;font-size:.8rem}"
        "</style></head><body>"
        f"<h1>Informe de validacion eCTD</h1><p>{e(informe['especificacion'])} &middot; ectd_validator "
        f"{e(informe['version'])} &middot; {e(informe['fecha_utc'])}</p><p>Paquete: {e(informe['paquete'])}</p>"
        f"<p class=\"estado\">Estado: {e(ESTADOS.get(informe['estado'], informe['estado']))}</p>"
        f"<p>Hojas inspeccionadas: {informe['hojas_inspeccionadas']} &middot; Reglas ejecutadas: "
        f"{len(informe['reglas_ejecutadas'])} de {len(informe['reglas_cargadas'])} &middot; Hallazgos: "
        f"{len(informe['hallazgos'])}</p>"
        "<h2>Hallazgos</h2><table><tr><th>Regla</th><th>Codigo oficial</th><th>Severidad</th><th>Evidencia</th>"
        f"<th>Mensaje</th><th>Accion</th></tr>{filas}</table>"
        f"<h2>Reglas no ejecutadas</h2><ul>{no_ej or '<li>(ninguna)</li>'}</ul>"
        f"<h2>Arbitros</h2><ul>{arb or '<li>(sin arbitros usados)</li>'}</ul>"
        f"<h2>Alcance</h2><h3>Valida</h3><ul>{valida}</ul><h3>No valida</h3><ul>{no_valida}</ul>"
        f"{rep}<footer><p>{e(AVISO_PREPARATORIO)}</p></footer></body></html>"
    )


def _registrar_fuente() -> None:
    """Bitstream Vera, que reportlab ya trae (libre, sin dependencia extra), registrada para EMBEBERSE: el informe
    del validador no puede ser el PDF con fuente sin embeber de un paquete cuyo validador exige embeberlas."""
    import os
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if "VAL-Vera" in pdfmetrics.getRegisteredFontNames():
        return
    d = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    for nombre, fichero in (("VAL-Vera", "Vera.ttf"), ("VAL-Vera-Bold", "VeraBd.ttf")):
        ruta = os.path.join(d, fichero)
        if not os.path.isfile(ruta):
            raise RuntimeError("falta %s en reportlab: no se escribe un PDF con fuente sin embeber" % ruta)
        pdfmetrics.registerFont(TTFont(nombre, ruta))
    pdfmetrics.registerFontFamily("VAL-Vera", normal="VAL-Vera", bold="VAL-Vera-Bold", italic="VAL-Vera",
                                  boldItalic="VAL-Vera-Bold")


def comprobar_fuentes_embebidas(ruta) -> None:
    """Toda fuente de cada pagina debe tener fichero de fuente (PyMuPDF); si no, RuntimeError (no verde)."""
    import fitz
    malas = set()
    with fitz.open(str(ruta)) as doc:
        for pg in doc:
            for f in pg.get_fonts(full=True):
                if f[1] == "n/a":
                    malas.add(str(f[3]))
    if malas:
        raise RuntimeError("%s contiene fuentes NO embebidas: %s" % (Path(ruta).name, ", ".join(sorted(malas))))


def a_pdf(informe: dict, ruta, reparacion: Optional[dict] = None) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    ruta = Path(ruta)
    _registrar_fuente()
    st = getSampleStyleSheet()
    for nombre in list(st.byName):          # toda la hoja de estilos a la fuente embebida
        est = st[nombre]
        if not hasattr(est, "fontName"):      # ListStyle y similares no llevan fuente
            continue
        est.fontName = "VAL-Vera-Bold" if "Bold" in est.fontName else "VAL-Vera"
    pequeno = st["BodyText"].clone("peq", fontSize=7, leading=8.5)
    aviso_style = st["BodyText"].clone("aviso", fontSize=6.5, leading=8)

    def pie(canvas, doc):  # aviso en CADA pagina
        canvas.saveState()
        anchura = landscape(A4)[0] - 24 * mm
        p = Paragraph(escape(AVISO_PREPARATORIO), aviso_style)
        w, h = p.wrap(anchura, 40 * mm)
        p.drawOn(canvas, 12 * mm, 8 * mm)
        canvas.setFont("VAL-Vera", 7)
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 4 * mm, f"Pag. {doc.page}")
        canvas.restoreState()

    def celdas(filas, cab):
        data = [[Paragraph(f"<b>{escape(c)}</b>", pequeno) for c in cab]]
        for f in filas:
            data.append([Paragraph(escape(str(c)), pequeno) for c in f])
        t = Table(data, repeatRows=1, colWidths=None)
        t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "VAL-Vera"), ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    doc = SimpleDocTemplate(str(ruta), pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=34 * mm, title="Informe de validacion eCTD",
                            initialFontName="VAL-Vera")
    el = [Paragraph("Informe de validacion eCTD", st["Title"]),
          Paragraph(escape(f"{informe['especificacion']} - ectd_validator {informe['version']} - {informe['fecha_utc']}"),
                    st["BodyText"]),
          Paragraph(escape(f"Paquete: {informe['paquete']}"), st["BodyText"]),
          Paragraph(f"<b>Estado: {escape(ESTADOS.get(informe['estado'], informe['estado']))}</b>", st["Heading2"]),
          Paragraph(escape(f"Hojas inspeccionadas: {informe['hojas_inspeccionadas']} - Reglas ejecutadas: "
                           f"{len(informe['reglas_ejecutadas'])} de {len(informe['reglas_cargadas'])} - "
                           f"Hallazgos: {len(informe['hallazgos'])}"), st["BodyText"]),
          Spacer(1, 6), Paragraph("Hallazgos", st["Heading3"])]
    filas = _tabla_hallazgos(informe)
    el.append(celdas(filas, ["Regla", "Codigo", "Severidad", "Evidencia", "Mensaje", "Accion"]) if filas
              else Paragraph("(ninguno)", st["BodyText"]))
    el.append(Paragraph("Reglas no ejecutadas", st["Heading3"]))
    if informe["reglas_no_ejecutadas"]:
        el.append(celdas([[r["regla"], r["motivo"]] for r in informe["reglas_no_ejecutadas"]], ["Regla", "Motivo"]))
    else:
        el.append(Paragraph("(ninguna)", st["BodyText"]))
    el.append(Paragraph("Alcance", st["Heading3"]))
    el.append(Paragraph(escape("Valida: " + "; ".join(informe["alcance"]["valida"])), st["BodyText"]))
    el.append(Paragraph(escape("No valida: " + "; ".join(informe["alcance"]["no_valida"])), st["BodyText"]))
    if reparacion:
        el.append(Paragraph("Reparacion (en copia)", st["Heading3"]))
        el.append(Paragraph(escape(f"Copia: {reparacion['copia']}. El original no se modifica."), st["BodyText"]))
        if reparacion["cambios"]:
            el.append(celdas([[c["fichero"], c["regla"], c["antes"], c["despues"]] for c in reparacion["cambios"]],
                             ["Fichero", "Regla", "Antes", "Despues"]))
        for n in reparacion["no_reparados"]:
            el.append(Paragraph(escape(f"Pendiente {n['regla']} {n['evidencia']}: {n['instruccion']}"), st["BodyText"]))
    doc.build(el, onFirstPage=pie, onLaterPages=pie)
    comprobar_fuentes_embebidas(ruta)
    return ruta


def escribir_informes(informe: dict, carpeta, base: str = "informe_ectd", reparacion: Optional[dict] = None) -> Dict[str, Path]:
    """Escribe JSON, HTML y PDF desde el MISMO dict. Devuelve las rutas."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    j, h, p = carpeta / f"{base}.json", carpeta / f"{base}.html", carpeta / f"{base}.pdf"
    j.write_text(json.dumps({"validacion": informe, "reparacion": reparacion} if reparacion else informe,
                            indent=2, ensure_ascii=False), encoding="utf-8", newline="")
    h.write_text(a_html(informe, reparacion), encoding="utf-8", newline="")
    a_pdf(informe, p, reparacion)
    return {"json": j, "html": h, "pdf": p}
