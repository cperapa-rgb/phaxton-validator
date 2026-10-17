import argparse
import json
import sys

from .engine import validar_paquete, carpetas, VERSION, AVISO_PREPARATORIO

_SALIDA = {"VALIDO": 0, "VALIDO_CON_AVISOS": 0, "CON_ERRORES": 1, "NO_VALIDABLE": 2}


def _info() -> dict:
    """Todo lo que un consumidor (p. ej. el escritor de backbones) necesita del validador SIN importarlo: datos, no codigo."""
    from pathlib import Path
    from .checkers import backbone, stf
    spec = Path(backbone.DTD_OFICIAL).parent
    return {"version": VERSION, "aviso_preparatorio": AVISO_PREPARATORIO, "spec_dir": str(spec),
            "dtd_ectd": str(backbone.DTD_OFICIAL), "dtd_ectd_en_paquete": backbone.DTD_EN_PAQUETE,
            "dtd_stf": str(stf.DTD_STF), "dtd_stf_en_paquete": stf.DTD_STF_EN_PAQUETE, "version_hoja_stf": stf.VERSION_HOJA,
            "carpetas": carpetas(), "stf_tags": stf.tags_validos()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ectd_validator", description="Validador tecnico eCTD 3.2.2 (v0)")
    ap.add_argument("paquete", nargs="?", help="carpeta de la secuencia (la que contiene index.xml)")
    ap.add_argument("--version", action="store_true", help="imprime la version y sale")
    ap.add_argument("--info", action="store_true",
                    help="imprime en JSON la frontera para quien consuma el validador: version, aviso preparatorio, rutas y tablas de la spec")
    ap.add_argument("--informe-dir", help="ademas escribe informe_ectd.json/.html/.pdf en esta carpeta")
    ap.add_argument("--informe-desde", help="no valida: escribe los informes (con --informe-dir) desde este JSON de validacion ya hecho")
    ap.add_argument("--json", help="escribe el informe JSON en esta ruta")
    ap.add_argument("--region", action="append", default=[],
                    help="pide las reglas de una region concreta (p. ej. us); repetible. Sin pedirlas se declaran no ejecutadas")
    ap.add_argument("--reparar-en", help="repara una COPIA en esta carpeta (nueva o vacia); el original no se toca")
    a = ap.parse_args(argv)
    if a.version:
        print("phaxton-validator " + VERSION)
        return 0
    if a.info:
        print(json.dumps(_info(), indent=2, ensure_ascii=False))
        return 0
    if a.informe_desde:
        if not a.informe_dir:
            print("ERROR: --informe-desde exige --informe-dir", file=sys.stderr)
            return 2
        from .report import escribir_informes
        with open(a.informe_desde, encoding="utf-8") as f:
            informe = json.load(f)
        rutas = escribir_informes(informe, a.informe_dir)
        print(json.dumps({k: str(v) for k, v in rutas.items()}, indent=2, ensure_ascii=False))
        return 0
    if not a.paquete:
        print("ERROR: falta la carpeta del paquete", file=sys.stderr)
        return 2
    if a.reparar_en:
        from .fixes import FixError, reparar
        try:
            rep = reparar(a.paquete, a.reparar_en)
        except (FixError, OSError) as e:
            print("ERROR: " + str(e), file=sys.stderr)
            return 2
        for adv in rep.get("advertencias", []):
            print("ADVERTENCIA: " + adv, file=sys.stderr)
        texto = json.dumps(rep, indent=2, ensure_ascii=False)
        if a.json:
            with open(a.json, "w", encoding="utf-8", newline="") as f:
                f.write(texto)
        else:
            print(texto)
        # 1 si algo quedo sin reparar, aunque la copia solo tenga avisos
        return max(_SALIDA[rep["estado_copia"]], 1 if rep["no_reparados"] else 0)
    informe = validar_paquete(a.paquete, regiones=a.region)
    no_pedidas = [r["regla"] for r in informe["reglas_no_ejecutadas"] if "no solicitada" in r["motivo"]]
    if no_pedidas:
        print("AVISO: reglas regionales NO solicitadas (no se ejecutaron): %s; use --region us para pedirlas"
              % ", ".join(no_pedidas), file=sys.stderr)
    if a.informe_dir:
        from .report import escribir_informes
        escribir_informes(informe, a.informe_dir)
    texto = json.dumps(informe, indent=2, ensure_ascii=False)
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
    else:
        print(texto)
    return _SALIDA[informe["estado"]]


if __name__ == "__main__":
    sys.exit(main())
