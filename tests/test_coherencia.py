"""COH-001..005: coherencia SDTM <-> ADaM. Cada regla se ve FALLAR sobre un paquete con UN defecto sembrado, y la linea base
(con ADaM y SDTM coherentes) las ejecuta TODAS y no dice nada. Los XPT se escriben a mano (IBM float propio de este test), no con
el lector que los cruza."""
import copy
import pytest

import ectd_fixtures as F
from ectd_validator import validar_paquete
from test_lector_xpt import _xpt_a_mano

COH = {"COH-%03d" % i for i in range(1, 6)}


def _ibm(x):
    if x is None:
        return b"." + bytes(7)
    if x == 0:
        return bytes(8)
    signo = 0x80 if x < 0 else 0
    m = abs(float(x))
    e = 0
    while m >= 1:
        m /= 16.0
        e += 1
    while m < 1 / 16.0:
        m *= 16.0
        e -= 1
    frac = int(round(m * (1 << 56)))
    return bytes([signo | (e + 64)]) + frac.to_bytes(7, "big")


def _c(v, n):
    return str(v).encode("latin-1").ljust(n, b" ")


# dataset -> (variables, filas). C = caracter de 12, N = numerico de 8.
def _base():
    return {
        "dm": ([("STUDYID", "C"), ("USUBJID", "C")], [["S1", "S1-01"], ["S1", "S1-02"]]),
        "pc": ([("STUDYID", "C"), ("USUBJID", "C"), ("PCSEQ", "N"), ("PCSTRESN", "N")],
               [["S1", "S1-01", 1, 5.5], ["S1", "S1-01", 2, 3.25], ["S1", "S1-02", 1, 7.0]]),
        "ex": ([("STUDYID", "C"), ("USUBJID", "C"), ("EXSEQ", "N"), ("EXDOSE", "N")],
               [["S1", "S1-01", 1, 100.0], ["S1", "S1-02", 1, 100.0]]),
        "pp": ([("STUDYID", "C"), ("USUBJID", "C"), ("PPSEQ", "N"), ("PPTESTCD", "C"), ("PPSTRESN", "N")],
               [["S1", "S1-01", 1, "CMAX", 5.5], ["S1", "S1-02", 1, "CMAX", 7.0]]),
        "adnca": ([("STUDYID", "C"), ("USUBJID", "C"), ("AVAL", "N"), ("SRCDOM", "C"), ("SRCSEQ", "N")],
                  [["S1", "S1-01", 100.0, "EX", 1], ["S1", "S1-01", 5.5, "PC", 1], ["S1", "S1-01", 3.25, "PC", 2],
                   ["S1", "S1-02", 100.0, "EX", 1], ["S1", "S1-02", 7.0, "PC", 1]]),
        "adpp": ([("STUDYID", "C"), ("USUBJID", "C"), ("PARAMCD", "C"), ("AVAL", "N"), ("SRCDOM", "C"), ("SRCSEQ", "N")],
                 [["S1", "S1-01", "CMAX", 5.5, "PP", 1], ["S1", "S1-02", "CMAX", 7.0, "PP", 1]]),
    }


def _bytes(variables, filas):
    spec = [(n, 2 if t == "C" else 1, 12 if t == "C" else 8) for n, t in variables]
    cuerpo = []
    for fila in filas:
        cuerpo.append([_c(v, 12) if t == "C" else _ibm(v) for (n, t), v in zip(variables, fila)])
    return _xpt_a_mano(spec, cuerpo)


def _ruta(k, layout):
    if layout == "fda":      # layout real de la FDA: SDTM y ADaM en carpetas hermanas del mismo estudio
        sub = "analysis/adam/datasets/" if k.startswith("ad") else "tabulations/sdtm/"
        return F.BASE + sub + "%s.xpt" % k
    return F.BASE + "%s.xpt" % k


def _paquete(tmp_path, datos, quitar=(), layout="plano"):
    ficheros = {_ruta(k, layout): _bytes(*v) for k, v in datos.items() if k not in quitar}
    viejo = F.FICHEROS
    F.FICHEROS = ficheros
    try:
        return F.construir(tmp_path / "0000")
    finally:
        F.FICHEROS = viejo


def _inf(tmp_path, mutar=None, quitar=()):
    datos = _base()
    if mutar:
        mutar(datos)
    return validar_paquete(_paquete(tmp_path, datos, quitar))


def _coh(inf):
    return {h["regla"] for h in inf["hallazgos"] if h["regla"] in COH}


def test_la_linea_base_ejecuta_las_cinco_reglas_y_no_dice_nada(tmp_path):
    inf = _inf(tmp_path)
    assert COH <= set(inf["reglas_ejecutadas"]), inf["reglas_no_ejecutadas"]
    assert _coh(inf) == set(), inf["hallazgos"]


def test_con_el_layout_de_la_fda_sdtm_y_adam_en_carpetas_hermanas_las_reglas_se_ejecutan_y_ven_el_defecto(tmp_path):
    datos = _base()
    inf = validar_paquete(_paquete(tmp_path / "a", datos, layout="fda"))
    assert COH <= set(inf["reglas_ejecutadas"]) and _coh(inf) == set(), inf["reglas_no_ejecutadas"]
    datos["adpp"][1][0][3] = 5.0
    inf = validar_paquete(_paquete(tmp_path / "b", datos, layout="fda"))
    assert _coh(inf) == {"COH-005"}


def test_sin_adam_las_cinco_reglas_se_declaran_no_ejecutadas_nunca_verde(tmp_path):
    inf = _inf(tmp_path, quitar=("adnca", "adpp"))
    assert not COH & set(inf["reglas_ejecutadas"])
    assert COH <= {r["regla"] for r in inf["reglas_no_ejecutadas"]}


def test_coh_001_un_usubjid_del_adam_que_no_esta_en_dm(tmp_path):
    def m(d):
        d["adnca"][1][3][1] = "S1-99"
    inf = _inf(tmp_path, m)
    assert "COH-001" in _coh(inf)
    assert any("S1-99" in h["mensaje"] for h in inf["hallazgos"] if h["regla"] == "COH-001")


def test_coh_002_dos_studyid_en_el_mismo_estudio(tmp_path):
    def m(d):
        for f in d["adpp"][1]:
            f[0] = "OTRO"
    inf = _inf(tmp_path, m)
    assert "COH-002" in _coh(inf)


def test_coh_003_el_aval_de_adnca_no_es_el_pcstresn(tmp_path):
    def m(d):
        d["adnca"][1][1][2] = 5.6                       # PC dice 5.5
    inf = _inf(tmp_path, m)
    assert _coh(inf) == {"COH-003"}, inf["hallazgos"]


def test_coh_003_un_srcseq_que_no_existe_en_pc(tmp_path):
    def m(d):
        d["adnca"][1][2][4] = 9
    inf = _inf(tmp_path, m)
    assert _coh(inf) == {"COH-003"}, inf["hallazgos"]


def test_coh_004_el_aval_de_la_dosis_no_es_el_exdose(tmp_path):
    def m(d):
        d["adnca"][1][0][2] = 50.0                      # EX dice 100
    inf = _inf(tmp_path, m)
    assert _coh(inf) == {"COH-004"}, inf["hallazgos"]


def test_coh_005_el_aval_de_adpp_no_es_el_ppstresn(tmp_path):
    def m(d):
        d["adpp"][1][0][3] = 5.0
    inf = _inf(tmp_path, m)
    assert _coh(inf) == {"COH-005"}, inf["hallazgos"]


def test_coh_005_el_paramcd_no_es_el_pptestcd(tmp_path):
    def m(d):
        d["adpp"][1][1][2] = "AUCLST"
    inf = _inf(tmp_path, m)
    assert _coh(inf) == {"COH-005"}
    assert any("PARAMCD" in h["mensaje"] for h in inf["hallazgos"])


def test_un_faltante_en_los_dos_lados_es_coherente_y_en_uno_solo_no(tmp_path):
    def ambos(d):
        d["pc"][1][0][3] = None
        d["adnca"][1][1][2] = None
    assert _coh(_inf(tmp_path / "a", ambos)) == set()

    def uno(d):
        d["pc"][1][0][3] = None
    assert _coh(_inf(tmp_path / "b", uno)) == {"COH-003"}


def test_un_adam_ilegible_es_un_hallazgo_no_un_silencio(tmp_path):
    d = _paquete(tmp_path, _base())
    (d / (F.BASE + "adpp.xpt")).write_bytes(b"esto no es un xpt")
    inf = validar_paquete(d)
    assert any(h["regla"] in COH and "no se puede leer" in h["mensaje"] for h in inf["hallazgos"]), inf["hallazgos"]


def test_un_fallo_sistematico_no_inunda_el_informe(tmp_path):
    def m(d):
        d["pc"] = (d["pc"][0], [["S1", "S1-01", i, float(i)] for i in range(1, 60)])
        d["adnca"] = (d["adnca"][0], [["S1", "S1-01", float(i) + 1, "PC", i] for i in range(1, 60)])
    inf = _inf(tmp_path, m)
    n = [h for h in inf["hallazgos"] if h["regla"] == "COH-003"]
    assert 0 < len(n) <= 21 and "mas de la misma regla" in n[-1]["mensaje"]
