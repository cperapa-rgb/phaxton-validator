# phaxton-validator

A technical validator for eCTD v3.2.2 submission packages (Module 5 focus).
Checks FORM, not science: folder structure, index.xml backbone against the
official ICH DTD, MD5 checksums (two independent hash arbiters), leaf
references, PDF integrity and embedded fonts, file naming, and the Study
Tagging File (STF) with the file-tags required by FDA's Technical
Conformance Guide. Repairs are applied ONLY to a copy, never to the
original, with a per-change log.

## Honest status

- PARTIAL: not yet contrasted against any agency validator.
- Single-sequence packages only; lifecycle (append/replace) not supported.
- One dogfooding cycle so far, on synthetic data. It found real defects in
  our own packages before release — that is what it is for.
- Every run reports how many rules it executed and how many it did not,
  with reasons. It never reports "clean" without saying against what.

## Install

    pip install .
    phaxton-validator path/to/ectd/package

## Contact

cperapa@fractalpk.es

## License

GPL-3.0. Built by Phaxton — the suite that takes small labs from the
concentration CSV to an eCTD-ready M5 data package. Landing: see the
repository description (free Render URL until the domain exists).

Third-party licence note: the PDF report checks that fonts are embedded using PyMuPDF, which is licensed under AGPL-3.0. This tool is distributed under GPL-3.0; combined with PyMuPDF, the AGPL-3.0 terms (including section 13, use over a network) also apply to the combined work.

---

This is a PREPARATORY tool for regulatory submissions. It checks and prepares
materials BEFORE submission; it does not submit to, and is not endorsed,
certified or validated by, any regulatory agency (FDA, EMA or other). Outputs
are drafts for review by qualified professionals; acceptance of any submission
is not guaranteed. The user (sponsor/applicant) retains sole responsibility for
the content, accuracy and regulatory compliance of any submission. Automated
repairs are applied only to copies, with a logged list of changes; originals
are never modified. Provided "AS IS", without warranty of any kind. Not an
electronic records/signatures system under 21 CFR Part 11.
