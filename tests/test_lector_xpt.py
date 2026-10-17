"""Lector XPT minimo propio del validador (otra familia de codigo que los lectores del productor): se prueba AQUI, con bytes escritos a mano.

Movido desde phoenixreplica (frontera por CLI, 17-oct-2026): estos tests prueban internos del validador."""
import pytest

from ectd_validator.checkers import stf as checker


def test_el_lector_rechaza_lo_que_no_entiende_y_no_devuelve_vacio(tmp_path):
    p = tmp_path / "x.xpt"
    p.write_bytes(b"esto no es un xpt")
    with pytest.raises(ValueError):
        checker.leer_xpt(p)


def _xpt_a_mano(vars_, filas):
    """XPT v5 minimo escrito a mano: vars_ = [(nombre, tipo 1|2, longitud)], filas = [[valor...]] ya en bytes de campo."""
    def rec(txt):
        return txt.ljust(80).encode("latin-1")
    cab = [rec("HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!000000000000000000000000000000"),
           rec("SAS     SAS     SASLIB  9.4     X64_10PR"), rec("16OCT26:00:00:00"),
           rec("HEADER RECORD*******MEMBER  HEADER RECORD!!!!!!!000000000000000001600000000140"),
           rec("HEADER RECORD*******DSCRPTR HEADER RECORD!!!!!!!000000000000000000000000000000"),
           rec("SAS     TS      SASDATA 9.4     X64_10PR"), rec("16OCT26:00:00:00"),
           rec("HEADER RECORD*******NAMESTR HEADER RECORD!!!!!!!000000%04d00000000000000000000" % len(vars_))]
    ns = b""
    pos = 0
    for i, (nombre, tipo, lng) in enumerate(vars_, 1):
        n = bytearray(140)
        n[0:2] = tipo.to_bytes(2, "big")
        n[4:6] = lng.to_bytes(2, "big")
        n[6:8] = i.to_bytes(2, "big")
        n[8:16] = nombre.ljust(8).encode("latin-1")
        n[16:56] = nombre.ljust(40).encode("latin-1")
        n[84:88] = pos.to_bytes(4, "big")
        ns += bytes(n)
        pos += lng
    ns += b" " * ((-len(ns)) % 80)
    obs = rec("HEADER RECORD*******OBS     HEADER RECORD!!!!!!!000000000000000000000000000000")
    cuerpo = b"".join(b"".join(f) for f in filas)
    cuerpo += b" " * ((-len(cuerpo)) % 80)
    return b"".join(cab) + ns + obs + cuerpo


def test_lector_xpt_decodifica_ibm_de_4_bytes_negativos_ceros_faltantes_y_caracteres(tmp_path):
    nulo = b".\x00\x00\x00"                      # faltante SAS de 4 bytes
    filas = [
        [b"ACTSUB  ", bytes.fromhex("41180000")],      # +1.5  (IBM: 0x41 exp, 0x180000 fraccion)
        [b"MENOS   ", bytes.fromhex("C1240000")],      # -2.25
        [b"CERO    ", bytes.fromhex("00000000")],      # 0
        [b"FALTA   ", nulo],                           # faltante
        ["A\u00c9".encode("latin-1").ljust(8, b" "), bytes.fromhex("42640000")],   # acento y 100.0
    ]
    p = tmp_path / "a.xpt"
    p.write_bytes(_xpt_a_mano([("K", 2, 8), ("V", 1, 4)], filas))
    cols, got = checker.leer_xpt(p)
    assert cols == ["K", "V"]
    assert [g["V"] for g in got] == [1.5, -2.25, 0.0, None, 100.0]
    assert [g["K"] for g in got] == ["ACTSUB", "MENOS", "CERO", "FALTA", "A\u00c9"]


def test_ibm_mutado_haria_fallar_el_test_anterior():
    """Mutacion de _ibm demostrada: sin el bit de signo o con el exponente +1 los valores conocidos dejan de coincidir."""
    ok = checker._ibm(bytes.fromhex("C124000000000000"))
    assert ok == -2.25
    sin_signo = (bytes([0xC1 & 0x7F]) + bytes.fromhex("24000000000000"))
    assert checker._ibm(sin_signo) == 2.25 and checker._ibm(sin_signo) != ok
    exp_mas_uno = bytes([0xC2]) + bytes.fromhex("24000000000000")
    assert checker._ibm(exp_mas_uno) != ok
