"""Validador tecnico de paquetes eCTD v3.2.2 (v0). Paquete AUTOCONTENIDO: no importa nada del resto del repo.

Valida FORMA (estructura, backbone, checksums, PDF, referencias); no contenido ni terminologia CDISC.
Ver docs/ARQUITECTURA_VALIDADOR_ECTD.md.
"""

from .engine import validar_paquete, carpetas, VERSION, AVISO_PREPARATORIO  # noqa: F401
