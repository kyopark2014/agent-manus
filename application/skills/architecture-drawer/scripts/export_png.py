#!/usr/bin/env python3
"""Export a .drawio / .xml diagram to PNG for chat preview.

Primary: diagrams.net convert API (Referer: app.diagrams.net).
Fallback: local `drawio` Desktop CLI if installed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


EXPORT_URL = "https://convert.diagrams.net/node/export"
REFERER = "https://app.diagrams.net/"
USER_AGENT = "aws-drawio-export/1.0"


def _read_diagram(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        xml = f.read().strip()
    if not xml:
        raise ValueError(f"Empty diagram file: {path}")
    if "<mxfile" not in xml and "<mxGraphModel" not in xml:
        raise ValueError(f"Not a draw.io XML file: {path}")
    return xml


def export_via_api(xml: str, output_path: str, *, scale: float = 2.0, border: int = 20) -> None:
    body = urllib.parse.urlencode(
        {
            "format": "png",
            "bg": "ffffff",
            "scale": str(scale),
            "border": str(border),
            "xml": xml,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        EXPORT_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": REFERER,
            "Origin": "https://app.diagrams.net",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
            content_type = (resp.headers.get("Content-Type") or "").lower()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Export API HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Export API unreachable: {e}") from e

    if "png" not in content_type and not data.startswith(b"\x89PNG"):
        preview = data[:200].decode("utf-8", errors="replace")
        raise RuntimeError(f"Export API did not return PNG ({content_type}): {preview}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)


def export_via_cli(input_path: str, output_path: str, *, scale: float = 2.0, border: int = 20) -> None:
    drawio = shutil.which("drawio")
    if not drawio:
        mac = "/Applications/draw.io.app/Contents/MacOS/draw.io"
        if os.path.isfile(mac):
            drawio = mac
    if not drawio:
        raise RuntimeError("drawio CLI not found")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    cmd = [
        drawio,
        "--export",
        "--format",
        "png",
        "--output",
        output_path,
        "--scale",
        str(scale),
        "--border",
        str(border),
        input_path,
    ]
    # Electron apps often need --no-sandbox in containers
    env = os.environ.copy()
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=180)
    if result.returncode != 0 or not os.path.isfile(output_path):
        err = (result.stderr or result.stdout or "").strip()[:500]
        raise RuntimeError(f"drawio CLI failed (code={result.returncode}): {err}")


def export_png(input_path: str, output_path: str, *, scale: float = 2.0, border: int = 20) -> str:
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")

    xml = _read_diagram(input_path)
    errors: list[str] = []

    try:
        export_via_api(xml, output_path, scale=scale, border=border)
        return output_path
    except Exception as e:
        errors.append(f"api: {e}")

    try:
        export_via_cli(input_path, output_path, scale=scale, border=border)
        return output_path
    except Exception as e:
        errors.append(f"cli: {e}")

    raise RuntimeError("PNG export failed. " + " | ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Export .drawio to PNG preview")
    parser.add_argument("input", help="Path to .drawio / .xml")
    parser.add_argument(
        "output",
        nargs="?",
        help="Output .png path (default: same name as input)",
    )
    parser.add_argument("--scale", type=float, default=2.0, help="Export scale (default 2.0)")
    parser.add_argument("--border", type=int, default=20, help="Border padding px (default 20)")
    args = parser.parse_args()

    out = args.output
    if not out:
        base, _ = os.path.splitext(args.input)
        out = base + ".png"

    try:
        path = export_png(args.input, out, scale=args.scale, border=args.border)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    size = os.path.getsize(path)
    print(f"PNG saved: {path} ({size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
