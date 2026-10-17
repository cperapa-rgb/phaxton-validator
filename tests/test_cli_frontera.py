"""La CLI es la FRONTERA: un consumidor (phoenixreplica) la usa por subproceso, sin importar el paquete.

Cada prueba corre `python -m ectd_validator` como proceso aparte, que es lo que hace el consumidor.
"""
import json
import subprocess
import sys

import ectd_fixtures as F
from ectd_validator import AVISO_PREPARATORIO, VERSION


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "ectd_validator", *args], capture_output=True, text=True, timeout=300)


def test_version():
    r = _cli("--version")
    assert r.returncode == 0 and r.stdout.strip() == "phaxton-validator " + VERSION


def test_info_trae_los_datos_de_frontera():
    r = _cli("--info")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["version"] == VERSION and d["aviso_preparatorio"] == AVISO_PREPARATORIO
    assert set(d["carpetas"]) and set(d["stf_tags"])
    assert d["dtd_ectd_en_paquete"].endswith("ich-ectd-3-2.dtd") and d["dtd_stf_en_paquete"].endswith("ich-stf-v2-2.dtd")
    from pathlib import Path
    assert Path(d["dtd_ectd"]).is_file() and Path(d["dtd_stf"]).is_file()


def test_informe_dir_escribe_los_tres_informes_desde_la_validacion(tmp_path):
    pkg = F.roto(tmp_path / "pkg", "CHK-001")
    r = _cli(str(pkg), "--informe-dir", str(tmp_path / "out"))
    assert r.returncode == 1, r.stderr                       # CON_ERRORES: el JSON sigue saliendo
    assert json.loads(r.stdout)["estado"] == "CON_ERRORES"
    for ext in ("json", "html", "pdf"):
        assert (tmp_path / "out" / ("informe_ectd." + ext)).is_file()


def test_informe_desde_json_no_valida_y_escribe(tmp_path):
    pkg = F.roto(tmp_path / "pkg", "CHK-001")
    r = _cli(str(pkg), "--json", str(tmp_path / "v.json"))
    assert r.returncode == 1
    r2 = _cli("--informe-desde", str(tmp_path / "v.json"), "--informe-dir", str(tmp_path / "out2"))
    assert r2.returncode == 0, r2.stderr
    assert json.loads(r2.stdout)["pdf"].endswith("informe_ectd.pdf")


def test_informe_desde_sin_informe_dir_falla():
    r = _cli("--informe-desde", "x.json")
    assert r.returncode == 2 and "exige --informe-dir" in r.stderr


def test_sin_paquete_ni_modo_falla_explicito():
    r = _cli()
    assert r.returncode == 2 and "falta la carpeta" in r.stderr


def test_info_trae_la_huella_del_codigo_y_es_estable_y_cambia_con_el_codigo(tmp_path, monkeypatch):
    a = json.loads(_cli("--info").stdout)["huella_codigo"]
    b = json.loads(_cli("--info").stdout)["huella_codigo"]
    assert a == b and len(a) == 64                           # estable entre procesos
    from ectd_validator import __main__ as M
    from pathlib import Path
    # visto fallar: un fichero nuevo en el paquete cambia la huella aunque la version no suba
    extra = Path(M.__file__).parent / "_huella_prueba.txt"
    try:
        extra.write_text("x", encoding="utf-8")
        assert M.huella_codigo() != a
    finally:
        extra.unlink()
    assert M.huella_codigo() == a
