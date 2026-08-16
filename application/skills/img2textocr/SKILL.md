---
name: img2textocr
description: >
  Extract text from an image file (PNG, JPG, etc.) using Tesseract OCR and save
  the result as a .txt file. Automatically crops the top header and bottom footer
  regions before OCR so that page titles, section headings in the margin, and
  page numbers are excluded from the output.
  Use this skill whenever the user wants to convert an image to text, extract
  body text from a scanned page, or perform OCR on a document image while
  skipping headers and footers (e.g. "page_033.png을 텍스트로 변환해줘",
  "이 이미지에서 본문만 추출해줘", "img2text로 변환해줘").
---

# img2textocr

Convert a document image to plain text using Tesseract OCR, with automatic
header/footer removal.

## Workflow

1. **Identify the source image** from the user's request (e.g. `artifacts/2017-NEC-Code/page_033.png`).
2. **Determine the output path** — default: same directory, same stem, `.txt` extension.
3. **Run the bundled script** via `bash` or `execute_code`:

```bash
python skills/img2textocr/scripts/img2textocr.py "<image_path>" "<output_txt_path>"
```

4. **Report results** — show the output path and a preview of the extracted text.

## Script

`scripts/img2textocr.py` — accepts positional and optional arguments:

| Argument          | Type   | Default | Description                                      |
|-------------------|--------|---------|--------------------------------------------------|
| `image_path`      | str    | —       | Path to the source image (required)              |
| `output_path`     | str    | auto    | Output .txt path (default: `<image_stem>.txt`)   |
| `--top-crop`      | float  | 0.09    | Fraction of height to crop from top (header)     |
| `--bottom-crop`   | float  | 0.04    | Fraction of height to crop from bottom (footer)  |
| `--lang`          | str    | eng     | Tesseract language code                          |
| `--psm`           | int    | 6       | Tesseract page segmentation mode                 |

## Crop Tuning

The default crop values (top=9%, bottom=4%) are calibrated for standard NEC/NFPA
document scans (1275×1650 px). Adjust if the header or footer is still visible in
the output:

```bash
# Larger header — crop 12% from top
python skills/img2textocr/scripts/img2textocr.py page.png --top-crop 0.12

# Multi-language document
python skills/img2textocr/scripts/img2textocr.py page.png --lang kor+eng
```

## Dependencies

- `pytesseract` — Python wrapper for Tesseract (auto-installed by script)
- `Pillow` — Image processing (auto-installed by script)
- `tesseract` — Must be installed on the system (e.g. `brew install tesseract`)

## Example

User says: `"artifacts/2017-NEC-Code/page_033.png을 img2text로 변환해줘"`

```bash
python skills/img2textocr/scripts/img2textocr.py \
    artifacts/2017-NEC-Code/page_033.png \
    artifacts/2017-NEC-Code/page_033.txt
```

Output: `artifacts/2017-NEC-Code/page_033.txt` (header/footer excluded)
