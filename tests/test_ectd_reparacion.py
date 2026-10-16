"""V0-4: reparacion SIEMPRE en copia. Original intacto, log por cambio, revalidacion de la copia, y lo no reparable
declarado con instruccion manual (nunca 'reparado' mudo)."""
import json
import subprocess
import sys

import pytest

import ectd_fixtures as F
from ectd_validator import validar_paquete
from ectd_validator.fixes import FixError, manifiesto, reparar

REPARABLES = [
    ("CHK-001", "CHK-001"), ("CHK-002", "CHK-002"), ("CHK-003", "CHK-003"), ("CHK-003-AUSENTE", "CHK-003"),
    ("BBN-002", "BBN-002"), ("BBN-003", "BBN-003"), ("BBN-004", "BBN-004"),
    ("BBN-005-BOM", "BBN-005"), ("BBN-005-INVISIBLE", "BBN-005"), ("BBN-005-LATIN1", "BBN-005"),
    ("PDF-002-PERMISOS", "PDF-002"), ("PDF-003", "PDF-003"),
]


@pytest.mark.parametrize("defecto,regla", REPARABLES)
def test_cada_defecto_reparable_se_repara_en_la_copia_y_el_original_queda_intacto(tmp_path, defecto, regla):
    orig = F.roto(tmp_path / "orig", defecto)
    antes = manifiesto(orig)
    estado_antes = validar_paquete(orig)["estado"]
    assert estado_antes != "VALIDO"
    rep = reparar(orig, tmp_path / "copia")
    assert manifiesto(orig) == antes and rep["original_intacto"] is True      # el original no se toco
    assert rep["estado_original"] == estado_antes
    assert rep["estado_copia"] == "VALIDO", rep["no_reparados"]               # revalidada y limpia
    assert rep["no_reparados"] == []
    assert regla in {c["regla"] for c in rep["cambios"]}
    assert validar_paquete(tmp_path / "copia")["estado"] == "VALIDO"          # revalidacion independiente


@pytest.mark.parametrize("defecto,regla", REPARABLES)
def test_el_log_describe_exactamente_los_ficheros_que_cambiaron(tmp_path, defecto, regla):
    orig = F.roto(tmp_path / "orig", defecto)
    rep = reparar(orig, tmp_path / "copia")
    a, b = manifiesto(orig), manifiesto(tmp_path / "copia")
    cambiados = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert cambiados == {c["fichero"] for c in rep["cambios"]}
    assert all(c["antes"] != c["despues"] for c in rep["cambios"])


@pytest.mark.parametrize("defecto,regla", [
    ("REF-001", "REF-001"), ("REF-002", "REF-002"), ("BBN-001", "BBN-001"), ("STR-001", "STR-001"),
    ("STR-003", "STR-003"), ("PDF-001", "PDF-001"), ("PDF-004", "PDF-004")])
def test_lo_no_reparable_queda_en_el_informe_con_instruccion_y_la_copia_no_finge(tmp_path, defecto, regla):
    orig = F.roto(tmp_path / "orig", defecto)
    rep = reparar(orig, tmp_path / "copia")
    ids = {n["regla"] for n in rep["no_reparados"]}
    assert regla in ids
    assert all(n["instruccion"] and n["motivo"] for n in rep["no_reparados"])
    assert rep["estado_copia"] != "VALIDO"     # no se declara reparado lo que no se reparo
    assert regla in {h["regla"] for h in rep["validacion_copia"]["hallazgos"]}


def test_pdf_con_contrasena_de_usuario_no_se_repara_y_dice_por_que(tmp_path):
    orig = F.roto(tmp_path / "orig", "PDF-002")
    rep = reparar(orig, tmp_path / "copia")
    n = [x for x in rep["no_reparados"] if x["regla"] == "PDF-002"]
    assert n and "contrasena" in n[0]["motivo"]
    assert rep["estado_copia"] == "CON_ERRORES"


def test_version_mayor_que_1_7_no_se_rebaja(tmp_path):
    orig = F.roto(tmp_path / "orig", "PDF-003-ALTA")
    rep = reparar(orig, tmp_path / "copia")
    n = [x for x in rep["no_reparados"] if x["regla"] == "PDF-003"]
    assert n and "1.7" in n[0]["motivo"]


@pytest.mark.parametrize("modo", ["igual", "dentro", "contiene", "no_vacio"])
def test_el_destino_nunca_puede_ser_el_original_ni_estar_ligado_a_el(tmp_path, modo):
    orig = F.construir(tmp_path / "orig")
    destino = {"igual": orig, "dentro": orig / "copia", "contiene": tmp_path, "no_vacio": tmp_path / "x"}[modo]
    if modo == "no_vacio":
        destino.mkdir()
        (destino / "algo.txt").write_text("ya hay cosas", encoding="utf-8")
    antes = manifiesto(orig)
    with pytest.raises(FixError):
        reparar(orig, destino)
    assert manifiesto(orig) == antes


def test_paquete_no_validable_no_se_repara(tmp_path):
    (tmp_path / "orig").mkdir()
    with pytest.raises(FixError, match="no es validable"):
        reparar(tmp_path / "orig", tmp_path / "copia")
    assert not (tmp_path / "copia").exists()


def test_un_paquete_valido_se_copia_sin_cambios(tmp_path):
    orig = F.construir(tmp_path / "orig")
    rep = reparar(orig, tmp_path / "copia")
    assert rep["cambios"] == [] and rep["estado_copia"] == "VALIDO"
    assert manifiesto(orig) == manifiesto(tmp_path / "copia")


def test_el_aviso_preparatorio_va_en_el_informe_de_reparacion(tmp_path):
    rep = reparar(F.roto(tmp_path / "orig", "CHK-001"), tmp_path / "copia")
    assert rep["aviso"] == rep["validacion_original"]["aviso"] and "originals are never modified" in rep["aviso"]


def test_cli_reparar_en(tmp_path):
    orig = F.roto(tmp_path / "orig", "CHK-001")
    antes = manifiesto(orig)
    out = tmp_path / "rep.json"
    r = subprocess.run([sys.executable, "-m", "ectd_validator", str(orig), "--reparar-en", str(tmp_path / "copia"),
                        "--json", str(out)])
    assert r.returncode == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["estado_original"] == "CON_ERRORES" and rep["estado_copia"] == "VALIDO"
    assert manifiesto(orig) == antes
    r2 = subprocess.run([sys.executable, "-m", "ectd_validator", str(orig), "--reparar-en", str(orig)])
    assert r2.returncode == 2


def test_latin1_real_se_reconvierte_a_utf_8_y_conserva_el_texto(tmp_path):
    orig = F.roto(tmp_path / "orig", "BBN-005-LATIN1")
    rep = reparar(orig, tmp_path / "copia")
    texto = (tmp_path / "copia" / "index.xml").read_bytes().decode("utf-8")  # estricto: ya es UTF-8
    assert "informe " + chr(0xE9) + "tico" in texto and "ISO-8859-1" not in texto
    assert rep["estado_copia"] == "VALIDO"


def test_zwj_no_se_elimina_queda_pendiente_manual(tmp_path):
    orig = F.roto(tmp_path / "orig", "BBN-005-ZWJ")
    rep = reparar(orig, tmp_path / "copia")
    assert chr(0x200D) in (tmp_path / "copia" / "index.xml").read_text(encoding="utf-8")
    n = [x for x in rep["no_reparados"] if x["regla"] == "BBN-005"]
    assert n and "U+200C/U+200D" in n[0]["instruccion"]
    assert rep["cambios"] == [] and rep["estado_copia"] == "VALIDO_CON_AVISOS"


def test_el_log_de_invisibles_dice_donde(tmp_path):
    orig = F.roto(tmp_path / "orig", "BBN-005-INVISIBLE")
    rep = reparar(orig, tmp_path / "copia")
    antes = [c["antes"] for c in rep["cambios"] if c["regla"] == "BBN-005"][0]
    assert "U+200B x1" in antes and "offset" in antes


def test_comillas_simples_es_fixerror_del_arreglo_y_queda_pendiente_no_traceback(tmp_path):
    orig = F.roto(tmp_path / "orig", "COMILLAS-SIMPLES")
    rep = reparar(orig, tmp_path / "copia")
    n = [x for x in rep["no_reparados"] if x["regla"] == "CHK-001"]
    assert n and "comillas simples" in n[0]["motivo"]
    assert rep["estado_copia"] == "CON_ERRORES"


def test_bytes_invalidos_en_index_no_revientan_y_se_declaran(tmp_path):
    orig = F.roto(tmp_path / "orig", "BYTES-INVALIDOS")
    inicial = validar_paquete(orig)
    # un index.xml no UTF-8 puede ser NO_VALIDABLE (mal formado): entonces no se repara y se dice
    if inicial["estado"] == "NO_VALIDABLE":
        with pytest.raises(FixError, match="no es validable"):
            reparar(orig, tmp_path / "copia")
        assert not (tmp_path / "copia").exists()
    else:
        rep = reparar(orig, tmp_path / "copia")
        assert any(n["regla"] == "BBN-005" for n in rep["no_reparados"])


def test_destino_que_es_un_fichero_es_fixerror_no_traceback(tmp_path):
    orig = F.construir(tmp_path / "orig")
    destino = tmp_path / "soy_un_fichero"
    destino.write_text("x", encoding="utf-8")
    with pytest.raises(FixError, match="no es una carpeta vacia"):
        reparar(orig, destino)


def test_enlace_simbolico_en_el_original_se_rechaza(tmp_path):
    orig = F.construir(tmp_path / "orig")
    (tmp_path / "externo.txt").write_text("secreto", encoding="utf-8")
    try:
        (orig / "m5" / "enlace.txt").symlink_to(tmp_path / "externo.txt")
    except (OSError, NotImplementedError):
        pytest.skip("este equipo no permite crear enlaces simbolicos")
    with pytest.raises(FixError, match="enlace simbolico"):
        reparar(orig, tmp_path / "copia")
    assert not (tmp_path / "copia").exists()


def test_fallo_tras_copiar_borra_la_copia_a_medias_y_el_original_sigue_intacto(tmp_path, monkeypatch):
    import ectd_validator.fixes as fx
    orig = F.roto(tmp_path / "orig", "CHK-001")
    antes = manifiesto(orig)
    llamadas = []
    real = fx.validar_paquete

    def falla_en_la_segunda(p):
        llamadas.append(p)
        if len(llamadas) == 2:   # la revalidacion de la copia
            raise OSError("simulado")
        return real(p)
    monkeypatch.setattr(fx, "validar_paquete", falla_en_la_segunda)
    with pytest.raises(FixError, match="fallo inesperado"):
        reparar(orig, tmp_path / "copia")
    assert not (tmp_path / "copia").exists() and manifiesto(orig) == antes


def test_mutacion_los_arreglos_sobre_el_original_hacen_fallar_el_invariante(tmp_path, monkeypatch):
    import ectd_validator.fixes as fx
    orig = F.roto(tmp_path / "orig", "CHK-001")
    antes = manifiesto(orig)
    monkeypatch.setattr(fx.shutil, "copytree", lambda s, d, **k: None)  # "copia" vacia: los arreglos no tocan nada
    with pytest.raises(FixError):
        reparar(orig, tmp_path / "copia")
    assert manifiesto(orig) == antes


def test_pdf_arreglo_que_no_cumple_la_postcondicion_se_descarta(tmp_path, monkeypatch):
    from ectd_validator.fixes import pdf as fpdf
    import types

    class Falso:
        pdf_version, is_encrypted = "1.3", True
        Root = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def save(self, ruta, **k):
            open(ruta, "wb").write(b"%PDF-1.3 sin cambios")
    real = fpdf.pikepdf
    fake = types.SimpleNamespace(open=lambda p: Falso(), PasswordError=real.PasswordError, PdfError=real.PdfError)
    monkeypatch.setattr(fpdf, "pikepdf", fake)
    orig = F.roto(tmp_path / "orig", "PDF-002-PERMISOS")
    rep = reparar(orig, tmp_path / "copia")
    n = [x for x in rep["no_reparados"] if x["regla"] == "PDF-002"]
    assert n and "postcondicion" in n[0]["motivo"] and rep["estado_copia"] == "CON_ERRORES"


def test_pdf_firmado_no_se_reescribe(tmp_path, monkeypatch):
    from ectd_validator.fixes import pdf as fpdf
    monkeypatch.setattr(fpdf, "_firmado", lambda pdf: True)
    orig = F.roto(tmp_path / "orig", "PDF-003")
    rep = reparar(orig, tmp_path / "copia")
    n = [x for x in rep["no_reparados"] if x["regla"] == "PDF-003"]
    assert n and "firmado" in n[0]["motivo"]


def test_toda_regla_es_automatica_o_tiene_instruccion_manual():
    from ectd_validator.engine import cargar_reglas
    from ectd_validator.fixes import AUTOMATICAS, MANUAL
    ids = {r["id"] for r in cargar_reglas()}
    assert ids <= AUTOMATICAS | set(MANUAL), ids - AUTOMATICAS - set(MANUAL)


def test_la_copia_con_avisos_sin_reparar_devuelve_codigo_1_en_el_cli(tmp_path):
    orig = F.roto(tmp_path / "orig", "PDF-004")
    r = subprocess.run([sys.executable, "-m", "ectd_validator", str(orig), "--reparar-en", str(tmp_path / "copia"),
                        "--json", str(tmp_path / "r.json")])
    assert r.returncode == 1
    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["estado_copia"] == "VALIDO_CON_AVISOS"


def test_cli_destino_fichero_es_rc_2_sin_traceback(tmp_path):
    orig = F.construir(tmp_path / "orig")
    destino = tmp_path / "f.txt"
    destino.write_text("x", encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "ectd_validator", str(orig), "--reparar-en", str(destino)],
                       capture_output=True, text=True)
    assert r.returncode == 2 and "Traceback" not in r.stderr


def test_deteccion_de_enlaces_sin_depender_de_privilegios_del_sistema(tmp_path, monkeypatch):
    import pathlib
    from ectd_validator.fixes import _sin_enlaces
    orig = F.construir(tmp_path / "orig")
    objetivo = orig / "m5"
    real = pathlib.Path.is_symlink
    monkeypatch.setattr(pathlib.Path, "is_symlink", lambda self: True if self == objetivo else real(self))
    with pytest.raises(FixError, match="enlace simbolico"):
        _sin_enlaces(orig)


def test_recalcular_un_md5_que_no_cuadraba_advierte_que_no_prueba_el_contenido(tmp_path):
    # dogfooding: un xpt corrupto tras el build quedaba 'VALIDO' en la copia sin mas aviso que el log
    rep = reparar(F.roto(tmp_path / "orig", "CHK-001"), tmp_path / "copia")
    assert rep["estado_copia"] == "VALIDO"
    assert len(rep["advertencias"]) == 1 and "NO demuestra" in rep["advertencias"][0]
    assert rep["cambios"][0]["objeto"].replace("hoja ", "") in rep["advertencias"][0]


def test_un_checksum_ausente_no_dispara_la_advertencia_de_contenido(tmp_path):
    rep = reparar(F.roto(tmp_path / "orig", "CHK-002"), tmp_path / "copia")
    assert rep["advertencias"] == []          # CHK-002 = no habia checksum, no hay contenido alterado que ocultar


def test_la_advertencia_cuenta_solo_los_chk_001_y_todas_las_hojas(tmp_path):
    # dos hojas con MD5 que no cuadra: la advertencia las cuenta y las lista a las dos
    orig = F.roto(tmp_path / "orig", "CHK-001")
    (orig / F.XPT).write_bytes((orig / F.XPT).read_bytes() + b" alterado")
    rep = reparar(orig, tmp_path / "copia")
    chk1 = [c for c in rep["cambios"] if c["regla"] == "CHK-001"]
    assert len(chk1) == 2                      # el PDF y el XPT
    assert len(rep["advertencias"]) == 1
    assert "%d hoja(s)" % len(chk1) in rep["advertencias"][0]
    for c in chk1:
        assert c["objeto"].replace("hoja ", "") in rep["advertencias"][0]


def test_el_cli_imprime_la_advertencia_en_stderr(tmp_path, capsys):
    from ectd_validator.__main__ import main
    main([str(F.roto(tmp_path / "orig", "CHK-001")), "--reparar-en", str(tmp_path / "copia")])
    assert "ADVERTENCIA" in capsys.readouterr().err
