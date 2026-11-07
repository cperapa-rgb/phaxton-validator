"""V0-1: motor de reglas + checker de checksums. Cada regla se ve FALLAR sobre un paquete roto por esa regla."""
import json
import os
import pathlib
import re
import subprocess
import sys

import pytest

from ectd_validator import validar_paquete
from ectd_validator.engine import cargar_reglas
from ectd_validator.checkers import checksums as C
import ectd_fixtures as F

REGLA = ("- {{id: {id}, codigo_oficial: null, severidad: {sev}, region: ich, spec_version: '3.2.2', "
         "checker: {checker}, params: {{check: {check}}}}}")
NL = chr(10)
COH = {f"COH-{i:03d}" for i in range(1, 6)}


def _reglas(inf):
    return {h["regla"] for h in inf["hallazgos"]}


def test_paquete_limpio_es_valido_y_dice_que_corrio(tmp_path):
    inf = validar_paquete(F.construir(tmp_path / "0000"))
    assert inf["estado"] == "VALIDO" and inf["hallazgos"] == []
    assert inf["hojas_inspeccionadas"] == 2 and len(inf["reglas_ejecutadas"]) == 20
    # el paquete de juguete no trae STF: las 7 reglas STF-001..007 no tienen material y STF-008 es regional (us) y no se pidio:
    # las 8 NO se ejecutan y se declaran (nunca verde por ausencia)
    stf = {f"STF-{i:03d}" for i in range(1, 12)} | {f"COH-{i:03d}" for i in range(1, 6)}
    assert set(inf["reglas_ejecutadas"]) == set(inf["reglas_cargadas"]) - stf
    assert {r["regla"] for r in inf["reglas_no_ejecutadas"]} == stf


CASOS = [("CHK-001", {"CHK-001"}, "CON_ERRORES"), ("CHK-002", {"CHK-002", "BBN-001"}, "CON_ERRORES"),  # la DTD tambien exige checksum
         ("CHK-003", {"CHK-003"}, "CON_ERRORES"), ("CHK-003-AUSENTE", {"CHK-003"}, "CON_ERRORES"),
         ("REF-001", {"REF-001"}, "CON_ERRORES"), ("REF-002", {"REF-002"}, "CON_ERRORES"),
         ("BBN-001", {"BBN-001"}, "CON_ERRORES"), ("BBN-001-OPERATION", {"BBN-001"}, "CON_ERRORES"),
         ("BBN-002", {"BBN-002"}, "VALIDO_CON_AVISOS"), ("BBN-003", {"BBN-003"}, "VALIDO_CON_AVISOS"),
         ("BBN-004", {"BBN-004"}, "CON_ERRORES"), ("STR-001", {"STR-001"}, "CON_ERRORES"),
         ("STR-001-F-65", {"STR-001"}, "CON_ERRORES"), ("STR-001-F-SINEXT", {"STR-001"}, "CON_ERRORES"),
         ("STR-001-F-DOSEXT", {"STR-001"}, "CON_ERRORES"), ("STR-001-DIR-PUNTO", {"STR-001"}, "CON_ERRORES"),
         ("STR-001-VALIDO-64", set(), "VALIDO"),  # el borde: 64 caracteres es valido, 65 no
         ("PDF-001", {"PDF-001"}, "CON_ERRORES"), ("PDF-001-VACIO", {"PDF-001", "PDF-005"}, "CON_ERRORES"),
         ("PDF-002", {"PDF-002"}, "CON_ERRORES"), ("PDF-003", {"PDF-003"}, "VALIDO_CON_AVISOS"),
         ("PDF-004", {"PDF-004"}, "VALIDO_CON_AVISOS"), ("PDF-004-LIMPIO", set(), "VALIDO"),
         ("PDF-006", {"PDF-006"}, "VALIDO_CON_AVISOS"),
         ("BBN-005-BOM", {"BBN-005"}, "VALIDO_CON_AVISOS"), ("BBN-005-INVISIBLE", {"BBN-005"}, "VALIDO_CON_AVISOS"),
         ("BBN-005-LATIN1", {"BBN-005"}, "VALIDO_CON_AVISOS"), ("BBN-005-ZWJ", {"BBN-005"}, "VALIDO_CON_AVISOS"),
         ("PDF-004-M-FORM", {"PDF-004"}, "VALIDO_CON_AVISOS"), ("PDF-004-M-TYPE0", {"PDF-004"}, "VALIDO_CON_AVISOS"),
         ("PDF-004-M-HEREDADO", {"PDF-004"}, "VALIDO_CON_AVISOS"), ("PDF-004-M-TYPE3", set(), "VALIDO"),
         ("PDF-004-M-FORM-OK", set(), "VALIDO"), ("PDF-004-M-TYPE0-OK", set(), "VALIDO"),
         ("PDF-004-M-MALFORMADO", {"PDF-004"}, "CON_ERRORES"),   # no inspeccionable: error, no verde ni excepcion
         ("PDF-VERSION-CATALOGO", {"PDF-003"}, "VALIDO_CON_AVISOS"),
         ("STR-003", {"STR-003", "REF-002"}, "CON_ERRORES")]


@pytest.mark.parametrize("defecto,esperado,estado", CASOS)
def test_cada_regla_falla_sobre_su_paquete_roto_y_no_dispara_las_demas(tmp_path, defecto, esperado, estado):
    inf = validar_paquete(F.roto(tmp_path / "0000", defecto))
    assert _reglas(inf) == esperado
    assert inf["estado"] == estado


def test_toda_regla_cargada_tiene_un_caso_roto():
    # Excepciones explicitas: CHK-004 -> test_el_arbitro_b_detecta_una_discrepancia (monkeypatch del arbitro);
    # STR-002 -> test_str_002_* (limite reducido: MAX_PATH de Windows impide crear >230 caracteres bajo el temporal).
    excepciones = {"CHK-004": "test_el_arbitro_b_detecta_una_discrepancia", "STR-002": "test_str_002_la_ruta_larga",
                   "PDF-005": "test_pdf_005_el_tamano_se_detecta_con_el_umbral_de_la_regla"}
    # STF-001..008: casos rotos sobre un paquete real con STF en tests/test_stf.py (necesitan un STF, que el paquete de juguete no trae)
    excepciones.update({f"STF-00{i}": "tests/test_stf_sample_package.py" for i in (1, 2, 3, 4, 7, 8)})
    excepciones.update({"STF-009": "tests/test_stf_sample_package.py"})
    # STF-005, STF-006, STF-010 y STF-011 NO tienen caso roto en este repo (sus tests vivian en la suite de Phaxton, ligados a su
    # constructor de paquetes): deuda declarada en docs/KNOWN_GAPS.md, no cubierta
    sin_caso = {f"STF-{i:03d}" for i in (5, 6, 10, 11)}
    # COH-001..005: casos rotos en tests/test_coherencia.py (necesitan XPT de ADaM y de SDTM, que el paquete de juguete no trae)
    fuente_coh = (pathlib.Path(__file__).parent / "test_coherencia.py").read_text(encoding="utf-8")
    for i in range(1, 6):
        assert "def test_coh_00%d_" % i in fuente_coh, i
        excepciones["COH-00%d" % i] = "test_coherencia.py::test_coh_00%d" % i
    for nombre in excepciones.values():
        if "::" in nombre:
            continue
        if nombre.endswith(".py"):
            fuente = (pathlib.Path(__file__).parent / pathlib.Path(nombre).name).read_text(encoding="utf-8")
            for regla, n in [(k, v) for k, v in excepciones.items() if v == nombre]:
                assert re.search(r"def test_stf_%s|def test_stf_\d{3}_y_%s" % (regla[-3:], regla[-3:]), fuente), regla
            continue
        assert nombre in globals() or any(k.startswith(nombre) for k in globals()), nombre
    cubiertas = set().union(*(c[1] for c in CASOS)) | set(excepciones)
    assert cubiertas | sin_caso >= {r["id"] for r in cargar_reglas()}
    assert not (cubiertas & sin_caso)


def test_str_002_la_ruta_larga_se_detecta_con_el_limite_de_la_regla(tmp_path):
    from ectd_validator.checkers import estructura
    from ectd_validator.engine import Contexto
    d = F.construir(tmp_path / "0000")
    ctx = Contexto(d, d / "index.xml", None, [])
    regla = {"id": "STR-002", "codigo_oficial": None, "severidad": "error", "params": {"check": "ruta", "max_ruta": 40}}
    hall = estructura.run(ctx, regla)
    assert hall and all(h["regla"] == "STR-002" for h in hall)
    mas_larga = max(len(p.relative_to(d).as_posix()) for p in d.rglob("*"))
    regla["params"]["max_ruta"] = mas_larga          # borde: justo en el limite es valido
    assert estructura.run(ctx, regla) == []
    regla["params"]["max_ruta"] = mas_larga - 1      # un caracter menos: la mas larga ya no cabe
    assert [h["evidencia"] for h in estructura.run(ctx, regla)] and len(estructura.run(ctx, regla)) >= 1
    real = [r for r in cargar_reglas() if r["id"] == "STR-002"][0]
    assert real["params"]["max_ruta"] == 230  # el limite de la especificacion 3.2.2


def test_el_backbone_dtd_se_valida_con_la_dtd_versionada_aunque_el_paquete_no_traiga_util(tmp_path):
    d = F.roto(tmp_path / "0000", "BBN-003")
    assert "BBN-001" not in _reglas(validar_paquete(d))


def test_href_con_el_namespace_xlink_del_estandar_w3_org_tambien_se_lee(tmp_path):
    d = F.construir(tmp_path / "0000")
    idx = (d / "index.xml").read_text(encoding="utf-8").replace("w3c.org", "w3.org")
    F._escribir_index(d, idx)  # recalcula index-md5.txt: solo cambia el espacio de nombres
    inf = validar_paquete(d)
    assert inf["hojas_inspeccionadas"] == 2 and "REF-001" not in _reglas(inf)
    assert _reglas(inf) == {"BBN-001"}  # el lector lo tolera; la DTD oficial fija w3c.org y lo marca


def test_sin_index_xml_es_error_claro_nunca_cero_hallazgos(tmp_path):
    (tmp_path / "0000").mkdir()
    inf = validar_paquete(tmp_path / "0000")
    assert inf["estado"] == "NO_VALIDABLE"
    assert [h["regla"] for h in inf["hallazgos"]] == ["ECTD-CORE-001"]
    assert inf["reglas_ejecutadas"] == [] and len(inf["reglas_no_ejecutadas"]) == len(inf["reglas_cargadas"])


def test_ruta_inexistente_y_xml_roto_y_backbone_vacio(tmp_path):
    assert validar_paquete(tmp_path / "no_existe")["estado"] == "NO_VALIDABLE"
    d = tmp_path / "x"
    d.mkdir()
    (d / "index.xml").write_text("<a><b></a>", encoding="utf-8")
    assert _reglas(validar_paquete(d)) == {"ECTD-CORE-002"}
    (d / "index.xml").write_text("<ectd/>", encoding="utf-8")
    inf = validar_paquete(d)
    assert inf["estado"] == "NO_VALIDABLE" and _reglas(inf) == {"ECTD-CORE-003"}


def test_href_fuera_del_paquete_no_se_sigue_aunque_exista_y_su_md5_cuadre(tmp_path):
    d = F.construir(tmp_path / "0000")
    (tmp_path / "fuera.pdf").write_bytes(F.FICHEROS[F.PDF])  # existe y su MD5 coincide: solo el confinamiento frena
    idx = (d / "index.xml").read_text(encoding="utf-8").replace(F.PDF, "../fuera.pdf")
    (d / "index.xml").write_text(idx, encoding="utf-8", newline="")
    inf = validar_paquete(d)
    msgs = [h["mensaje"] for h in inf["hallazgos"] if h["regla"] == "REF-001"]
    assert msgs and "fuera del paquete" in msgs[0]
    assert "CHK-001" not in _reglas(inf)  # el fichero externo no se hashea


def test_el_arbitro_b_detecta_una_discrepancia(tmp_path, monkeypatch):
    d = F.construir(tmp_path / "0000")
    monkeypatch.setattr(C, "arbitro_externo", lambda: ("md5sum", ["md5sum"]))
    monkeypatch.setattr(C, "md5_externo", lambda n, p, f: "f" * 32)
    assert "CHK-004" in _reglas(validar_paquete(d))


def test_sin_arbitro_externo_se_declara_arbitro_unico(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "arbitro_externo", lambda: None)
    inf = validar_paquete(F.construir(tmp_path / "0000"))
    assert inf["estado"] == "VALIDO" and inf["arbitros"]["md5"]["estado"] == "ARBITRO_UNICO"


@pytest.mark.parametrize("nombre", ["md5sum", "openssl", "certutil"])
def test_cada_arbitro_disponible_arbitra_un_valor_conocido(tmp_path, nombre):
    disp = dict(C.arbitros_disponibles())
    if nombre not in disp:
        pytest.skip(f"{nombre} no esta en este equipo")
    p = tmp_path / "x.bin"
    p.write_bytes(b"abc")
    assert C.md5_externo(nombre, disp[nombre], p) == "900150983cd24fb0d6963f7d28e17f72"


def test_hay_al_menos_un_arbitro_real(tmp_path):
    if C.arbitro_externo() is None:
        if os.environ.get("PHX_REQUIRE_XPORTR") == "1":
            pytest.fail("gate de cierre: ningun arbitro externo (verde por ausencia prohibido)")
        pytest.skip("sin arbitro externo")
    inf = validar_paquete(F.construir(tmp_path / "0000"))
    assert inf["estado"] == "VALIDO" and inf["arbitros"]["md5"]["estado"] == "DOS_ARBITROS"


def test_un_arbitro_roto_es_no_validable_no_valido_ni_con_errores(tmp_path, monkeypatch):
    d = F.construir(tmp_path / "0000")
    monkeypatch.setattr(C, "arbitro_externo", lambda: ("md5sum", ["md5sum"]))

    def roto(n, pre, p):
        raise C.ArbitroError("simulado")
    monkeypatch.setattr(C, "md5_externo", roto)
    inf = validar_paquete(d)
    assert inf["estado"] == "NO_VALIDABLE" and "ECTD-CORE-004" in _reglas(inf)
    assert {"regla": "CHK-004", "motivo": "arbitro externo fallo"} in inf["reglas_no_ejecutadas"]


def test_md5_externo_rc_distinto_de_cero_salida_basura_y_timeout_lanzan(tmp_path, monkeypatch):
    class R:
        def __init__(self, rc, out):
            self.returncode, self.stdout, self.stderr = rc, out, "e"

    monkeypatch.setattr(C.subprocess, "run", lambda *a, **k: R(1, ""))
    with pytest.raises(C.ArbitroError):
        C.md5_externo("md5sum", ["md5sum"], tmp_path / "x")
    monkeypatch.setattr(C.subprocess, "run", lambda *a, **k: R(0, "no hay hash"))
    with pytest.raises(C.ArbitroError):
        C.md5_externo("openssl", ["openssl", "md5"], tmp_path / "x")

    def tarda(*a, **k):
        raise C.subprocess.TimeoutExpired("md5sum", 60)
    monkeypatch.setattr(C.subprocess, "run", tarda)
    with pytest.raises(C.ArbitroError):
        C.md5_externo("md5sum", ["md5sum"], tmp_path / "x")


@pytest.mark.parametrize("texto,patron", [
    ("- {id: X-1, severidad: error}", "campo obligatorio"),
    ("", "lista no vacia"),
    (REGLA.format(id="X-1", sev="error", checker="inexistente", check="leaf_md5"), "checker inexistente"),
    (REGLA.format(id="X-1", sev="grave", checker="checksums", check="leaf_md5"), "severidad invalida"),
    (REGLA.format(id="X-1", sev="error", checker="checksums", check="no_existe"), "check desconocido"),
])
def test_el_motor_rechaza_reglas_invalidas(tmp_path, texto, patron):
    (tmp_path / "r.yaml").write_text(texto + NL, encoding="utf-8")
    with pytest.raises(ValueError, match=patron):
        cargar_reglas(tmp_path)


def test_el_motor_rechaza_ids_duplicados(tmp_path):
    r = REGLA.format(id="X-1", sev="error", checker="checksums", check="leaf_md5")
    (tmp_path / "a.yaml").write_text(r + NL, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(r + NL, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicados"):
        cargar_reglas(tmp_path)


def test_index_md5_con_dos_hashes_o_basura_es_formato_invalido(tmp_path):
    d = F.construir(tmp_path / "0000")
    h = (d / "index-md5.txt").read_text(encoding="utf-8").strip()
    (d / "index-md5.txt").write_text(h + NL + "0" * 32 + NL, encoding="utf-8", newline="")
    assert "CHK-003" in _reglas(validar_paquete(d))
    (d / "index-md5.txt").write_text("basura " + h, encoding="utf-8", newline="")
    assert "CHK-003" in _reglas(validar_paquete(d))
    (d / "index-md5.txt").write_text(h + "  index.xml" + NL, encoding="utf-8", newline="")
    assert validar_paquete(d)["estado"] == "VALIDO"


def test_el_aviso_es_el_disclaimer_del_readme_en_cada_informe(tmp_path):
    readme = pathlib.Path(__file__).resolve().parent.parent / "README.md"
    texto = readme.read_text(encoding="utf-8").split(chr(10) + "---" + chr(10))[-1]
    esperado = " ".join(texto.split())
    assert len(esperado) > 500
    assert " ".join(validar_paquete(F.construir(tmp_path / "0000"))["aviso"].split()) == esperado
    assert " ".join(validar_paquete(tmp_path / "nada")["aviso"].split()) == esperado
    out = tmp_path / "i.json"
    subprocess.run([sys.executable, "-m", "ectd_validator", str(tmp_path / "0000"), "--json", str(out)], check=True)
    assert " ".join(json.loads(out.read_text(encoding="utf-8"))["aviso"].split()) == esperado


def test_el_esquema_json_tiene_las_mismas_claves_en_todos_los_estados(tmp_path):
    ok = validar_paquete(F.construir(tmp_path / "0000"))
    mal = validar_paquete(tmp_path / "nada")
    assert set(ok) == set(mal)


def test_cli_codigos_de_salida_y_json(tmp_path):
    d = F.construir(tmp_path / "0000")
    out = tmp_path / "inf.json"
    cmd = [sys.executable, "-m", "ectd_validator"]
    assert subprocess.run(cmd + [str(d), "--json", str(out)]).returncode == 0
    assert json.loads(out.read_text(encoding="utf-8"))["estado"] == "VALIDO"
    F.roto(tmp_path / "r", "CHK-001")
    assert subprocess.run(cmd + [str(tmp_path / "r"), "--json", str(out)]).returncode == 1
    assert subprocess.run(cmd + [str(tmp_path / "nada"), "--json", str(out)]).returncode == 2


def test_autocontenido_no_importa_nada_del_core():
    patron = re.compile(r"^\s*(from|import)\s+(src|engines|services|tests)\b", re.M)
    raiz = pathlib.Path(__file__).resolve().parent.parent / "ectd_validator"
    ficheros = list(raiz.rglob("*.py"))
    assert len(ficheros) >= 5
    for f in ficheros:
        assert not patron.search(f.read_text(encoding="utf-8")), f


def test_el_sha256_de_la_dtd_versionada_es_el_de_procedencia():
    import re as _re
    from ectd_validator.checkers import backbone
    md = (pathlib.Path(backbone.DTD_OFICIAL).parent / "PROCEDENCIA.md").read_text(encoding="utf-8")
    fijado = _re.search(r"normalizado a LF: ([0-9a-f]{64})", md).group(1)
    assert backbone.sha256_lf(backbone.DTD_OFICIAL) == fijado


def test_bbn_004_tolera_fines_de_linea_pero_no_un_byte_cambiado(tmp_path):
    from ectd_validator.checkers import backbone
    d = F.construir(tmp_path / "0000")
    dtd = d / "util" / "dtd" / "ich-ectd-3-2.dtd"
    original = backbone.DTD_OFICIAL.read_bytes()
    dtd.write_bytes(original.replace(bytes([13, 10]), bytes([10])))   # misma DTD con LF
    assert "BBN-004" not in _reglas(validar_paquete(d))
    dtd.write_bytes(original.replace(b"leaf", b"leef", 1))            # un byte distinto
    assert "BBN-004" in _reglas(validar_paquete(d))


def test_dtd_que_no_valida_sin_errores_legibles_nunca_es_verde(tmp_path, monkeypatch):
    from ectd_validator.checkers import backbone

    class DtdFalsa:
        error_log = type("L", (), {"filter_from_errors": lambda self: [], "__str__": lambda self: "log vacio"})()

        def __init__(self, *_a, **_k):
            pass

        def validate(self, _tree):
            return False
    monkeypatch.setattr(backbone.etree, "DTD", DtdFalsa)
    inf = validar_paquete(F.construir(tmp_path / "0000"))
    assert "BBN-001" in _reglas(inf) and inf["estado"] == "CON_ERRORES"


def test_sin_pdfs_las_reglas_pdf_no_se_ejecutan_y_se_declara(tmp_path):
    inf = validar_paquete(F.roto(tmp_path / "0000", "SIN-PDF"))
    pdf = [r for r in inf["reglas_no_ejecutadas"] if r["regla"].startswith("PDF")]   # STF-* y COH-*: sin su material, aparte
    ids = [r["regla"] for r in pdf]
    assert ids == ["PDF-001", "PDF-002", "PDF-003", "PDF-004", "PDF-005", "PDF-006"]
    assert not set(ids) & set(inf["reglas_ejecutadas"])
    assert "ningun PDF" in pdf[0]["motivo"]


def test_pdf_005_el_tamano_se_detecta_con_el_umbral_de_la_regla(tmp_path):
    from ectd_validator.checkers import pdf
    from ectd_validator.engine import Contexto
    d = F.construir(tmp_path / "0000")
    ctx = Contexto(d, d / "index.xml", None, [{"id": "l", "href": F.PDF, "md5": None, "md5_tipo": None}])
    n = (d / F.PDF).stat().st_size
    regla = {"id": "PDF-005", "codigo_oficial": None, "severidad": "aviso", "params": {"check": "tamano", "max_mb": 1}}
    pdfs = [(F.PDF, d / F.PDF)]
    assert pdf._tamano(ctx, regla, pdfs) == []
    regla["params"]["max_mb"] = (n - 1) / 1048576  # un byte menos que el fichero: ya supera
    assert len(pdf._tamano(ctx, regla, pdfs)) == 1
    regla["params"]["max_mb"] = n / 1048576        # justo en el limite: valido
    assert pdf._tamano(ctx, regla, pdfs) == []
    real = [r for r in cargar_reglas() if r["id"] == "PDF-005"][0]
    assert real["params"]["max_mb"] == 100 and real["severidad"] == "aviso"


def test_las_reglas_regionales_estan_marcadas_y_son_avisos():
    reg = {r["id"]: r for r in cargar_reglas() if r["region"] == "regional"}
    assert set(reg) == {"PDF-003", "PDF-005", "PDF-006"} and all(r["severidad"] == "aviso" for r in reg.values())


def test_pdf_referenciado_pero_ausente_no_se_declara_como_sin_pdfs(tmp_path):
    inf = validar_paquete(F.roto(tmp_path / "0000", "PDF-REF-AUSENTE"))
    assert "REF-001" in _reglas(inf) and inf["estado"] == "CON_ERRORES"
    motivos = {r["regla"]: r["motivo"] for r in inf["reglas_no_ejecutadas"]}
    assert set(motivos) - {f"STF-{i:03d}" for i in range(1, 12)} - COH == {"PDF-001", "PDF-002", "PDF-003", "PDF-004", "PDF-005", "PDF-006"}
    assert all("ninguno accesible" in m for k, m in motivos.items() if k.startswith("PDF"))


def test_pdf_truncado_se_registra_su_resultado_real(tmp_path):
    # pypdf (strict=False) puede reconstruir un PDF truncado: PDF-001 significa "pypdf lo lee", no "es valido".
    inf = validar_paquete(F.roto(tmp_path / "0000", "PDF-TRUNCADO"))
    assert inf["estado"] in ("CON_ERRORES", "VALIDO", "VALIDO_CON_AVISOS")  # documentado en el informe
    assert not _reglas(inf) - {"PDF-001", "PDF-004"}


@pytest.mark.parametrize("nombre,exenta", [
    ("Times-Roman", True), ("TimesNewRomanPSMT", True), ("TimesNewRoman", True), ("Arial-BoldMT", True),
    ("ArialMT", True), ("Courier", True), ("CourierNew", True), ("Helvetica-Bold", True), ("Symbol", True),
    ("Timesheet", False), ("ArialUnicodeMS", False), ("Couriersans-Custom", False), ("Garamond", False)])
def test_familias_exentas_con_borde(nombre, exenta):
    from ectd_validator.checkers import pdf
    assert bool(pdf.EXENTA.match(nombre.lower().replace(" ", ""))) is exenta


def test_severidad_de_ref_002_y_bbn_003_viene_de_los_criterios_de_la_fda_con_su_codigo():
    """Director 16-oct: severidad con fuente, no a ojo. FDA 1306 (High) -> error; FDA 1119 (Medium) -> aviso. Nunca error sin fuente."""
    from ectd_validator.engine import cargar_reglas
    reglas = {r["id"]: r for r in cargar_reglas()}
    assert (reglas["REF-002"]["codigo_oficial"], reglas["REF-002"]["severidad"]) == ("FDA 1306", "error")
    assert (reglas["BBN-003"]["codigo_oficial"], reglas["BBN-003"]["severidad"]) == ("FDA 1119", "aviso")
    for i in ("REF-002", "BBN-003"):
        assert "Specifications for eCTD Validation Criteria v4.6" in reglas[i]["descripcion"]
    # una regla con severidad error y sin codigo oficial seria 'a ojo': las que ya eran error sin codigo son del DTD/estructura (ICH)
    assert reglas["REF-002"]["codigo_oficial"]


def test_certutil_solo_cuenta_como_arbitro_en_windows(monkeypatch):
    # CI Linux: `certutil` existe (NSS) y no calcula hashes; no debe figurar como arbitro MD5
    import shutil
    import sys
    from ectd_validator.checkers import checksums as K
    monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/" + x)
    monkeypatch.setattr(sys, "platform", "linux")
    assert "certutil" not in dict(K.arbitros_disponibles())
    monkeypatch.setattr(sys, "platform", "win32")
    assert "certutil" in dict(K.arbitros_disponibles())


def test_un_oserror_de_lxml_por_bytes_invalidos_es_no_validable_no_un_crash(tmp_path, monkeypatch):
    # libxml2 en Linux informa los bytes invalidos como OSError, no como XMLSyntaxError
    from lxml import etree
    d = F.construir(tmp_path / "p")

    def falla(*a, **k):
        raise OSError("Error reading file: Invalid bytes in character encoding")
    monkeypatch.setattr(etree, "parse", falla)
    inf = validar_paquete(d)
    assert inf["estado"] == "NO_VALIDABLE" and inf["hallazgos"][0]["regla"] == "ECTD-CORE-002"


def test_un_oserror_que_no_es_de_bytes_invalidos_se_dice_ilegible_no_mal_formado(tmp_path, monkeypatch):
    from lxml import etree
    d = F.construir(tmp_path / "p")

    def falla(*a, **k):
        raise OSError("Permission denied")
    monkeypatch.setattr(etree, "parse", falla)
    inf = validar_paquete(d)
    assert inf["estado"] == "NO_VALIDABLE" and inf["hallazgos"][0]["regla"] == "ECTD-CORE-001"
    assert "mal formado" not in inf["hallazgos"][0]["mensaje"]


def test_una_ruta_relativa_valida_igual_que_la_absoluta(tmp_path, monkeypatch):
    # fallo real hallado al publicar: el CLI con ruta relativa lanzaba ValueError en el checker STF
    d = F.construir(tmp_path / "0000")
    monkeypatch.chdir(tmp_path)
    rel = validar_paquete("0000")
    ab = validar_paquete(d)
    assert rel["estado"] == ab["estado"] and rel["hojas_inspeccionadas"] == ab["hojas_inspeccionadas"]
    assert [h["regla"] for h in rel["hallazgos"]] == [h["regla"] for h in ab["hallazgos"]]


def test_pdf_006_fast_web_view_exime_1_0_y_1_2_y_no_inspecciona_lo_que_no_se_puede_abrir(tmp_path):
    """PDF-006 (EU 16.BP5, aviso): un PDF sin linealizar se senala, salvo en las carpetas 10-cover y 12-form del Modulo 1; uno cifrado o ilegible lo dicen PDF-002 y PDF-001."""
    from ectd_validator.checkers import pdf
    from ectd_validator.engine import Contexto
    regla = [r for r in cargar_reglas() if r["id"] == "PDF-006"][0]
    assert regla["codigo_oficial"] == "EU 16.BP5" and regla["severidad"] == "aviso" and regla["region"] == "regional"
    sin, con, cif, roto = tmp_path / "sin.pdf", tmp_path / "con.pdf", tmp_path / "cif.pdf", tmp_path / "roto.pdf"
    sin.write_bytes(F.pdf_bytes(lineal=False))
    con.write_bytes(F.pdf_bytes(lineal=True))
    cif.write_bytes(F.pdf_bytes(cifrar=True))
    roto.write_bytes(b"%PDF-1.4" + b"\n" + b"esto no es un pdf")
    ctx = Contexto(tmp_path, tmp_path / "index.xml", None, [])
    hojas = [("m5/53/a.pdf", sin), ("m5/53/b.pdf", con), ("m1/eu/10-cover/c.pdf", sin), ("m1/eu/12-form/d.pdf", sin), ("m1/eu/13-other/e.pdf", sin), ("m5/53/f.pdf", cif), ("m5/53/g.pdf", roto)]
    hall = pdf._fwv(ctx, regla, hojas)
    assert sorted(h["evidencia"] for h in hall) == ["m1/eu/13-other/e.pdf", "m5/53/a.pdf"]            # solo los no exentos, legibles y sin linealizar
    assert all(h["regla"] == "PDF-006" and h["severidad"] == "aviso" for h in hall)


def _lineal_con_actualizacion_incremental(destino):
    """PDF linealizado al que se anade una actualizacion incremental: conserva la marca /Linearized y deja de estar linealizado (lo ve qpdf y Acrobat)."""
    from io import BytesIO
    from pypdf import PdfWriter
    destino.write_bytes(F.pdf_bytes(lineal=True))
    w = PdfWriter(str(destino), incremental=True)
    w.add_metadata({"/Title": "actualizado"})
    w.write(str(destino))


def test_pdf_006_no_se_deja_enganar_por_la_marca_sola(tmp_path):
    """La marca /Linearized en los primeros bytes no basta: una actualizacion incremental y un comentario de cabecera la conservan sin que el PDF este linealizado."""
    import pikepdf
    from ectd_validator.checkers import pdf
    from ectd_validator.engine import Contexto
    regla = [r for r in cargar_reglas() if r["id"] == "PDF-006"][0]
    incr, falso, bueno = tmp_path / "incr.pdf", tmp_path / "falso.pdf", tmp_path / "bueno.pdf"
    _lineal_con_actualizacion_incremental(incr)
    sin = F.pdf_bytes(lineal=False)
    falso.write_bytes(b"%PDF-1.4" + b"\n% /Linearized\n" + sin.split(b"\n", 1)[1])
    bueno.write_bytes(F.pdf_bytes(lineal=True))
    assert b"/Linearized" in incr.read_bytes()[:1024] and b"/Linearized" in falso.read_bytes()[:1024]            # la marca esta en los dos
    for p in (incr, falso):
        with pikepdf.open(str(p)) as x:
            assert not x.is_linearized, p                                                                           # y ninguno esta linealizado
    ctx = Contexto(tmp_path, tmp_path / "index.xml", None, [])
    hall = pdf._fwv(ctx, regla, [("m5/a/incr.pdf", incr), ("m5/a/falso.pdf", falso), ("m5/a/bueno.pdf", bueno)])
    assert sorted(h["evidencia"] for h in hall) == ["m5/a/falso.pdf", "m5/a/incr.pdf"]


def test_la_reparacion_de_pdf_sale_linealizada_aunque_el_original_no_lo_estuviera(tmp_path):
    import pikepdf
    orig = F.roto(tmp_path / "orig", "PDF-002-PERMISOS")                                  # cifrado de permisos, sin linealizar
    with pikepdf.open(str(orig / F.PDF)) as x:
        assert not x.is_linearized
    from ectd_validator.fixes import reparar
    copia = tmp_path / "copia"
    reparar(orig, copia)
    with pikepdf.open(str(copia / F.PDF)) as x:
        assert x.is_linearized and not x.is_encrypted
    assert validar_paquete(copia)["hallazgos"] == []


def test_el_informe_pdf_del_validador_sale_linealizado_para_el_paquete(tmp_path):
    import pikepdf
    d = F.construir(tmp_path / "0000")
    inf = validar_paquete(d)
    from ectd_validator.report import escribir_informes
    rutas = escribir_informes(inf, tmp_path / "inf")
    with pikepdf.open(str(rutas["pdf"])) as x:
        assert x.is_linearized


@pytest.mark.parametrize("variante", ["completa", "byterange", "tipo_sig"])
def test_pdf_006_un_pdf_firmado_es_exento_y_consta_en_el_informe_no_como_hallazgo(tmp_path, variante):
    """D5: un PDF con /Sig o /ByteRange no se linealiza ni se marca: consta como «firmado, exento» en ctx.exentos."""
    from ectd_validator.checkers import pdf
    from ectd_validator.engine import Contexto
    regla = [r for r in cargar_reglas() if r["id"] == "PDF-006"][0]
    f, sin = tmp_path / "firmado.pdf", tmp_path / "sin.pdf"
    f.write_bytes(F.pdf_bytes(lineal=False))
    F.firmar_sintetico(f, variante)
    sin.write_bytes(F.pdf_bytes(lineal=False))
    ctx = Contexto(tmp_path, tmp_path / "index.xml", None, [])
    hall = pdf._fwv(ctx, regla, [("m5/53/firmado.pdf", f), ("m5/53/sin.pdf", sin)])
    assert [h["evidencia"] for h in hall] == ["m5/53/sin.pdf"]
    assert ctx.exentos == [{"regla": "PDF-006", "evidencia": "m5/53/firmado.pdf", "motivo": "firmado, exento (se reescribiria la firma)"}]


def test_pdf_006_la_palabra_byterange_en_el_texto_no_exime_a_un_pdf_sin_firma(tmp_path):
    """El exento sale de la estructura, no de buscar la palabra: un comentario con /ByteRange y /Sig no libra a un PDF sin linealizar."""
    from ectd_validator.checkers import pdf
    from ectd_validator.engine import Contexto
    regla = [r for r in cargar_reglas() if r["id"] == "PDF-006"][0]
    p = tmp_path / "x.pdf"
    p.write_bytes(F.pdf_bytes(lineal=False))
    F.con_texto_de_firma_sin_firma(p)
    ctx = Contexto(tmp_path, tmp_path / "index.xml", None, [])
    hall = pdf._fwv(ctx, regla, [("m5/53/x.pdf", p)])
    assert [h["evidencia"] for h in hall] == ["m5/53/x.pdf"] and ctx.exentos == []


def test_el_informe_lista_los_pdf_firmados_exentos_y_la_reparacion_no_los_reescribe(tmp_path):
    from ectd_validator.fixes import pdf as fpdf
    from ectd_validator.fixes import FixError
    f = tmp_path / "copia" / "a.pdf"
    f.parent.mkdir()
    f.write_bytes(F.pdf_bytes(lineal=False))
    F.firmar_sintetico(f, "byterange")
    antes = f.read_bytes()
    with pytest.raises(FixError, match="firmado digitalmente"):
        fpdf.reparar(tmp_path / "copia", [{"regla": "PDF-003", "evidencia": "a.pdf"}], [])
    assert f.read_bytes() == antes
