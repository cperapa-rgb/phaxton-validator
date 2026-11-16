"""T3 (deuda 'las DTD de ICH incluidas son las originales, no verificado'): los ficheros de ICH versionados en ectd_validator/spec son los publicados por ICH.

Tres capas, de la mas debil a la mas fuerte:
1. (siempre) huellas SHA-256 y MD5 fijadas aqui y registradas en spec/PROCEDENCIA.md; cualquier cambio de un byte las rompe.
2. (siempre) las copias de los fixtures coinciden byte a byte con las de spec.
3. (opt-in, VALIDADOR_VERIFICAR_ICH=1) descarga de las URLs de ICH y comparacion byte a byte. Con la variable puesta y SIN red la prueba FALLA: un verde por ausencia esta prohibido.
   Sin la variable se OMITE y dice por que (las pruebas del validador no deben depender de internet).

Que prueba y que no: la capa 3 prueba que el fichero versionado es el que ICH sirve HOY en esa URL. Que el MD5 publicado coincida es la comparacion con una huella que ICH y las agencias publican
(spec/PROCEDENCIA.md, seccion Verificacion), no con una segunda copia del fichero. El MD5 del STF DTD no tiene huella publicada localizada: solo la capa 3 lo cubre.
"""
import hashlib
import io
import os
import urllib.request
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SPEC = RAIZ / "ectd_validator" / "spec"
FIXTURE_DTD = RAIZ / "tests" / "fixtures" / "sample_package" / "util" / "dtd"
BASE = "https://admin.ich.org/sites/default/files/inline-files/"

# nombre -> (sha256, md5, url, nombre dentro del zip o None). sha256/md5 de los bytes tal cual los publica ICH (el .xsl no lleva CRLF; las DTD si, y `*.dtd -text` los conserva).
ICH = {
    "ich-ectd-3-2.dtd": ("c094aa2bded99564ade8ac78ae1540f95e518461b8eebe9a3063f67a165c2731", "1d6f631cc6b6357f0f4fe378e5f79a27",
                         BASE + "ich-ectd-3-2_dtd_0.zip", "ich-ectd-3-2.dtd"),
    "ich-stf-v2-2.dtd": ("e6d47695501e263534a89a2b7bf7018c92e12a11c3dd82fc1d0c462bfa52c81f", "0972c10a4dadf3df5d2f41b2026a4a5c",
                         BASE + "ich-stf-v2-2_dtd_0.zip", "ich-stf-v2-2.dtd"),
    "ectd-2-0.xsl": ("41bf6aaf78fa1ba736951174c5e3dc6724410f4d5d9332034dac9b2c8d34dcd1", "3a07a202455e954a2eb203c5bb443f77",
                     BASE + "ectd-2-0_0.xsl", None),
}


def _bytes(p: Path) -> bytes:
    """Los bytes del fichero; el .xsl se normaliza a LF porque un checkout de Windows sin `-text` lo convierte a CRLF (la regla BBN-007 hace lo mismo)."""
    datos = p.read_bytes()
    return datos.replace(bytes([13, 10]), bytes([10])) if p.suffix == ".xsl" else datos


def coinciden(a: bytes, b: bytes) -> bool:
    return hashlib.sha256(a).digest() == hashlib.sha256(b).digest() and len(a) == len(b)


@pytest.mark.parametrize("nombre", sorted(ICH))
def test_las_huellas_de_los_ficheros_de_ich_son_las_fijadas(nombre):
    sha, md5, _, _ = ICH[nombre]
    datos = _bytes(SPEC / nombre)
    assert hashlib.sha256(datos).hexdigest() == sha, nombre
    assert hashlib.md5(datos).hexdigest() == md5, nombre                    # noqa: S324 - MD5 es el que publican ICH y las agencias


def test_la_procedencia_registra_las_mismas_huellas_que_el_test():
    texto = (SPEC / "PROCEDENCIA.md").read_text(encoding="utf-8")
    for nombre, (sha, md5, _, _) in ICH.items():
        assert sha in texto, f"PROCEDENCIA.md no registra el SHA-256 de {nombre}"
        assert md5 in texto, f"PROCEDENCIA.md no registra el MD5 de {nombre}"


def test_las_dtd_de_los_fixtures_son_byte_a_byte_las_de_spec():
    for nombre in ("ich-ectd-3-2.dtd", "ich-stf-v2-2.dtd"):
        assert coinciden((FIXTURE_DTD / nombre).read_bytes(), (SPEC / nombre).read_bytes()), nombre


def test_la_comparacion_se_ve_fallar_con_un_solo_byte_cambiado():
    original = (SPEC / "ich-ectd-3-2.dtd").read_bytes()
    alterado = bytearray(original)
    alterado[len(alterado) // 2] ^= 0x01
    assert coinciden(original, original)
    assert not coinciden(original, bytes(alterado))
    assert not coinciden(original, original[:-1])
    assert hashlib.md5(bytes(alterado)).hexdigest() != ICH["ich-ectd-3-2.dtd"][1]


def _descargar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (verificacion de huella de fichero publico)"})
    return urllib.request.urlopen(req, timeout=60).read()


@pytest.mark.parametrize("nombre", sorted(ICH))
def test_los_ficheros_versionados_son_los_que_ich_publica_ahora(nombre):
    if os.environ.get("VALIDADOR_VERIFICAR_ICH") != "1":
        pytest.skip("comprobacion en linea contra admin.ich.org: ejecutar con VALIDADOR_VERIFICAR_ICH=1 (sin esa variable no se comprueba y se dice)")
    _, _, url, dentro = ICH[nombre]
    try:
        bruto = _descargar(url)
    except Exception as e:  # noqa: BLE001 - con la variable puesta, no poder descargar es un FALLO, no un verde
        pytest.fail(f"no se pudo descargar {url}: {type(e).__name__}: {e}", pytrace=False)
    original = zipfile.ZipFile(io.BytesIO(bruto)).read(dentro) if dentro else bruto
    assert coinciden(original, (SPEC / nombre).read_bytes() if nombre.endswith(".dtd") else _bytes(SPEC / nombre)), f"{nombre} difiere de lo que sirve ICH en {url}"
