"""Datos de la spec STF versionados en el validador: DTD fijada por checksum y procedencia.

Movido desde phoenixreplica (frontera por CLI, 17-oct-2026): prueban la fuente que el validador lleva."""
import hashlib
from pathlib import Path

import ectd_validator

SPEC = Path(ectd_validator.__file__).parent / "spec"
# fijados el 15-oct-2026 (ver spec/PROCEDENCIA.md); si cambian, alguien toco la fuente oficial
DTD_SHA_BYTES = "e6d47695501e263534a89a2b7bf7018c92e12a11c3dd82fc1d0c462bfa52c81f"
DTD_SHA_LF = "c9036b11ca6a50df707887fb113c5278a0ef29af86d8e9ed216e818bc0ede506"


def test_la_dtd_oficial_del_stf_esta_fijada_por_checksum():
    b = (SPEC / "ich-stf-v2-2.dtd").read_bytes()
    assert hashlib.sha256(b).hexdigest() == DTD_SHA_BYTES
    assert hashlib.sha256(b.replace(bytes([13, 10]), bytes([10]))).hexdigest() == DTD_SHA_LF
    assert b"<!ELEMENT ectd:study (study-identifier, study-document)>" in b


def test_la_procedencia_cita_fuente_y_checksum():
    texto = (SPEC / "PROCEDENCIA.md").read_text(encoding="utf-8")
    for s in ("ich-stf-v2-2_dtd_0.zip", DTD_SHA_BYTES, DTD_SHA_LF, "STF Specification V 2.6.1", "153632",
              "63132c3751682193f6f13db125ee03583b740680851c0f0e6412561438b482da", "INFERENCIA"):
        assert s in texto, s
