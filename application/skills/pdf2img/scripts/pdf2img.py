#!/usr/bin/env python3
"""
pdf2img.py — Convert each page of a PDF file into PNG images.

Usage:
    python pdf2img.py <pdf_path> <output_dir>

Arguments:
    pdf_path    Path to the source PDF file (e.g. ~/Downloads/6660-SPS.pdf)
    output_dir  Directory where page images will be saved
                (created automatically if it does not exist)

Output:
    <output_dir>/page_001.png
    <output_dir>/page_002.png
    ...

Dependencies:
    pip install pymupdf          # imports as `fitz`
"""

import sys
import os

def pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 150) -> list[str]:
    """Convert every page of *pdf_path* to PNG and save in *output_dir*.

    Args:
        pdf_path:   Absolute or relative path to the source PDF.
        output_dir: Destination directory (created if absent).
        dpi:        Resolution for rendered images (default 150).

    Returns:
        List of absolute paths to the saved image files.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("PyMuPDF is not installed. Installing now …", file=sys.stderr)
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pymupdf"], stdout=subprocess.DEVNULL)
        import fitz

    pdf_path = os.path.expanduser(pdf_path)
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total = len(doc)
    saved = []
    zoom = dpi / 72  # 72 dpi is the PDF default
    mat = fitz.Matrix(zoom, zoom)

    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=mat, alpha=False)
        filename = f"page_{i:03d}.png"
        out_path = os.path.join(output_dir, filename)
        pix.save(out_path)
        saved.append(out_path)
        print(f"  [{i}/{total}] Saved → {out_path}")

    doc.close()
    return saved


def main():
    if len(sys.argv) < 3:
        print("Usage: pdf2img.py <pdf_path> <output_dir>", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_dir = sys.argv[2]

    print(f"Converting: {pdf_path}")
    print(f"Output dir: {output_dir}")

    saved = pdf_to_images(pdf_path, output_dir)
    print(f"\nDone — {len(saved)} image(s) saved to '{output_dir}'.")


if __name__ == "__main__":
    main()
