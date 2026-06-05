#!/usr/bin/env python3
"""
pdf_triage.py — Text-layer-first triage for PDFs.

Decides, per file and per page, whether a PDF already has a usable text
layer (extract directly) or is a scan that needs OCR.

Usage:
    python3 pdf_triage.py file1.pdf [file2.pdf ...]
    python3 pdf_triage.py *.pdf

Dependency:
    pip install pypdf
"""

import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit("Missing dependency. Run:  pip install pypdf")

# A page with fewer than this many extracted characters is treated as
# "no real text layer" (i.e. a scanned image page).
MIN_CHARS_PER_PAGE = 100


def triage(path: Path):
    try:
        reader = PdfReader(str(path))
    except Exception as e:
        print(f"  ERROR opening {path.name}: {e}")
        return

    n = len(reader.pages)
    scanned_pages = []
    total_chars = 0
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        total_chars += len(text)
        if len(text.strip()) < MIN_CHARS_PER_PAGE:
            scanned_pages.append(i + 1)  # 1-based for humans

    if not scanned_pages:
        verdict = "TEXT  -> extract directly, NO OCR needed"
    elif len(scanned_pages) == n:
        verdict = "SCAN  -> OCR all pages"
    else:
        verdict = f"MIXED -> OCR pages {scanned_pages}"

    print(f"{path.name}")
    print(f"  pages: {n}   total extracted chars: {total_chars:,}")
    print(f"  verdict: {verdict}\n")


def main(argv):
    files = [Path(a) for a in argv]
    if not files:
        sys.exit(__doc__)
    for f in files:
        if f.exists():
            triage(f)
        else:
            print(f"  NOT FOUND: {f}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
