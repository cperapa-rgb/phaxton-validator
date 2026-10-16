"""STF / TS rules on a real package (built by the Phaxton suite, committed as a fixture): the baseline must validate, and
each deliberate defect must be seen by the rule that corresponds to it."""
import re
import shutil
from pathlib import Path

import pytest

from ectd_validator import validar_paquete

SAMPLE = Path(__file__).resolve().parent / "fixtures" / "sample_package"


@pytest.fixture()
def pkg(tmp_path):
    d = tmp_path / "ectd"
    shutil.copytree(SAMPLE, d)
    return d


def _stf(d):
    return next(d.rglob("stf-*.xml"))


def _editar(f, a, b, n=1):
    t = f.read_text(encoding="utf-8")
    assert a in t, (f.name, a)
    f.write_text(t.replace(a, b, n), encoding="utf-8")


def _reglas(inf):
    return {h["regla"] for h in inf["hallazgos"]}


def test_la_linea_base_valida_y_ejecuta_las_reglas_stf(pkg):
    inf = validar_paquete(pkg, regiones=("us",))
    assert inf["estado"] in ("VALIDO", "VALIDO_CON_AVISOS"), inf["hallazgos"]
    assert not [h for h in inf["hallazgos"] if h["severidad"] == "error"]
    assert inf["hojas_inspeccionadas"] >= 10                       # not green for inspecting nothing
    no_ejec = {r["regla"] for r in inf["reglas_no_ejecutadas"]}
    assert not {f"STF-{i:03d}" for i in range(1, 12)} & no_ejec    # every STF rule ran


def test_stf_008_sin_pedir_la_region_us_se_declara_no_ejecutada(pkg):
    inf = validar_paquete(pkg)
    no_ejec = {r["regla"]: r["motivo"] for r in inf["reglas_no_ejecutadas"]}
    assert "STF-008" in no_ejec and "no solicitada" in no_ejec["STF-008"]


def test_stf_001_un_elemento_fuera_de_la_dtd(pkg):
    _editar(_stf(pkg), "</study-document>", "<bogus/></study-document>")
    assert "STF-001" in _reglas(validar_paquete(pkg, regiones=("us",)))


def test_stf_002_un_file_tag_inventado(pkg):
    _editar(_stf(pkg), 'name="analysis-dataset"', 'name="tag-inventado"')
    assert "STF-002" in _reglas(validar_paquete(pkg, regiones=("us",)))


def test_stf_003_referencia_a_una_hoja_inexistente(pkg):
    _editar(_stf(pkg), "index.xml#leaf-0007", "index.xml#leaf-9999")
    assert "STF-003" in _reglas(validar_paquete(pkg, regiones=("us",)))


def test_stf_004_una_hoja_sin_etiquetar(pkg):
    t = _stf(pkg).read_text(encoding="utf-8")
    nuevo = re.sub(r'\s*<doc-content xlink:href="[^"]*#leaf-0011">.*?</doc-content>', "", t, count=1, flags=re.S)
    assert nuevo != t
    _stf(pkg).write_text(nuevo, encoding="utf-8")
    assert "STF-004" in _reglas(validar_paquete(pkg, regiones=("us",)))


def test_stf_007_dtd_del_stf_alterada(pkg):
    dtd = next(pkg.rglob("ich-stf-v2-2.dtd"))
    dtd.write_text(dtd.read_text(encoding="utf-8") + "\n<!-- alterada -->\n", encoding="utf-8")
    assert "STF-007" in _reglas(validar_paquete(pkg, regiones=("us",)))


def test_stf_009_study_id_distinto_del_studyid_de_ts(pkg):
    _editar(_stf(pkg), "<study-id>PROT-DG1</study-id>", "<study-id>OTRO-ESTUDIO</study-id>")
    assert "STF-009" in _reglas(validar_paquete(pkg, regiones=("us",)))


def test_ts_ausente_con_stf_presente_no_pasa(pkg):
    next(pkg.rglob("ts.xpt")).unlink()
    inf = validar_paquete(pkg, regiones=("us",))
    assert inf["estado"] == "CON_ERRORES" and "REF-001" in _reglas(inf)


def test_un_xpt_alterado_tras_el_build_se_ve_por_checksum(pkg):
    f = next(pkg.rglob("dm.xpt"))
    b = bytearray(f.read_bytes())
    b[len(b) // 2] ^= 0xFF
    f.write_bytes(bytes(b))
    assert "CHK-001" in _reglas(validar_paquete(pkg, regiones=("us",)))


def test_el_cli_con_ruta_relativa_funciona_sobre_un_paquete_con_stf(pkg, monkeypatch):
    monkeypatch.chdir(pkg.parent)
    inf = validar_paquete(pkg.name, regiones=("us",))
    assert inf["estado"] in ("VALIDO", "VALIDO_CON_AVISOS")
