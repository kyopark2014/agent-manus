#!/usr/bin/env python3
"""
img2textocr.py — Extract text from an image using Tesseract OCR.

Usage:
    python img2textocr.py <image_path> [output_txt_path]
                         [--top-crop FLOAT] [--bottom-crop FLOAT]
                         [--lang LANG] [--psm INT]

Arguments:
    image_path       Path to source image (PNG, JPG, etc.)
    output_txt_path  (Optional) Output .txt path. Defaults to same stem as image.

Options:
    --top-crop    FLOAT  Fraction of image height to crop from top    (default: 0.09)
    --bottom-crop FLOAT  Fraction of image height to crop from bottom (default: 0.04)
    --lang        STR    Tesseract language code                       (default: eng)
    --psm         INT    Tesseract page segmentation mode              (default: 6)
"""

import sys
import os
import re
import argparse

# ── auto-install dependencies ────────────────────────────────────────────────
import subprocess

def _ensure(*packages):
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

_ensure("pytesseract", "Pillow")
# ────────────────────────────────────────────────────────────────────────────

import pytesseract
from PIL import Image, ImageEnhance


def crop_header_footer(img: Image.Image, top_frac: float, bottom_frac: float) -> Image.Image:
    """Remove header (top) and footer (bottom) by fraction of total height."""
    w, h = img.size
    top_px    = int(h * top_frac)
    bottom_px = int(h * bottom_frac)
    return img.crop((0, top_px, w, h - bottom_px))


def preprocess(img: Image.Image) -> Image.Image:
    """Convert to grayscale and enhance contrast/sharpness for better OCR."""
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    return img


def remove_page_number_lines(text: str) -> str:
    """Strip common NEC-style footer lines that may survive cropping."""
    lines = text.split("\n")
    cleaned = [
        line for line in lines
        if not re.search(r"^\s*\d{2}-\d+\s+NATIONAL ELECTRICAL CODE", line, re.IGNORECASE)
    ]
    return "\n".join(cleaned)


def ocr_image(
    image_path: str,
    output_path: str,
    top_frac: float = 0.09,
    bottom_frac: float = 0.04,
    lang: str = "eng",
    psm: int = 6,
) -> str:
    """Main OCR pipeline. Returns extracted text."""
    img = Image.open(image_path)
    w, h = img.size
    print(f"[img2textocr] Source : {image_path}  ({w}x{h})")
    print(f"[img2textocr] Crop   : top={top_frac*100:.0f}%  bottom={bottom_frac*100:.0f}%")

    img = crop_header_footer(img, top_frac, bottom_frac)
    img = preprocess(img)

    config = f"--psm {psm} --dpi 300"
    text = pytesseract.image_to_string(img, lang=lang, config=config)
    text = remove_page_number_lines(text)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"[img2textocr] Saved  : {output_path}  ({len(text)} chars)")
    return text


# ── CLI entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCR an image to text, stripping header/footer.")
    parser.add_argument("image_path",            help="Path to the source image")
    parser.add_argument("output_path", nargs="?", help="Output .txt path (default: <image_stem>.txt)")
    parser.add_argument("--top-crop",    type=float, default=0.09, help="Top crop fraction    (default: 0.09)")
    parser.add_argument("--bottom-crop", type=float, default=0.04, help="Bottom crop fraction (default: 0.04)")
    parser.add_argument("--lang",        type=str,   default="eng", help="Tesseract lang code (default: eng)")
    parser.add_argument("--psm",         type=int,   default=6,     help="Page segmentation mode (default: 6)")
    args = parser.parse_args()

    image_path = os.path.expanduser(args.image_path)

    if args.output_path:
        output_path = os.path.expanduser(args.output_path)
    else:
        stem = os.path.splitext(os.path.basename(image_path))[0]
        output_path = os.path.join(os.path.dirname(image_path), f"{stem}.txt")

    ocr_image(
        image_path=image_path,
        output_path=output_path,
        top_frac=args.top_crop,
        bottom_frac=args.bottom_crop,
        lang=args.lang,
        psm=args.psm,
    )
