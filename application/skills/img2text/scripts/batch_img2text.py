#!/usr/bin/env python3
"""
Batch image→Markdown using the same pipeline as mcp_server_text_extraction.py.
Run from the application/ directory:

    python skills/img2text/scripts/batch_img2text.py "<folder_with_images>"
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# application/ is parent of skills/
_APP_ROOT = Path(__file__).resolve().parents[3]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

import mcp_server_text_extraction as tex  # noqa: E402

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"}

LLM_PROMPT = (
    "페이지 내용을 Markdown 형식으로 변환합니다. 평문이 아니라 제목(#·##)·목록·강조·코드 블록 등 "
    "Markdown 문법을 적절히 써서 구조화해 주세요. 문장 단위로 읽기 쉽게 구분합니다. "
    "상단의 header와 하단의 footer는 출력에서 제외합니다. 상단 header는 주로 현재 페이지 제목이고, "
    "footer에는 페이지 번호 등이 있는데, 변환 결과에는 포함하지 않습니다.\n\n"
    "페이지에 그림·도표·사진·스크린샷·다이어그램·캡처 등 시각적 요소가 있으면, 그 이미지가 무엇을 보여주는지·"
    "본문과 어떤 관계인지·어떤 정보를 전달하는지를 빠짐없이 상세히 풀어서 서술합니다."
)


def natural_key(path: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def list_image_files(folder: Path) -> list[Path]:
    out = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    out.sort(key=natural_key)
    return out


def extract_one(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        raw = f.read()
    b64 = tex._prepare_image_base64(raw)
    raw_text = tex._extract_text_with_llm(b64, LLM_PROMPT)
    return tex._parse_result(raw_text).strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="폴더 내 이미지를 LLM으로 Markdown 변환 후 폴더명.md로 저장"
    )
    parser.add_argument("folder", type=Path, help="이미지가 들어 있는 폴더 경로")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="출력 .md 경로 (기본: 폴더 안의 폴더이름.md)",
    )
    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        print(f"Error: 폴더가 아닙니다: {folder}", file=sys.stderr)
        return 1

    images = list_image_files(folder)
    if not images:
        print(f"Error: 이미지 파일이 없습니다: {folder}", file=sys.stderr)
        return 1

    out_path = args.output.expanduser().resolve() if args.output else folder / f"{folder.name}.md"

    parts: list[str] = []
    for i, img in enumerate(images, start=1):
        print(f"[{i}/{len(images)}] {img.name}", file=sys.stderr)
        try:
            body = extract_one(img)
        except Exception as e:
            body = f"> (추출 오류: {e})"
        parts.append(f"## 파일: {img.name}\n\n{body}\n")

    text = "\n".join(parts).rstrip() + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
