"""Un PDF firmado digitalmente no se reescribe nunca (la firma cubre los bytes). Decision del director (D5).

Firmado = alguna de tres senales en la estructura (pikepdf lee tambien los objetos dentro de flujos de objetos): un diccionario con /ByteRange,
un diccionario /Type /Sig, o /AcroForm con /SigFlags distinto de cero. La palabra suelta en el texto del fichero NO cuenta."""

from __future__ import annotations

import pikepdf


def esta_firmado(pdf) -> bool:
    """`pdf`: pikepdf.Pdf abierto. Un fallo de lectura se propaga (PdfError): quien llama decide, nunca se devuelve False por no poder mirar."""
    try:
        form = pdf.Root.get("/AcroForm")
        if form is not None and int(form.get("/SigFlags", 0)) != 0:
            return True
    except (TypeError, ValueError):
        pass
    for obj in pdf.objects:
        if isinstance(obj, pikepdf.Dictionary) and ("/ByteRange" in obj or str(obj.get("/Type", "")) == "/Sig"):
            return True
    return False


def firmado_en_ruta(p) -> bool:
    with pikepdf.open(str(p)) as pdf:
        return esta_firmado(pdf)
