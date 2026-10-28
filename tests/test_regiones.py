"""Regiones sin reglas (decision del dueno, 26-oct): `--region eu` NO devuelve lo mismo que `us` en silencio.

Hoy solo `us` tiene reglas regionales. El criterio EMA v8.x no esta implementado: pedir `eu` (o cualquier region sin reglas) se DICE en la salida y en el informe
(`regiones_no_evaluadas`, aviso ECTD-CORE-005) y el estado nunca es VALIDO a secas. La severidad de la FDA consta como tal (`severidad_fuente`)."""
import json
import subprocess
import sys

import pytest

import ectd_fixtures as F
from ectd_validator import engine
from ectd_validator.engine import REGION_NO_EVALUADA, SEVERIDAD_FUENTE, validar_paquete

MENSAJE_EU = "EU: not evaluated (EMA v8.x criteria not implemented)"


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "ectd_validator", *args], capture_output=True, text=True, timeout=300)


@pytest.fixture()
def pkg(tmp_path):
    return F.construir(tmp_path / "pkg")


def test_el_mensaje_de_eu_es_el_decidido():
    assert REGION_NO_EVALUADA["eu"] == MENSAJE_EU


def test_eu_se_declara_no_evaluada_en_el_informe_y_no_es_valido_a_secas(pkg):
    inf = validar_paquete(pkg, regiones=("eu",))
    assert inf["regiones_no_evaluadas"] == [{"region": "eu", "motivo": MENSAJE_EU}]
    av = [h for h in inf["hallazgos"] if h["regla"] == "ECTD-CORE-005"]
    assert len(av) == 1 and av[0]["severidad"] == "aviso" and av[0]["mensaje"] == MENSAJE_EU
    assert inf["estado"] == "VALIDO_CON_AVISOS"                       # un paquete sin errores pero con una region pedida y no evaluada no es VALIDO


def test_eu_no_se_comporta_como_us(pkg):
    """VISTO FALLAR con la mutacion "eu se trata como us": las reglas us NO se ejecutan para eu y siguen en `reglas_no_ejecutadas`."""
    us = validar_paquete(pkg, regiones=("us",))
    eu = validar_paquete(pkg, regiones=("eu",))
    reglas_us = {r["id"] for r in engine.cargar_reglas() if r["region"] == "us"}
    corren_con_us = reglas_us & set(us["reglas_ejecutadas"])             # algunas reglas us no aplican a este paquete de ejemplo: se comparan las que SI corren
    assert corren_con_us, "con us tiene que correr alguna regla us"
    assert not (reglas_us & set(eu["reglas_ejecutadas"]))                 # con eu NO corre ninguna regla us
    assert {r["regla"] for r in eu["reglas_no_ejecutadas"]} >= corren_con_us   # y las que corrian con us constan como no ejecutadas
    assert eu["regiones_no_evaluadas"] and not us["regiones_no_evaluadas"]


def test_us_no_declara_ninguna_region_sin_evaluar(pkg):
    inf = validar_paquete(pkg, regiones=("us",))
    assert inf["regiones_no_evaluadas"] == [] and not [h for h in inf["hallazgos"] if h["regla"] == "ECTD-CORE-005"]


def test_una_region_desconocida_tambien_se_declara_y_el_nombre_se_normaliza(pkg):
    inf = validar_paquete(pkg, regiones=("JP", " Eu "))
    assert {x["region"] for x in inf["regiones_no_evaluadas"]} == {"jp", "eu"}
    assert any(x["motivo"] == "JP: not evaluated (no rules for this region)" for x in inf["regiones_no_evaluadas"])
    assert any(x["motivo"] == MENSAJE_EU for x in inf["regiones_no_evaluadas"])


def test_la_severidad_fda_consta_como_tal_en_el_informe(pkg):
    inf = validar_paquete(pkg, regiones=("us",))
    assert inf["severidad_fuente"] == SEVERIDAD_FUENTE
    assert "FDA" in SEVERIDAD_FUENTE and "NOT the EMA severity" in SEVERIDAD_FUENTE


def test_la_cli_con_region_eu_lo_dice_en_la_salida_y_en_el_json(pkg, tmp_path):
    r = _cli(str(pkg), "--region", "eu", "--informe-dir", str(tmp_path / "out"))
    assert r.returncode == 0, r.stderr                                    # VALIDO_CON_AVISOS no es fallo, pero se ve
    assert "AVISO: " + MENSAJE_EU in r.stderr
    d = json.loads(r.stdout)
    assert d["regiones_no_evaluadas"][0]["motivo"] == MENSAJE_EU and d["estado"] == "VALIDO_CON_AVISOS"
    html = (tmp_path / "out" / "informe_ectd.html").read_text(encoding="utf-8")
    assert MENSAJE_EU in html and "NOT the EMA severity" in html          # tambien en el informe HTML


def test_el_pdf_del_informe_lleva_la_region_no_evaluada_y_la_fuente(pkg, tmp_path):
    r = _cli(str(pkg), "--region", "eu", "--informe-dir", str(tmp_path / "out"))
    assert r.returncode == 0, r.stderr
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    texto = " ".join(" ".join(p.get_text() for p in fitz.open(str(tmp_path / "out" / "informe_ectd.pdf"))).split())      # el PDF parte las frases en varias lineas
    assert "Regiones no evaluadas" in texto and "not evaluated" in texto and "EMA v8.x" in texto and "NOT the EMA severity" in texto


def test_un_informe_antiguo_sin_las_claves_nuevas_sigue_generando_informes(pkg, tmp_path):
    """--informe-desde con un JSON anterior a este cambio (sin regiones_no_evaluadas ni severidad_fuente) no se rompe."""
    inf = validar_paquete(pkg)
    inf.pop("regiones_no_evaluadas"), inf.pop("severidad_fuente")
    (tmp_path / "v.json").write_text(json.dumps(inf), encoding="utf-8")
    r = _cli("--informe-desde", str(tmp_path / "v.json"), "--informe-dir", str(tmp_path / "out"))
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "out" / "informe_ectd.html").is_file() and (tmp_path / "out" / "informe_ectd.pdf").is_file()
