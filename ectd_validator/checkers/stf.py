"""Study Tagging Files (STF v2.2): DTD oficial, file-tags validos, referencias a hojas y cobertura de la carpeta del estudio.

Fuentes (ver spec/PROCEDENCIA.md): DTD oficial ICH STF v2.2 y tabla de file-tags de la ICH eCTD STF Specification v2.6.1,
mas los dos tags de guias del revisor de la FDA Study Data TCG. Sin STF en el paquete, las reglas que lo inspeccionan NO se
ejecutan (NoAplicable): nunca cuentan como verde.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from lxml import etree

from .comun import NoAplicable, hallazgo, rel

SPEC = Path(__file__).resolve().parent.parent / "spec"
DTD_STF = SPEC / "ich-stf-v2-2.dtd"
TAGS_JSON = SPEC / "stf_file_tags.json"
DTD_STF_EN_PAQUETE = "util/dtd/ich-stf-v2-2.dtd"
VERSION_HOJA = "STF version 2.2"
XLINK = ("http://www.w3.org/1999/xlink", "http://www.w3c.org/1999/xlink")


def sha256_lf(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes().replace(bytes([13, 10]), bytes([10]))).hexdigest()


def tags_validos() -> Dict[str, dict]:
    return json.loads(TAGS_JSON.read_text(encoding="utf-8"))["tags"]


def _attr(el, nombre: str) -> Optional[str]:
    for ns in XLINK:
        v = el.get("{%s}%s" % (ns, nombre))
        if v is not None:
            return v
    return None


def _hojas_stf(ctx) -> List[Tuple[dict, Path]]:
    """Hojas del backbone que son STF: version 'STF version ...' o fichero stf-*.xml. [(hoja, ruta)]"""
    out = []
    for h in ctx.leaves:
        p = ctx.resolver(h["href"])
        nombre = (h["href"] or "").rsplit("/", 1)[-1]
        es = (h.get("version") or "").lower().startswith("stf version") or (nombre.startswith("stf-") and nombre.endswith(".xml"))
        if es and p is not None:
            out.append((h, p))
    return out


def _requiere_stf(ctx) -> List[Tuple[dict, Path]]:
    stfs = _hojas_stf(ctx)
    if not stfs:
        raise NoAplicable("el paquete no tiene ningun STF que inspeccionar")
    return stfs


def _parse(p: Path):
    return etree.parse(str(p), etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))


def run(ctx, rule: dict) -> List[dict]:
    return _CHECKS[rule["params"]["check"]](ctx, rule)


def _dtd_valida(ctx, rule):
    if not DTD_STF.is_file():
        raise FileNotFoundError("falta la DTD versionada del STF: %s" % DTD_STF)       # nunca verde por ausencia
    dtd = etree.DTD(str(DTD_STF))
    out = []
    for _h, p in _requiere_stf(ctx):
        r = rel(ctx.root, p) if p.is_file() else str(p)
        if not p.is_file():
            continue                                    # lo dice REF-001
        try:
            arbol = _parse(p)
        except etree.XMLSyntaxError as e:
            out.append(hallazgo(rule, r, "el STF no esta bien formado: %s" % e))
            continue
        if dtd.validate(arbol):
            continue
        det = [e for e in dtd.error_log.filter_from_errors()]
        if not det:
            out.append(hallazgo(rule, r, "no valida contra la DTD STF 2.2 (sin detalle): %s" % dtd.error_log))
        for e in det:
            out.append(hallazgo(rule, "%s:%s" % (r, e.line), e.message))
    return out


def _file_tags(ctx, rule):
    validos = tags_validos()
    out = []
    n = 0
    for _h, p in _requiere_stf(ctx):
        if not p.is_file():
            continue
        try:
            arbol = _parse(p)
        except etree.XMLSyntaxError:
            continue                                    # lo dice STF-001
        for ft in arbol.iter("file-tag"):
            n += 1
            nombre, tipo = ft.get("name"), ft.get("info-type")
            if nombre not in validos:
                out.append(hallazgo(rule, "%s:%s" % (rel(ctx.root, p), ft.sourceline),
                                    "file-tag name=%r no existe en la tabla de la STF spec 2.6.1 ni en la TCG de la FDA" % nombre))
            elif validos[nombre]["info_type"] != tipo:
                out.append(hallazgo(rule, "%s:%s" % (rel(ctx.root, p), ft.sourceline),
                                    "file-tag %r con info-type=%r; la tabla dice %r" % (nombre, tipo, validos[nombre]["info_type"])))
    if n == 0:
        raise NoAplicable("los STF del paquete no contienen ningun file-tag que comprobar")
    return out


def _referencias(ctx, rule):
    """doc-content/@xlink:href = <ruta>/index.xml#<ID> con ID de una hoja existente."""
    ids = {h["id"]: h for h in ctx.leaves if h["id"]}
    out = []
    n = 0
    for _h, p in _requiere_stf(ctx):
        if not p.is_file():
            continue
        try:
            arbol = _parse(p)
        except etree.XMLSyntaxError:
            continue
        for dc in arbol.iter("doc-content"):
            n += 1
            href = _attr(dc, "href") or ""
            ev = "%s:%s" % (rel(ctx.root, p), dc.sourceline)
            if "#" not in href:
                out.append(hallazgo(rule, ev, "doc-content sin fragmento #ID de hoja: %r" % href))
                continue
            ruta, idh = href.rsplit("#", 1)
            destino = (p.parent / ruta).resolve() if ruta else None
            if destino is None or destino != ctx.index_path.resolve():
                out.append(hallazgo(rule, ev, "el href %r no apunta al index.xml de la secuencia" % href))
            if idh not in ids:
                out.append(hallazgo(rule, ev, "el ID %r no es una hoja del backbone" % idh))
    if n == 0:
        raise NoAplicable("los STF del paquete no contienen ningun doc-content")
    return out


def _cobertura(ctx, rule):
    """Toda hoja bajo la carpeta del STF (salvo el propio STF) debe estar etiquetada por algun doc-content."""
    out = []
    for h, p in _requiere_stf(ctx):
        if not p.is_file():
            continue
        try:
            arbol = _parse(p)
        except etree.XMLSyntaxError:
            continue
        etiquetadas = set()
        for dc in arbol.iter("doc-content"):
            href = _attr(dc, "href") or ""
            if "#" in href:
                etiquetadas.add(href.rsplit("#", 1)[1])
        carpeta = p.parent.resolve()
        for o in ctx.leaves:
            po = ctx.resolver(o["href"])
            if po is None or o["id"] == h["id"] or o["id"] in etiquetadas:
                continue
            nombre = (o["href"] or "").rsplit("/", 1)[-1]
            if nombre.startswith("stf-") and nombre.endswith(".xml"):
                continue
            try:
                po.resolve().relative_to(carpeta)
            except ValueError:
                continue
            out.append(hallazgo(rule, o["href"], "hoja del estudio %s sin file-tag en %s" % (carpeta.name, p.name)))
    return out


def _nombre(ctx, rule):
    out = []
    for h, p in _requiere_stf(ctx):
        nombre = p.name
        if not (nombre.startswith("stf-") and nombre.endswith(".xml") and len(nombre) > len("stf-.xml")):
            out.append(hallazgo(rule, h["href"], "el STF debe llamarse stf-<study-id>.xml, se llama %r" % nombre))
    return out


def _version_hoja(ctx, rule):
    out = []
    for h, _p in _requiere_stf(ctx):
        if (h.get("version") or "").lower() != VERSION_HOJA.lower():
            out.append(hallazgo(rule, h["href"], "la hoja del STF debe llevar version=%r, lleva %r"
                                % (VERSION_HOJA, h.get("version"))))
    return out


def _dtd_en_paquete(ctx, rule):
    stfs = _requiere_stf(ctx)
    p = ctx.root / DTD_STF_EN_PAQUETE
    out = []
    if not p.is_file():
        out.append(hallazgo(rule, DTD_STF_EN_PAQUETE, "el paquete no incluye la DTD del STF en util/dtd"))
    elif sha256_lf(p) != sha256_lf(DTD_STF):
        out.append(hallazgo(rule, DTD_STF_EN_PAQUETE, "la DTD del STF del paquete difiere de la oficial ICH STF 2.2"))
    # el DOCTYPE de cada STF debe RESOLVER a esa DTD (la validacion de STF-001 usa la versionada, no la declarada)
    for _h, f in stfs:
        if not f.is_file():
            continue
        try:
            url = _parse(f).docinfo.system_url or ""
        except etree.XMLSyntaxError:
            continue
        destino = (f.parent / url).resolve() if url else None
        if destino != p.resolve():
            out.append(hallazgo(rule, rel(ctx.root, f), "el DOCTYPE apunta a %r y no resuelve a %s" % (url, DTD_STF_EN_PAQUETE)))
    return out


def _sin_stf(ctx, rule):
    """Aviso (region us): hay documentos de estudio en M4/M5 y ningun STF."""
    if _hojas_stf(ctx):
        return []
    # v0: solo datasets de estudio (.xpt) en M4/M5; otros documentos sin STF no se senalan (alcance declarado en la regla)
    estudio = [h["href"] for h in ctx.leaves
               if (h["href"] or "").startswith(("m4/", "m5/")) and (h["href"] or "").lower().endswith(".xpt")]
    if not estudio:
        raise NoAplicable("el paquete no tiene datasets (.xpt) en M4/M5: la exigencia de STF no se evalua")
    return [hallazgo(rule, estudio[0], "hay %d dataset(s) .xpt en M4/M5 y ningun STF; FDA exige un STF por estudio" % len(estudio))]


# ---- lector minimo de XPT v5 (independiente de xportr, pandas y pyreadstat): arbitro de ts.xpt ----------------------
def leer_xpt(ruta: Path) -> Tuple[List[str], List[Dict[str, object]]]:
    """(nombres, filas) de un XPT v5 (SAS Transport). Solo lo necesario: NAMESTR de 140 bytes, caracteres y reales IBM.
    Falla con ValueError ante cualquier cosa que no reconoce: nunca devuelve 'vacio' por no entender el fichero."""
    b = Path(ruta).read_bytes()
    if not b.startswith(b"HEADER RECORD*******LIBRARY HEADER RECORD"):
        raise ValueError("no es un XPT v5 (cabecera de libreria ausente)")
    i = b.find(b"HEADER RECORD*******NAMESTR HEADER RECORD")
    if i < 0:
        raise ValueError("XPT sin cabecera NAMESTR")
    try:
        nvars = int(b[i + 54:i + 58])
    except ValueError as e:
        raise ValueError("numero de variables ilegible en la cabecera NAMESTR") from e
    pos = i + 80
    campos = []
    for k in range(nvars):
        ns = b[pos + 140 * k: pos + 140 * (k + 1)]
        if len(ns) < 140:
            raise ValueError("NAMESTR truncado")
        ntype = int.from_bytes(ns[0:2], "big")
        nlng = int.from_bytes(ns[4:6], "big")
        nombre = ns[8:16].decode("latin-1").strip()
        npos = int.from_bytes(ns[84:88], "big")
        if ntype not in (1, 2) or nlng < 1 or (ntype == 1 and nlng > 8):
            raise ValueError("variable %s con tipo/longitud no valida" % nombre)
        campos.append((nombre, ntype, nlng, npos))
    pos += 140 * nvars
    pos += (-pos) % 80
    j = b.find(b"HEADER RECORD*******OBS", pos - 80 if pos >= 80 else 0)
    if j < 0:
        raise ValueError("XPT sin cabecera OBS")
    pos = j + 80
    largo = sum(c[2] for c in campos)
    if any(npos + nlng > largo for _n, _t, nlng, npos in campos):
        raise ValueError("una variable se sale del registro (NAMESTR incoherente)")
    filas = []
    while pos + largo <= len(b):
        reg = b[pos:pos + largo]
        if reg.strip(b" ") == b"" and len(b) - (pos + largo) < 80:
            pos += largo
            break                                   # relleno final a multiplo de 80
        fila = {}
        for nombre, ntype, nlng, npos in campos:
            raw = reg[npos:npos + nlng]
            if ntype == 2:
                fila[nombre] = raw.decode("latin-1").rstrip(" ")
            else:
                fila[nombre] = _ibm(raw)
        filas.append(fila)
        pos += largo
    if b[pos:].strip(b" ") != b"":
        raise ValueError("XPT truncado o con basura tras el ultimo registro (%d bytes sin interpretar)" % len(b[pos:].strip(b" ")))
    if not filas:
        raise ValueError("el XPT no tiene ninguna observacion")
    return [c[0] for c in campos], filas


def _ibm(raw: bytes) -> Optional[float]:
    """Real IBM de 8 (o menos) bytes -> float. Faltante SAS (byte inicial '.', '_' o A-Z con el resto a cero) -> None."""
    if not raw:
        return None
    if raw[0] in b"._ABCDEFGHIJKLMNOPQRSTUVWXYZ" and raw[1:].strip(b"\x00") == b"":
        return None
    r = raw + b"\x00" * (8 - len(raw))
    signo = -1.0 if r[0] & 0x80 else 1.0
    exp = (r[0] & 0x7F) - 64
    frac = int.from_bytes(r[1:8], "big") / float(1 << 56)
    return signo * frac * (16.0 ** exp)


def _stf_study_id(p: Path) -> Optional[str]:
    try:
        el = _parse(p).find(".//study-id")
    except etree.XMLSyntaxError:
        return None
    return (el.text or "").strip() if el is not None else None


def _ts_de(ctx, stf_path: Path) -> List[Tuple[dict, Path]]:
    """Hojas ts.xpt bajo la carpeta del STF."""
    carpeta = stf_path.parent.resolve()
    out = []
    for h in ctx.leaves:
        if (h["href"] or "").rsplit("/", 1)[-1].lower() != "ts.xpt":
            continue
        p = ctx.resolver(h["href"])
        if p is None:
            continue
        try:
            p.resolve().relative_to(carpeta)
        except ValueError:
            continue
        out.append((h, p))
    return out


def _tags_por_id(p: Path) -> Dict[str, str]:
    try:
        arbol = _parse(p)
    except etree.XMLSyntaxError:
        return {}
    out = {}
    for dc in arbol.iter("doc-content"):
        href = _attr(dc, "href") or ""
        ft = dc.find("file-tag")
        if "#" in href and ft is not None:
            out[href.rsplit("#", 1)[1]] = ft.get("name") or ""
    return out


def _ts_stf_coherencia(ctx, rule):
    """STUDYID de ts.xpt == study-id del STF (TCG, Apendice G); distinto solo si TS declara SPREFID = study-id del STF."""
    out = []
    n_ts = 0
    for _h, p in _requiere_stf(ctx):
        sid = _stf_study_id(p)
        for ht, pt in _ts_de(ctx, p):
            if not pt.is_file():
                continue
            n_ts += 1
            try:
                _cols, filas = leer_xpt(pt)
            except ValueError as e:
                out.append(hallazgo(rule, rel(ctx.root, pt), "no se puede leer ts.xpt para cruzarlo con el STF: %s" % e))
                continue
            studyids = {str(f.get("STUDYID", "")).strip() for f in filas}
            sprefid = {str(f.get("TSVAL", "")).strip() for f in filas if str(f.get("TSPARMCD", "")).strip() == "SPREFID"}
            if sid is None or sid == "":
                out.append(hallazgo(rule, rel(ctx.root, p), "el STF no declara study-id"))
            for s in sorted(studyids):
                if s != sid and sid not in sprefid:
                    out.append(hallazgo(rule, rel(ctx.root, pt),
                                        "STUDYID de TS %r != study-id del STF %r y TS no declara SPREFID con ese valor" % (s, sid)))
    if n_ts == 0:
        raise NoAplicable("no hay ts.xpt bajo la carpeta del STF que cruzar")
    return out


def _ts_presente(ctx, rule):
    """Si el STF etiqueta datasets de tabulacion, debe haber un ts.xpt etiquetado igual (FDA: error 1734)."""
    out = []
    n_con_datasets = 0
    for h, p in _requiere_stf(ctx):
        tags = _tags_por_id(p)
        hay_datasets = any(t == "data-tabulation-dataset" for t in tags.values())
        if not hay_datasets:
            continue
        n_con_datasets += 1
        tiene_ts = False
        for ht, _pt in _ts_de(ctx, p):
            if tags.get(ht["id"]) == "data-tabulation-dataset":
                tiene_ts = True
        if not tiene_ts:
            out.append(hallazgo(rule, rel(ctx.root, p),
                                "el STF etiqueta datasets de tabulacion y no hay un ts.xpt etiquetado data-tabulation-dataset "
                                "en su carpeta (la FDA valida STF + TS)"))
    if n_con_datasets == 0:
        raise NoAplicable("ningun STF etiqueta datasets de tabulacion: la exigencia de TS no aplica")
    return out


def _ssd(ctx, rule):
    """La FDA lee la fecha de inicio del estudio de SSTDTC en ts.xpt: sin fecha valida el aviso es obligado."""
    out = []
    n = 0
    for _h, p in _requiere_stf(ctx):
        for _ht, pt in _ts_de(ctx, p):
            if not pt.is_file():
                continue
            n += 1
            ev = rel(ctx.root, pt)
            try:
                _c, filas = leer_xpt(pt)
            except ValueError as e:
                out.append(hallazgo(rule, ev, "no se pudo leer ts.xpt para comprobar SSTDTC: %s" % e))
                continue
            ssd = [f for f in filas if str(f.get("TSPARMCD", "")).strip() == "SSTDTC"]
            vals = [str(f.get("TSVAL", "")).strip() for f in ssd if str(f.get("TSVAL", "")).strip()]
            if not ssd:
                out.append(hallazgo(rule, ev, "ts.xpt no tiene SSTDTC: la FDA no puede determinar la fecha de inicio del estudio"))
            elif not vals:
                out.append(hallazgo(rule, ev, "SSTDTC sin fecha (TSVALNF=%r): la FDA no podra determinar la fecha de inicio"
                                    % str(ssd[0].get("TSVALNF", "")).strip()))
            else:
                for v in vals:
                    if not re.match(r"^\d{4}-\d{2}-\d{2}", v):
                        out.append(hallazgo(rule, ev, "SSTDTC=%r no es ISO 8601 con al menos AAAA-MM-DD (TCG, nota 82)" % v))
    if n == 0:
        raise NoAplicable("no hay ts.xpt que inspeccionar")
    return out


_CHECKS = {"dtd_valida": _dtd_valida, "ts_stf": _ts_stf_coherencia, "ts_presente": _ts_presente, "ssd": _ssd, "file_tags": _file_tags, "referencias": _referencias, "cobertura": _cobertura,
           "nombre": _nombre, "version_hoja": _version_hoja, "dtd_en_paquete": _dtd_en_paquete, "sin_stf": _sin_stf}
CHECKS = _CHECKS
