---
name: pdf2img
description: >
  Convert a PDF file into per-page PNG images and save them into a dedicated
  subfolder inside the artifacts directory. Use this skill whenever the user
  provides a PDF path (e.g. ~/Downloads/6660-SPS.pdf) and asks to extract,
  convert, or save its pages as images. The output folder is named after the
  PDF file stem (e.g. artifacts/6660-SPS/).
---

# pdf2img

Convert every page of a PDF into individual PNG images.

## Workflow

1. **Derive the output directory** from the PDF file stem:
   ```
   pdf_path  = ~/Downloads/6660-SPS.pdf
   stem      = 6660-SPS
   output_dir = <ARTIFACTS_DIR>/6660-SPS/
   ```

2. **Run the bundled script** via `execute_code` or `bash`:
   ```bash
   python skills/pdf2img/scripts/pdf2img.py "<pdf_path>" "<output_dir>"
   ```
   The script auto-installs `pymupdf` if it is missing.

3. **Report results** – list the saved image paths and total page count to the user.

## Script

`scripts/pdf2img.py` — accepts two positional arguments:

| Argument     | Description                              |
|-------------|------------------------------------------|
| `pdf_path`   | Path to the source PDF (supports `~`)   |
| `output_dir` | Destination folder (created if absent)  |

Default resolution is **150 DPI** (clear enough for most documents).  
Images are named `page_001.png`, `page_002.png`, … in order.

## Dependencies

- `pymupdf` (`fitz`) — auto-installed by the script if missing.

## Example

User says: "~/Downloads/6660-SPS.pdf 파일을 이미지로 변환해줘"

```python
import subprocess, sys
script = "skills/pdf2img/scripts/pdf2img.py"
pdf    = os.path.expanduser("~/Downloads/6660-SPS.pdf")
outdir = os.path.join(ARTIFACTS_DIR, "6660-SPS")
subprocess.run([sys.executable, script, pdf, outdir], check=True)
```
