"""Fixtures del validador eCTD: un paquete LIMPIO (valido contra la DTD oficial ICH 3.2) y variantes ROTAS,
un defecto sembrado por regla."""
import hashlib
import shutil
from pathlib import Path

NL = chr(10)
RAIZ_DTD = Path(__file__).resolve().parent.parent / "ectd_validator" / "spec" / "ich-ectd-3-2.dtd"
BASE = "m5/53-clin-stud-rep/531-rep-biopharm-stud/5311-ba-stud-rep/study-1/"
PDF = BASE + "report.pdf"
XPT = BASE + "dm.xpt"


def pdf_bytes(fuentes=(), version=b"%PDF-1.4", cifrar=False, modo="directo", cat_version=None) -> bytes:
    """PDF real generado con pypdf. fuentes: [(nombre, embebida)].
    modo: directo | form (fuente dentro de un Form XObject) | type0 (descendiente CID) | type3 | heredado (recursos
    en el nodo /Pages) | malformado (Type0 con DescendantFonts vacio)."""
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject
    w = PdfWriter()
    page = w.add_blank_page(612, 792)
    if fuentes:
        fd = DictionaryObject()
        for i, (nombre, embebida) in enumerate(fuentes):
            subtipo = {"type0": "/Type0", "type3": "/Type3"}.get(modo, "/Type1")
            fnt = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject(subtipo),
                                    NameObject("/BaseFont"): NameObject("/" + nombre)})
            desc = None
            if modo != "type3":
                dd = {NameObject("/Type"): NameObject("/FontDescriptor"), NameObject("/FontName"): NameObject("/" + nombre)}
                if embebida:
                    ff = DecodedStreamObject()
                    ff.set_data(b"fontdata")
                    dd[NameObject("/FontFile")] = w._add_object(ff)
                desc = w._add_object(DictionaryObject(dd))
            if modo == "type0":
                cid = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                        NameObject("/Subtype"): NameObject("/CIDFontType2"),
                                        NameObject("/BaseFont"): NameObject("/" + nombre),
                                        NameObject("/FontDescriptor"): desc})
                fnt[NameObject("/DescendantFonts")] = ArrayObject([w._add_object(cid)])
            elif modo == "malformado":
                fnt[NameObject("/Subtype")] = NameObject("/Type0")
                fnt[NameObject("/DescendantFonts")] = ArrayObject([])
            elif desc is not None:
                fnt[NameObject("/FontDescriptor")] = desc
            fd[NameObject("/F%d" % i)] = w._add_object(fnt)
        res = DictionaryObject({NameObject("/Font"): fd})
        if modo == "form":
            form = DecodedStreamObject()
            form.set_data(b"")
            form.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Form"),
                         NameObject("/BBox"): ArrayObject([NumberObject(0), NumberObject(0), NumberObject(10),
                                                           NumberObject(10)]),
                         NameObject("/Resources"): res})
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/XObject"): DictionaryObject({NameObject("/X1"): w._add_object(form)})})
        elif modo == "heredado":
            if "/Resources" in page:
                del page["/Resources"]
            w._root_object["/Pages"][NameObject("/Resources")] = res
        else:
            page[NameObject("/Resources")] = res
    if cat_version:
        w._root_object[NameObject("/Version")] = NameObject("/" + cat_version)
    if version:
        w.pdf_header = version
    if cifrar == "permisos":      # cifrado con contrasena de usuario VACIA: abre sin contrasena
        w.encrypt(user_password="", owner_password="propietario")
    elif cifrar:
        w.encrypt("clave")
    b = BytesIO()
    w.write(b)
    return b.getvalue()


FICHEROS = {PDF: pdf_bytes(fuentes=[("Arial", False), ("Garamond", True)]),
            XPT: b"XPT dummy dm" + NL.encode()}

INDEX = (
    '<?xml version="1.0" encoding="UTF-8"?>' + NL +
    '<!DOCTYPE ectd:ectd SYSTEM "util/dtd/ich-ectd-3-2.dtd">' + NL +
    '<ectd:ectd xmlns:ectd="http://www.ich.org/ectd" xmlns:xlink="http://www.w3c.org/1999/xlink">' + NL +
    '<m5-clinical-study-reports><m5-3-clinical-study-reports><m5-3-1-reports-of-biopharmaceutic-studies>'
    '<m5-3-1-1-bioavailability-study-reports>' + NL + '{hojas}' +
    '</m5-3-1-1-bioavailability-study-reports></m5-3-1-reports-of-biopharmaceutic-studies>'
    '</m5-3-clinical-study-reports></m5-clinical-study-reports>' + NL +
    '</ectd:ectd>' + NL
)
HOJA = ('<leaf ID="{id}" operation="new" checksum="{md5}" checksum-type="md5" xlink:href="{href}">'
        '<title>{id}</title></leaf>' + NL)


def _md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def _escribir_index(d: Path, texto: str):
    b = texto.encode("utf-8")
    (d / "index.xml").write_bytes(b)
    (d / "index-md5.txt").write_text(_md5(b) + NL, encoding="utf-8", newline="")


def construir(destino: Path) -> Path:
    destino.mkdir(parents=True, exist_ok=True)
    hojas = ""
    for i, (rel, datos) in enumerate(FICHEROS.items(), 1):
        p = destino / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(datos)
        hojas += HOJA.format(id=f"leaf{i}", md5=_md5(datos), href=rel)
    (destino / "util" / "dtd").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RAIZ_DTD, destino / "util" / "dtd" / "ich-ectd-3-2.dtd")
    _escribir_index(destino, INDEX.format(hojas=hojas))
    return destino


def _reemplazar_pdf(d: Path, datos: bytes):
    viejo = _md5((d / PDF).read_bytes())
    (d / PDF).write_bytes(datos)
    _reescribir_index(d, lambda s: s.replace(viejo, _md5(datos), 1))


def _reescribir_index(d: Path, f):
    _escribir_index(d, f((d / "index.xml").read_text(encoding="utf-8")))


def roto(destino: Path, defecto: str) -> Path:
    d = construir(destino)
    if defecto == "CHK-001":      # el fichero cambia despues de calcular el MD5
        (d / PDF).write_bytes((d / PDF).read_bytes() + NL.encode() + b"% alterado" + NL.encode())
    elif defecto == "CHK-002":    # una hoja sin checksum
        quitar = ' checksum="%s" checksum-type="md5"' % _md5(FICHEROS[XPT])
        _reescribir_index(d, lambda s: s.replace(quitar, "", 1))
    elif defecto == "CHK-003":    # index-md5.txt no corresponde a index.xml
        (d / "index-md5.txt").write_text("0" * 32 + NL, encoding="utf-8", newline="")
    elif defecto == "CHK-003-AUSENTE":
        (d / "index-md5.txt").unlink()
    elif defecto == "REF-001":    # la hoja apunta a un fichero que no esta
        (d / XPT).unlink()
    elif defecto == "REF-002":    # fichero sin hoja
        (d / "m5" / "sobrante.pdf").write_bytes(b"%PDF-1.4 huerfano")
    elif defecto == "BBN-001":    # elemento que la DTD no admite
        _reescribir_index(d, lambda s: s.replace("</ectd:ectd>", "<m9-inventado/></ectd:ectd>"))
    elif defecto == "BBN-001-OPERATION":  # atributo obligatorio con valor fuera de la enumeracion
        _reescribir_index(d, lambda s: s.replace('operation="new"', 'operation="nuevo"', 1))
    elif defecto == "BBN-002":
        _reescribir_index(d, lambda s: s.replace("util/dtd/ich-ectd-3-2.dtd", "otra/ruta.dtd"))
    elif defecto == "BBN-003":
        shutil.rmtree(d / "util")
    elif defecto == "BBN-004":
        (d / "util" / "dtd" / "ich-ectd-3-2.dtd").write_text("<!-- alterada -->", encoding="utf-8")
    elif defecto == "STR-001":    # nombre con mayusculas y guion bajo, el fichero esta referenciado
        nuevo = BASE + "Informe_Final.pdf"
        (d / PDF).rename(d / nuevo)
        _reescribir_index(d, lambda s: s.replace(PDF, nuevo))
    elif defecto.startswith("STR-001-F-") or defecto == "STR-001-VALIDO-64":
        nombres = {"STR-001-F-65": "a" * 61 + ".pdf", "STR-001-F-SINEXT": "hello", "STR-001-F-DOSEXT": "a.b.pdf",
                   "STR-001-VALIDO-64": "a" * 60 + ".pdf"}
        nuevo = BASE + nombres[defecto]
        (d / PDF).rename(d / nuevo)
        _reescribir_index(d, lambda s: s.replace(PDF, nuevo))
    elif defecto == "STR-001-DIR-PUNTO":
        (d / "m5/53-clin-stud-rep/531-rep-biopharm-stud/5311-ba-stud-rep/study-1").rename(
            d / "m5/53-clin-stud-rep/531-rep-biopharm-stud/5311-ba-stud-rep/study.1")
        _reescribir_index(d, lambda s: s.replace("study-1/", "study.1/"))
    elif defecto == "BBN-005-BOM":
        idx = (d / "index.xml").read_bytes()
        (d / "index.xml").write_bytes(bytes([0xEF, 0xBB, 0xBF]) + idx)
        (d / "index-md5.txt").write_text(_md5((d / "index.xml").read_bytes()) + NL, encoding="utf-8", newline="")
    elif defecto == "BBN-005-INVISIBLE":
        _reescribir_index(d, lambda s: s.replace("<title>leaf1", "<title>" + chr(0x200B) + "leaf1", 1))
    elif defecto == "BBN-005-LATIN1":   # contenido REAL en ISO-8859-1 (e con acento) y declaracion acorde
        txt = (d / "index.xml").read_text(encoding="utf-8").replace('encoding="UTF-8"', 'encoding="ISO-8859-1"', 1)
        txt = txt.replace("<title>leaf1", "<title>informe " + chr(0xE9) + "tico leaf1", 1)
        b = txt.encode("latin-1")
        (d / "index.xml").write_bytes(b)
        (d / "index-md5.txt").write_text(_md5(b) + NL, encoding="utf-8", newline="")
    elif defecto == "BBN-005-ZWJ":
        _reescribir_index(d, lambda s: s.replace("<title>leaf1", "<title>a" + chr(0x200D) + "b leaf1", 1))
    elif defecto == "COMILLAS-SIMPLES":   # hoja con atributos entre comillas simples y MD5 incorrecto
        _reescribir_index(d, lambda s: s.replace('operation="new"', "operation='new'", 1))
        (d / PDF).write_bytes((d / PDF).read_bytes() + NL.encode() + b"% x" + NL.encode())
    elif defecto == "BYTES-INVALIDOS":    # index.xml con bytes que no son UTF-8 y declarado UTF-8
        b = (d / "index.xml").read_bytes().replace(b"<title>leaf1", b"<title>" + bytes([0xFF, 0xFE, 0xFA]) + b"leaf1", 1)
        (d / "index.xml").write_bytes(b)
        (d / "index-md5.txt").write_text(_md5(b) + NL, encoding="utf-8", newline="")
    elif defecto == "SIN-PDF":
        (d / PDF).unlink()
        _reescribir_index(d, lambda s: "".join(x for x in s.splitlines(True) if PDF not in x))
    elif defecto == "PDF-001":
        _reemplazar_pdf(d, b"%PDF-1.4" + NL.encode() + b"esto no es un pdf")
    elif defecto == "PDF-001-VACIO":
        _reemplazar_pdf(d, b"")
    elif defecto == "PDF-002":
        _reemplazar_pdf(d, pdf_bytes(cifrar=True))
    elif defecto == "PDF-002-PERMISOS":
        _reemplazar_pdf(d, pdf_bytes(cifrar="permisos"))
    elif defecto == "PDF-003-ALTA":
        _reemplazar_pdf(d, pdf_bytes(version=b"%PDF-1.9"))
    elif defecto == "PDF-003":
        _reemplazar_pdf(d, pdf_bytes(version=b"%PDF-1.3"))
    elif defecto == "PDF-004":
        _reemplazar_pdf(d, pdf_bytes(fuentes=[("Garamond", False)]))
    elif defecto == "PDF-004-LIMPIO":   # embebida, exentas y subset con prefijo: no debe disparar
        _reemplazar_pdf(d, pdf_bytes(fuentes=[("ABCDEF+Garamond", True), ("TimesNewRoman", False),
                                              ("Courier", False), ("Arial-BoldMT", False)]))
    elif defecto.startswith("PDF-004-M-"):
        modo, embebida = {"PDF-004-M-FORM": ("form", False), "PDF-004-M-TYPE0": ("type0", False),
                          "PDF-004-M-HEREDADO": ("heredado", False), "PDF-004-M-TYPE3": ("type3", False),
                          "PDF-004-M-MALFORMADO": ("malformado", False),
                          "PDF-004-M-TYPE0-OK": ("type0", True), "PDF-004-M-FORM-OK": ("form", True)}[defecto]
        _reemplazar_pdf(d, pdf_bytes(fuentes=[("Garamond", embebida)], modo=modo))
    elif defecto == "PDF-REF-AUSENTE":
        (d / PDF).unlink()
    elif defecto == "PDF-TRUNCADO":
        _reemplazar_pdf(d, FICHEROS[PDF][: len(FICHEROS[PDF]) // 2])
    elif defecto == "PDF-VERSION-CATALOGO":   # cabecera 1.4 pero /Version 1.8 en el catalogo
        _reemplazar_pdf(d, pdf_bytes(version=b"%PDF-1.4", cat_version="1.8"))
    elif defecto == "STR-003":
        (d / "notas.txt").write_text("fuera de sitio", encoding="utf-8")
    else:
        raise ValueError(defecto)
    return d
