"""Motor de reglas declarativo: carga rules/*.yaml, ejecuta checkers, produce un informe JSON estructurado."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import unquote

import yaml
from lxml import etree

from .checkers import REGISTRO
from .checkers.checksums import ArbitroError
from .checkers.comun import NoAplicable

VERSION = "0.8.1"
SPEC = "ICH eCTD 3.2.2"
XLINK_NS = ("http://www.w3.org/1999/xlink", "http://www.w3c.org/1999/xlink")
RULES_DIR = Path(__file__).parent / "rules"
# Severidad: la de la FDA, declarada como tal en cada informe (decision del dueno, 26-oct). NO es la severidad de la EMA.
SEVERIDAD_FUENTE = ("FDA Specifications for eCTD Validation Criteria v4.6 (High -> error; Medium/Low -> warning). "
                    "This is the FDA severity, applied as such; it is NOT the EMA severity.")
# Regiones pedidas con --region que NO tienen reglas: se dicen, nunca pasan en silencio ni se tratan como otra region.
REGION_NO_EVALUADA = {"eu": "EU: not evaluated (EMA v8.x criteria not implemented)"}

AVISO_PREPARATORIO = (
    "This is a PREPARATORY tool for regulatory submissions. It checks and prepares materials BEFORE submission; "
    "it does not submit to, and is not endorsed, certified or validated by, any regulatory agency (FDA, EMA or "
    "other). Outputs are drafts for review by qualified professionals; acceptance of any submission is not "
    "guaranteed. The user (sponsor/applicant) retains sole responsibility for the content, accuracy and "
    "regulatory compliance of any submission. Automated repairs are applied only to copies, with a logged list "
    "of changes; originals are never modified. Provided \"AS IS\", without warranty of any kind. Not an "
    "electronic records/signatures system under 21 CFR Part 11."
)

ALCANCE = {
    "valida": ["checksums MD5 (hojas e index-md5.txt)", "index.xml contra la DTD oficial ICH 3.2",
               "estructura y nombres (ICH 3.2.2)", "referencias y ficheros huerfanos",
               "PDF: apertura, cifrado, version, fuentes embebidas, tamano", "index.xml: BOM, invisibles, codificacion",
               "study tagging files (STF v2.2): DTD oficial, file-tags de la tabla, referencias a hojas, cobertura de la carpeta del estudio",
               "coherencia STF <-> ts.xpt (STUDYID/SPREFID), presencia de ts.xpt y SSTDTC (region us; lector XPT propio)",
               "coherencia SDTM <-> ADaM en la carpeta del estudio: USUBJID de ADNCA/ADPP en DM, un solo STUDYID, trazabilidad SRCDOM/SRCSEQ de ADNCA a PC y EX y de ADPP a PP (valor y PARAMCD); lector XPT propio"],
    "no_valida": ["contenido cientifico", "terminologia CDISC (CORE)", "Modulo 1 regional completo",
                  "ciclo de vida multi-secuencia (modified-file, replace/delete, STF append)",
                  "STF: valid-values.xml y hoja de estilos; CONTENIDO de ts.xpt (solo se valida STUDYID/SPREFID, presencia y SSTDTC)",
                  "conformidad CDISC del ADaM (ningun motor libre trae reglas ADaM; solo se cruza con SDTM)", "eCTD 4.0", "aceptacion por agencia"],
}


def carpetas() -> dict:
    """Tabla carpeta -> elemento DTD (spec 3.2.2). Funcion de frontera para quien genere backbones."""
    import json
    return json.loads((Path(__file__).parent / "spec" / "carpetas_ectd_322.json").read_text(encoding="utf-8"))


class Contexto:
    def __init__(self, root: Path, index_path: Path, tree, leaves: List[dict]):
        self.root = root
        self.index_path = index_path
        self.tree = tree
        self.leaves = leaves
        self.arbitros: Dict[str, dict] = {}

    def resolver(self, href: Optional[str]) -> Optional[Path]:
        if not href:
            return None
        p = (self.root / unquote(href)).resolve()
        try:
            p.relative_to(self.root.resolve())
        except ValueError:
            return None  # href fuera del paquete: nunca se sigue
        return p


def cargar_reglas(directorio: Path = RULES_DIR) -> List[dict]:
    reglas: List[dict] = []
    for f in sorted(Path(directorio).glob("*.yaml")):
        datos = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not isinstance(datos, list) or not datos:
            raise ValueError(f"{f.name}: debe ser una lista no vacia de reglas")
        for r in datos:
            for k in ("id", "codigo_oficial", "severidad", "region", "spec_version", "checker", "params"):
                if k not in r:
                    raise ValueError(f"{f.name}: regla sin campo obligatorio {k!r}: {r}")
            if r["severidad"] not in ("error", "aviso"):
                raise ValueError(f"{f.name}: {r['id']} severidad invalida: {r['severidad']!r}")
            if r["checker"] not in REGISTRO:
                raise ValueError(f"{f.name}: {r['id']} usa un checker inexistente: {r['checker']}")
            if r["params"].get("check") not in REGISTRO[r["checker"]].CHECKS:
                raise ValueError(f"{f.name}: {r['id']} check desconocido: {r['params'].get('check')!r}")
            reglas.append(r)
    ids = [r["id"] for r in reglas]
    if len(ids) != len(set(ids)):
        raise ValueError("ids de regla duplicados")
    return reglas


def _hallazgo_core(codigo: str, mensaje: str, evidencia: str) -> dict:
    return {"regla": codigo, "codigo_oficial": None, "severidad": "error", "evidencia": evidencia,
            "mensaje": mensaje, "accion": "pendiente"}


def _leaves(tree) -> List[dict]:
    out = []
    for el in tree.iter():
        if isinstance(el.tag, str) and etree.QName(el).localname == "leaf":
            href = next((el.get("{%s}href" % ns) for ns in XLINK_NS if el.get("{%s}href" % ns) is not None), None)
            out.append({"id": el.get("ID"), "href": href, "version": el.get("version"),
                        "md5": el.get("checksum"), "md5_tipo": el.get("checksum-type")})
    return out


def validar_paquete(ruta, regiones=()) -> dict:
    """`regiones`: reglas de region concreta (p. ej. "us") que SI se piden; sin pedirlas se declaran no ejecutadas.

    Una region pedida que no tiene reglas (hoy: todas salvo `us`; `eu` por no tener implementados los criterios EMA v8.x) NO se trata
    como otra region: consta en `regiones_no_evaluadas` con su motivo y como aviso ECTD-CORE-005 (el estado nunca es VALIDO a secas)."""
    regiones = tuple(str(r).strip().lower() for r in regiones)
    root = Path(ruta).resolve()   # una ruta relativa rompia el checker STF (relative_to) al invocar el CLI desde fuera
    reglas = cargar_reglas()
    informe = {
        "herramienta": "ectd_validator", "version": VERSION, "especificacion": SPEC,
        "paquete": str(root), "fecha_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "alcance": ALCANCE, "aviso": AVISO_PREPARATORIO,
        "reglas_cargadas": [r["id"] for r in reglas], "reglas_ejecutadas": [], "reglas_no_ejecutadas": [],
        "hallazgos": [], "arbitros": {}, "hojas_inspeccionadas": 0, "regiones_solicitadas": list(regiones),
        "severidad_fuente": SEVERIDAD_FUENTE, "regiones_no_evaluadas": [],
    }
    con_reglas = {r["region"] for r in reglas} - {"ich", "regional"}
    for reg in regiones:
        if reg not in con_reglas:
            motivo = REGION_NO_EVALUADA.get(reg, "%s: not evaluated (no rules for this region)" % reg.upper())
            informe["regiones_no_evaluadas"].append({"region": reg, "motivo": motivo})
            informe["hallazgos"].append({"regla": "ECTD-CORE-005", "codigo_oficial": None, "severidad": "aviso",
                                         "evidencia": "--region " + reg, "mensaje": motivo, "accion": "pendiente"})

    def no_validable(codigo: str, mensaje: str, evidencia: str, motivo: str) -> dict:
        informe["hallazgos"].append(_hallazgo_core(codigo, mensaje, evidencia))
        informe["reglas_no_ejecutadas"] = [{"regla": r["id"], "motivo": motivo} for r in reglas]
        informe["estado"] = "NO_VALIDABLE"
        return informe

    if not root.is_dir():
        return no_validable("ECTD-CORE-001", "la ruta no es una carpeta", str(root), "paquete no encontrado")
    index = root / "index.xml"
    if not index.is_file():
        return no_validable("ECTD-CORE-001",
                            "no existe index.xml en la raiz de la secuencia: el paquete no se puede validar",
                            "index.xml", "sin index.xml")
    try:
        tree = etree.parse(str(index), etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))
    except etree.XMLSyntaxError as e:
        return no_validable("ECTD-CORE-002", f"index.xml no esta bien formado: {e}", "index.xml",
                            "index.xml mal formado")
    except OSError as e:
        # libxml2 en Linux informa los bytes invalidos como OSError (CI, 16-oct): eso es contenido mal formado; cualquier
        # otro OSError es un fallo de lectura y se dice como tal (no se etiqueta de "mal formado").
        if "Invalid bytes" in str(e):
            return no_validable("ECTD-CORE-002", f"index.xml no esta bien formado: {e}", "index.xml",
                                "index.xml mal formado")
        return no_validable("ECTD-CORE-001", f"no se pudo leer index.xml: {e}", "index.xml", "index.xml ilegible")
    leaves = _leaves(tree)
    if not leaves:
        return no_validable("ECTD-CORE-003",
                            "el backbone no tiene ninguna hoja (leaf): no hay material que verificar",
                            "index.xml", "backbone sin hojas")

    ctx = Contexto(root, index, tree, leaves)
    for r in reglas:
        if r["region"] not in ("ich", "regional") and r["region"] not in regiones:
            informe["reglas_no_ejecutadas"].append(
                {"regla": r["id"], "motivo": "regla de region %r no solicitada (--region %s)" % (r["region"], r["region"])})
            continue
        try:
            informe["hallazgos"].extend(REGISTRO[r["checker"]].run(ctx, r))
        except NoAplicable as e:
            informe["reglas_no_ejecutadas"].append({"regla": r["id"], "motivo": str(e)})
            continue
        except ArbitroError as e:
            informe["hallazgos"].append(_hallazgo_core("ECTD-CORE-004", str(e), r["id"]))
            informe["reglas_no_ejecutadas"].append({"regla": r["id"], "motivo": "arbitro externo fallo"})
            continue
        informe["reglas_ejecutadas"].append(r["id"])
    informe["arbitros"] = ctx.arbitros
    informe["hojas_inspeccionadas"] = len(leaves)
    hay_error = any(h["severidad"] == "error" for h in informe["hallazgos"])
    if any(h["regla"] == "ECTD-CORE-004" for h in informe["hallazgos"]):
        informe["estado"] = "NO_VALIDABLE"  # un arbitro roto no es un paquete con errores ni un paquete valido
    else:
        hay_aviso = any(h["severidad"] == "aviso" for h in informe["hallazgos"])
        informe["estado"] = "CON_ERRORES" if hay_error else ("VALIDO_CON_AVISOS" if hay_aviso else "VALIDO")
    return informe
