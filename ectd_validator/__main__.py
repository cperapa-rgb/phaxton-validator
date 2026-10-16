import argparse
import json
import sys

from .engine import validar_paquete

_SALIDA = {"VALIDO": 0, "VALIDO_CON_AVISOS": 0, "CON_ERRORES": 1, "NO_VALIDABLE": 2}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ectd_validator", description="Validador tecnico eCTD 3.2.2 (v0)")
    ap.add_argument("paquete", help="carpeta de la secuencia (la que contiene index.xml)")
    ap.add_argument("--json", help="escribe el informe JSON en esta ruta")
    ap.add_argument("--region", action="append", default=[],
                    help="pide las reglas de una region concreta (p. ej. us); repetible. Sin pedirlas se declaran no ejecutadas")
    ap.add_argument("--reparar-en", help="repara una COPIA en esta carpeta (nueva o vacia); el original no se toca")
    a = ap.parse_args(argv)
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
    texto = json.dumps(informe, indent=2, ensure_ascii=False)
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            f.write(texto)
    else:
        print(texto)
    return _SALIDA[informe["estado"]]


if __name__ == "__main__":
    sys.exit(main())
