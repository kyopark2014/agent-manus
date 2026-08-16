#!/usr/bin/env python3
"""
Recall home / residence location from AgentCore memory.

Used by korea-weather when the user does not name a place.
Requires application/mcp_memory.py (AGENTCORE_USER_ID optional).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys

_APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(filename)s:%(lineno)d | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("korea-weather-memory")

DEFAULT_QUERY = "집 주소 자택 거주 지역 동네 홈 주소 home address residence"
LOCATION_NOT_FOUND = "LOCATION_NOT_FOUND"


def memory_contents_to_text(contents) -> str:
    """Flatten recall_memory contents into searchable text."""
    chunks: list[str] = []
    if not contents:
        return ""
    if isinstance(contents, dict):
        contents = contents.get("text") or contents.get("content") or [contents]
    if not isinstance(contents, list):
        contents = [contents]
    for item in contents:
        if isinstance(item, dict):
            if "text" in item and isinstance(item["text"], str):
                chunks.append(item["text"])
            else:
                for k, v in item.items():
                    if isinstance(v, str) and v.strip():
                        chunks.append(f"{k}: {v}")
                    elif isinstance(v, (list, dict)):
                        chunks.append(str(v))
        elif isinstance(item, str):
            chunks.append(item)
        else:
            chunks.append(str(item))
    return "\n".join(chunks)


def extract_address_candidates(text: str) -> list[str]:
    """Pull Korean address-like phrases from memory text."""
    if not text:
        return []
    candidates: list[str] = []

    for m in re.finditer(
        r"((?:서울|부산|대구|인천|광주|대전|울산|세종|제주)[^\n,]{0,4}"
        r"(?:특별시|광역시|특별자치시|특별자치도|시)?\s*"
        r"[가-힣0-9]+(?:시|군|구)\s*[가-힣0-9]+(?:동|읍|면|로|길)?)",
        text,
    ):
        candidates.append(re.sub(r"\s+", " ", m.group(1)).strip())

    for m in re.finditer(r"([가-힣]+구\s*[가-힣0-9]+동)", text):
        candidates.append(re.sub(r"\s+", " ", m.group(1)).strip())

    for m in re.finditer(
        r"(?:집|자택|거주|주소|home|address)\s*[:：]?\s*([가-힣A-Za-z0-9\s]+)",
        text,
        re.I,
    ):
        val = re.sub(r"\s+", " ", m.group(1)).strip(" .")
        if 2 <= len(val) <= 40:
            candidates.append(val)

    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _place_like_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if any(k in line for k in ("시", "구", "동", "군")) and 2 <= len(line) <= 40:
            lines.append(line)
    return lines


def recall_home_location(query: str = DEFAULT_QUERY, max_results: int = 10) -> dict:
    """
    Look up home/residence address text from AgentCore memory.

    Returns:
      {
        "status": "ok" | "not_found" | "error",
        "location": str | None,   # best address query for get_weather.py
        "candidates": list[str],
        "error": str | None,
      }
    """
    try:
        import mcp_memory
    except Exception as e:
        logger.warning(f"mcp_memory import failed: {e}")
        return {
            "status": "error",
            "location": None,
            "candidates": [],
            "error": f"mcp_memory import failed: {e}",
        }

    try:
        result = mcp_memory.recall_memory(
            action="retrieve",
            query=query,
            max_results=max_results,
        )
    except Exception as e:
        logger.warning(f"memory recall failed: {e}")
        return {
            "status": "error",
            "location": None,
            "candidates": [],
            "error": f"memory recall failed: {e}",
        }

    text = memory_contents_to_text(result)
    if not text.strip():
        logger.info("memory recall returned no usable text")
        return {
            "status": "not_found",
            "location": None,
            "candidates": [],
            "error": None,
        }

    logger.info(f"memory text for location (truncated): {text[:300]}")
    candidates = extract_address_candidates(text)
    if not candidates:
        candidates = _place_like_lines(text)

    if not candidates:
        return {
            "status": "not_found",
            "location": None,
            "candidates": [],
            "error": None,
        }

    return {
        "status": "ok",
        "location": candidates[0],
        "candidates": candidates,
        "error": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recall home/residence location from AgentCore memory for weather lookup."
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="Memory search query (default: home/residence keywords)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Max memory records to retrieve (default: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of a plain location string",
    )
    args = parser.parse_args()

    result = recall_home_location(query=args.query, max_results=args.max_results)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "ok" else 1

    if result["status"] == "ok" and result.get("location"):
        print(result["location"])
        return 0

    print(LOCATION_NOT_FOUND)
    if result.get("error"):
        print(result["error"], file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
