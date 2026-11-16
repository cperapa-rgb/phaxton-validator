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

## Hoja de estilo ICH ectd-2-0.xsl (anadida 15-nov-2026, lote Y1)
- `ectd-2-0.xsl`: hoja de estilo oficial ICH eCTD (comentario interno "util/ectd-2-0.xsl, version 2.0, Yokohama, November 17, 2004").
- Fuente: https://admin.ich.org/sites/default/files/inline-files/ectd-2-0_0.xsl (enlazada desde la pagina de FDA "eCTD Submission
  Standards for eCTD v3.2.2 and Regional M1"), descargada el 15-nov-2026.
- SHA-256 (bytes tal cual, 2049 B, sin CRLF): 41bf6aaf78fa1ba736951174c5e3dc6724410f4d5d9332034dac9b2c8d34dcd1. MD5: 3a07a202455e954a2eb203c5bb443f77.
- (15-nov) Que sea la version publicada por ICH no estaba verificado contra un checksum publicado. Actualizado el 16-nov-2026: ver la seccion «Verificacion contra ICH» al final. BBN-007 sigue comparando con este fichero versionado (normalizado a LF), no con un valor publicado.
- Ubicacion en el paquete y referencia: ICH eCTD Specification v3.2.2 (16-jul-2008, PDF de PMDA): util/style/ectd-n.xsl "should be included"
  (apendice de estructura de directorios, elementos 377-378) y la instruccion xml-stylesheet en las primeras lineas de index.xml
  (ejemplos con href="util/style/ectd-2-1-x.xsl"; aqui se usa el nombre del fichero oficial, ectd-2-0.xsl).
- La hoja referencia `util/style/screen.css`; ese fichero NO se incluye (no se ha localizado una fuente oficial): la hoja se ve sin estilos de pantalla.

## Verificacion contra ICH (16-nov-2026, lote T3; test: tests/test_spec_ich_original.py)
Se volvieron a descargar los tres ficheros de las MISMAS URLs de ICH de arriba y se compararon byte a byte con los versionados (blob de git), con las copias de `tests/fixtures/` y con las del zip de ejemplo publicado (SHA-256 4f3cee3d):
- `ich-ectd-3-2.dtd`: IGUAL byte a byte (31400 B). SHA-256 c094aa2bded99564ade8ac78ae1540f95e518461b8eebe9a3063f67a165c2731. MD5 1d6f631cc6b6357f0f4fe378e5f79a27 (zip de ICH: SHA-256 e8676fc1229842ac5565b77f5309183a3957fae55c2c7256620ecae46cbe27bb, contiene ich-ectd-3-2.dtd e index.htm).
- `ich-stf-v2-2.dtd`: IGUAL byte a byte (5024 B). SHA-256 e6d47695501e263534a89a2b7bf7018c92e12a11c3dd82fc1d0c462bfa52c81f. MD5 0972c10a4dadf3df5d2f41b2026a4a5c (zip: SHA-256 dfc41602d8f398a8eb37dca7c5693cb243460f5efdd151f78e58b542bea4da06, el mismo del 15-oct).
- `ectd-2-0.xsl`: IGUAL byte a byte (2049 B) en el blob de git; en un checkout de Windows la copia de trabajo lleva CRLF (2114 B) porque `.gitattributes` no tenia `*.xsl -text` (anadido); la regla BBN-007 y el test normalizan a LF. SHA-256 41bf6aaf78fa1ba736951174c5e3dc6724410f4d5d9332034dac9b2c8d34dcd1. MD5 3a07a202455e954a2eb203c5bb443f77.

Huellas PUBLICADAS que coinciden (el MD5 de los bytes tal cual):
- DTD eCTD 3.2: 1d6f631cc6b6357f0f4fe378e5f79a27. La publican ICH (pagina https://www.ich.org/page/ich-electronic-common-technical-document-ectd-v322-specification-and-related-files, texto «The checksum for the eCTD DTD is: ...») y los criterios de validacion de varias agencias (EU, Health Canada, Tailandia, Ucrania). LIMITE: leí el texto de ICH solo como fragmento de un buscador (la pagina se genera con JavaScript y mi descarga directa devolvio la envoltura vacia), y los documentos de las agencias solo como fragmentos; no abri esos documentos completos.
- Hoja de estilo ectd-2-0.xsl: 3a07a202455e954a2eb203c5bb443f77, «the checksum corresponding to the stylesheet from eCTD specification v3.2 (ectd-2-0.xsl)» en los criterios de Tailandia y Ucrania (mismo limite: fragmento de buscador).
- DTD del STF 2.2: NO se ha localizado una huella publicada. Solo esta contrastado contra el servidor de ICH.

Conclusion por fichero: ich-ectd-3-2.dtd y ectd-2-0.xsl: VERIFICADOS (igual al que sirve ICH hoy y su MD5 coincide con el publicado, con el limite de lectura indicado). ich-stf-v2-2.dtd: VERIFICADO SOLO contra el servidor de ICH.
Limites que quedan: (a) la verificacion es contra el mismo servidor de ICH del que se descargo el 15-oct: no hay una segunda copia independiente de los ficheros, solo la huella publicada; (b) ICH puede cambiar el fichero: la comprobacion en linea es opt-in (`VALIDADOR_VERIFICAR_ICH=1`) y falla si no hay red; (c) `screen.css` sigue sin fuente oficial localizada y no se incluye.
