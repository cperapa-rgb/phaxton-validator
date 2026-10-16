# Procedencia de la DTD

- `ich-ectd-3-2.dtd`: DTD oficial ICH eCTD v3.2 (nov-2003), la que referencia la especificacion v3.2.2.
- Fuente: https://admin.ich.org/sites/default/files/inline-files/ich-ectd-3-2_dtd_0.zip (enlazada desde la pagina de FDA
  "eCTD Submission Standards for eCTD v3.2.2"), descargada el 15-oct-2026. Contenido del zip: ich-ectd-3-2.dtd, index.htm.
- SHA-256 (bytes tal cual, CRLF): c094aa2bded99564ade8ac78ae1540f95e518461b8eebe9a3063f67a165c2731
- SHA-256 normalizado a LF: 9843b1b00055726ed3604b6f224aba52d4c396959e51def1441f8022057f60c9 (el que fija el test).
- La DTD declara `xmlns:xlink` FIXED como `http://www.w3c.org/1999/xlink` (con w3c, no w3.org): es el valor oficial.
- Reglas de nombres (checker `estructura`) tomadas de ICH eCTD Specification v3.2.2 (16-jul-2008, PDF de PMDA,
  https://www.pmda.go.jp/files/000156235.pdf), seccion de nombres: [a-z0-9-], fichero = nombre.nombre, <=64 caracteres
  por nombre, ruta <=230 caracteres.

## Study Tagging File (STF) v2.2 (anadido 15-oct-2026, lote STF v0)
- `ich-stf-v2-2.dtd`: DTD oficial ICH STF v2.2 (comentario interno "version 2-2"), la que cita la ICH eCTD STF Specification v2.6.1.
- Fuente: https://admin.ich.org/sites/default/files/inline-files/ich-stf-v2-2_dtd_0.zip (enlazada desde la pagina de FDA "eCTD Submission
  Standards for eCTD v3.2.2 and Regional M1", entrada "ICH-STF DTD"), descargada el 15-oct-2026. Contenido del zip: ich-stf-v2-2.dtd.
- SHA-256 del zip: dfc41602d8f398a8eb37dca7c5693cb243460f5efdd151f78e58b542bea4da06
- SHA-256 de ich-stf-v2-2.dtd (bytes tal cual, 5024 B): e6d47695501e263534a89a2b7bf7018c92e12a11c3dd82fc1d0c462bfa52c81f;
  normalizado a LF: c9036b11ca6a50df707887fb113c5278a0ef29af86d8e9ed216e818bc0ede506 (el que fija el test).
- Especificacion: "ICH eCTD STF Specification V 2.6.1", 3-jun-2008, https://www.fda.gov/media/159383/download?attachment (PDF de 22 paginas,
  SHA-256 de la descarga del 15-oct-2026: 63132c3751682193f6f13db125ee03583b740680851c0f0e6412561438b482da). Nombre del fichero (`stf-<study-id>.xml`), ubicacion
  (carpeta del estudio), DTD en util/dtd, hoja `version="STF version 2.2"` en la hoja del STF y `xlink:href="<ruta>/index.xml#<ID de hoja>"`:
  paginas 4-5, 11 y 14-15 de esa especificacion.
- `stf_file_tags.json`: valores validos de `file-tag name`/`info-type`. 48 de la tabla de la spec 2.6.1 (p. 8-10); 2 anadidos por la FDA
  Study Data Technical Conformance Guide (oct. 2026, https://www.fda.gov/media/153632/download, secciones 2.1 y 2.3):
  `study-data-reviewers-guide`, `analysis-data-reviewers-guide`. El `info-type` de estos dos (`us`) es una INFERENCIA declarada.
- No hay `valid-values.xml` ni hoja de estilos del STF en el validador: no se arbitra contra ellos (la tabla de la spec es la fuente).

## Severidad de REF-002 y BBN-003 (16-oct-2026)
- Fuente: FDA "Specifications for eCTD Validation Criteria", version 4.6 (revision 2026-08-17), https://www.fda.gov/media/87056/download,
  descargada el 16-oct-2026 (PDF de 77 paginas; SHA-256 de la descarga e5cc369a03840164ef97371d92504124ba013517f69e54487c7dfe9e5f3c46b6; el PDF NO esta
  versionado: otra descarga puede diferir, la FDA lo revisa). Criterio 1306 en la pagina 14 del PDF y 1119 en la 9. Niveles segun el propio documento: High = el envio se considera NO recibido; Medium =
  puede afectar a la revisabilidad, el envio puede considerarse recibido; Low = tecnico, probablemente recibido.
- REF-002 (fichero sin hoja) = criterio 1306 "No leaf element for file", **High**, efectivo 1-mar-2022 -> `error`.
- BBN-003 (DTD ausente de util) = criterio 1119 "Missing required file" (carpeta util), **Medium**, efectivo 10-mar-2008 -> `aviso`.
  (1130, "required file ... altered", es Low; cubierto por BBN-004, que ya es error por otra razon.)
- Mapeo a nuestros dos niveles: High -> error; Medium y Low -> aviso. Decidido por defecto, REVERSIBLE.
- La EMA NO se comprobo (el criterio EU v8.x no se pudo localizar): la severidad es la de la FDA y se declara asi en la regla.
