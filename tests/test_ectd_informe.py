"""V0-5: informe HTML/PDF derivado del JSON, aviso preparatorio con guard visto fallar."""
import json
import re

import pytest
from pypdf import PdfReader

import ectd_fixtures as F
from ectd_validator import AVISO_PREPARATORIO, validar_paquete
from ectd_validator.fixes import reparar
from ectd_validator.report import a_html, a_pdf, contiene_aviso, escribir_informes


def _texto_pdf(ruta):
    return "".join(p.extract_text() or "" for p in PdfReader(str(ruta)).pages)


def test_guard_ve_fallar_un_texto_sin_aviso_o_con_aviso_mutilado():
    assert contiene_aviso(AVISO_PREPARATORIO)
    assert not contiene_aviso("informe sin aviso")
    assert not contiene_aviso(AVISO_PREPARATORIO.replace("Part 11", "Part 12"))
    assert not contiene_aviso(AVISO_PREPARATORIO[:-20])


def test_json_html_y_pdf_salen_del_mismo_dict_y_llevan_el_aviso(tmp_path):
    inf = validar_paquete(F.roto(tmp_path / "pkg", "CHK-001"))
    rutas = escribir_informes(inf, tmp_path / "out")
    j = json.loads(rutas["json"].read_text(encoding="utf-8"))
    assert j == inf                                          # el JSON ES el dict
    h = rutas["html"].read_text(encoding="utf-8")
    assert contiene_aviso(h) and "CHK-001" in h and "Con errores" in h
    assert contiene_aviso(_texto_pdf(rutas["pdf"])) and "CHK-001" in _texto_pdf(rutas["pdf"])
    assert j["aviso"] == AVISO_PREPARATORIO


def test_el_aviso_va_en_cada_pagina_del_pdf(tmp_path):
    inf = validar_paquete(F.construir(tmp_path / "pkg"))
    # muchos hallazgos sinteticos para forzar varias paginas
    for i in range(120):
        inf["hallazgos"].append({"regla": "STR-001", "codigo_oficial": None, "severidad": "error",
                                 "evidencia": f"m5/carpeta-{i}/fichero-{i}.pdf",
                                 "mensaje": "mensaje de relleno " * 6, "accion": "pendiente"})
    a_pdf(inf, tmp_path / "x.pdf")
    paginas = PdfReader(str(tmp_path / "x.pdf")).pages
    assert len(paginas) >= 3
    for i, p in enumerate(paginas):
        assert contiene_aviso(p.extract_text() or ""), f"pagina {i + 1} sin aviso"


def test_html_escapa_el_contenido_de_los_hallazgos(tmp_path):
    inf = validar_paquete(F.construir(tmp_path / "pkg"))
    inf["hallazgos"].append({"regla": "STR-001", "codigo_oficial": None, "severidad": "error",
                             "evidencia": "<script>alert(1)</script>", "mensaje": "a & b", "accion": "pendiente"})
    h = a_html(inf)
    assert "<script>alert(1)</script>" not in h and "&lt;script&gt;" in h and "a &amp; b" in h


def test_informe_de_no_validable_tambien_lleva_aviso(tmp_path):
    inf = validar_paquete(tmp_path / "no_existe")
    rutas = escribir_informes(inf, tmp_path / "out")
    assert contiene_aviso(rutas["html"].read_text(encoding="utf-8"))
    assert contiene_aviso(_texto_pdf(rutas["pdf"]))
    assert "No validable" in rutas["html"].read_text(encoding="utf-8")


def test_informe_con_reparacion_lista_cambios_y_pendientes(tmp_path):
    rep = reparar(F.roto(tmp_path / "o", "CHK-001"), tmp_path / "c")
    rutas = escribir_informes(rep["validacion_original"], tmp_path / "out", reparacion=rep)
    h = rutas["html"].read_text(encoding="utf-8")
    assert "Reparacion (en copia)" in h and "index-md5.txt" in h and contiene_aviso(h)
    assert contiene_aviso(_texto_pdf(rutas["pdf"]))


def test_el_pdf_del_informe_tiene_todas_las_fuentes_embebidas(tmp_path):
    """Precondicion (b) de la publicacion: el informe del propio validador no lleva Helvetica sin embeber."""
    import fitz
    from ectd_validator.report import comprobar_fuentes_embebidas
    from reportlab.pdfgen import canvas
    informe = {"especificacion": "ICH eCTD 3.2.2", "version": "0", "fecha_utc": "2026-10-15T00:00:00Z",
               "paquete": "x", "estado": "VALIDO", "hojas_inspeccionadas": 1, "reglas_ejecutadas": ["R1"],
               "reglas_cargadas": ["R1"], "hallazgos": [], "reglas_no_ejecutadas": [],
               "alcance": {"valida": ["a"], "no_valida": ["b"]}, "arbitros": []}
    ruta = a_pdf(informe, tmp_path / "informe.pdf")
    fuentes = [f for pg in fitz.open(str(ruta)) for f in pg.get_fonts(full=True)]
    assert fuentes and all(f[1] != "n/a" and "+" in f[3] for f in fuentes), fuentes
    # visto fallar: el guard rechaza un PDF de reportlab por defecto (Helvetica sin embeber)
    malo = tmp_path / "malo.pdf"
    c = canvas.Canvas(str(malo))
    c.drawString(50, 750, "x")
    c.save()
    import pytest
    with pytest.raises(RuntimeError, match="NO embebidas"):
        comprobar_fuentes_embebidas(malo)
