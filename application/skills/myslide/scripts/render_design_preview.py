#!/usr/bin/env python3
"""
Design Spec → HTML Preview Renderer

Reads a myslide design spec (markdown with the slide table from
references/design-spec-template.md) and produces a single-file HTML preview:
theme palette chips + slide wireframe thumbnails. Opens in the default
browser so the user can sanity-check structure before any PPTX is built.

Why: The Layout column in the spec is just text; "Hub-Spoke / Hub-Spoke /
Hub-Spoke" reads fine in markdown but is obviously monotonous as thumbnails.
Cheap visual review = fewer late-stage rebuilds.

Usage:
    python3 render_design_preview.py design-specs/my-deck.md
    python3 render_design_preview.py design-specs/my-deck.md --no-open
    python3 render_design_preview.py design-specs/my-deck.md -o /tmp/preview.html

Exit codes:
    0  Preview generated successfully
    1  Spec parse failure (missing required sections)
    2  File not found
"""

import argparse
import re
import sys
import webbrowser
from html import escape
from pathlib import Path


THEME_PALETTES = {
    "dark": {
        "name": "Dark (reInvent)",
        "bg": "#09051B",
        "text": "#FFFFFF",
        "muted": "#C8D0D8",
        "card": "#161E2D",
        "accent": "#F66C02",
        "accent2": "#C91F8A",
        "accent3": "#5600C2",
    },
    "light": {
        "name": "Light (L100/Field)",
        "bg": "#FFFFFF",
        "text": "#1A1A1A",
        "muted": "#666666",
        "card": "#F5F0EB",
        "accent": "#4FC3F7",
        "accent2": "#6B46C1",
        "accent3": "#C96842",
    },
}


def parse_spec(md_text: str) -> dict:
    """Pull Meta, Theme, Slides table, Open Questions out of the spec markdown."""
    spec = {
        "title": "",
        "meta": {},
        "theme": "dark",
        "theme_reason": "",
        "slides": [],
        "open_questions": [],
    }

    title_match = re.search(r"^#\s+Design Spec\s*[—\-–]\s*(.+)$", md_text, re.M)
    if title_match:
        spec["title"] = title_match.group(1).strip()

    meta_block = _section(md_text, "Meta")
    for line in meta_block.splitlines():
        m = re.match(r"\s*-\s*\*\*(.+?)\*\*\s*[:：]\s*(.+)", line)
        if m:
            spec["meta"][m.group(1).strip().lower()] = m.group(2).strip()

    theme_block = _section(md_text, "Theme")
    for line in theme_block.splitlines():
        m = re.match(r"\s*-\s*\*\*Theme\*\*\s*[:：]\s*(.+)", line)
        if m:
            value = m.group(1).strip().lower()
            spec["theme"] = "light" if "light" in value else "dark"
        m2 = re.match(r"\s*-\s*\*\*Reasoning\*\*\s*[:：]\s*(.+)", line)
        if m2:
            spec["theme_reason"] = m2.group(1).strip()

    slides_block = _section(md_text, "Slides")
    spec["slides"] = _parse_slide_table(slides_block)

    questions_block = _section(md_text, "Open Questions")
    for line in questions_block.splitlines():
        m = re.match(r"\s*-\s*(.+)", line)
        if m and not m.group(1).startswith("<"):
            spec["open_questions"].append(m.group(1).strip())

    if not spec["slides"]:
        raise ValueError(
            "No slide rows found. Spec must have a `## Slides` section "
            "with a markdown table matching design-spec-template.md."
        )
    return spec


def _section(md_text: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s|\Z)"
    m = re.search(pattern, md_text, re.M)
    return m.group(1) if m else ""


def _parse_slide_table(block: str) -> list[dict]:
    slides = []
    rows = [
        line for line in block.splitlines()
        if line.strip().startswith("|") and not re.match(r"^\s*\|[\s\-:|]+\|\s*$", line)
    ]
    if len(rows) < 2:
        return []
    header = [c.strip().lower() for c in rows[0].strip("|").split("|")]
    expected = {"#", "title", "layout", "key message", "visual", "svg/diagram", "notes"}
    if not expected.issubset(set(header)):
        return []
    idx = {name: header.index(name) for name in expected}
    for raw in rows[1:]:
        cells = [c.strip() for c in raw.strip("|").split("|")]
        if len(cells) < len(header):
            continue
        slides.append({
            "n": cells[idx["#"]],
            "title": cells[idx["title"]],
            "layout": cells[idx["layout"]],
            "message": cells[idx["key message"]],
            "visual": cells[idx["visual"]],
            "svg": cells[idx["svg/diagram"]],
            "notes": cells[idx["notes"]],
        })
    return slides


def variety_warnings(slides: list[dict]) -> list[str]:
    """Return human-readable warnings about layout variety."""
    warnings = []
    streak_layout, streak_count, streak_start = None, 0, 0
    for i, s in enumerate(slides):
        layout = s["layout"]
        if layout == streak_layout:
            streak_count += 1
            if streak_count == 3:
                warnings.append(
                    f"Slides {streak_start + 1}–{i + 1} all use “{layout}”. "
                    "Three identical layouts in a row creates visual fatigue — "
                    "consider swapping one for a Section Header or hybrid SVG layout."
                )
        else:
            streak_layout, streak_count, streak_start = layout, 1, i

    has_visual = any(s["svg"] not in ("", "—", "-") for s in slides)
    if len(slides) >= 5 and not has_visual:
        warnings.append(
            "No SVG/diagram slides in the deck. Pure-text decks feel academic — "
            "consider at least one hub-spoke, architecture, or process-flow slide."
        )

    return warnings


def render_html(spec: dict) -> str:
    palette = THEME_PALETTES[spec["theme"]]
    warnings = variety_warnings(spec["slides"])

    palette_chips = "".join(
        f'<div class="chip"><span class="swatch" style="background:{color}"></span>'
        f'<span class="chip-label">{escape(label)}</span>'
        f'<span class="chip-hex">{color}</span></div>'
        for label, color in [
            ("Background", palette["bg"]),
            ("Primary Text", palette["text"]),
            ("Muted", palette["muted"]),
            ("Card", palette["card"]),
            ("Accent", palette["accent"]),
            ("Accent 2", palette["accent2"]),
            ("Accent 3", palette["accent3"]),
        ]
    )

    meta_rows = "".join(
        f'<div class="meta-row"><span class="meta-key">{escape(k.title())}</span>'
        f'<span class="meta-val">{escape(v)}</span></div>'
        for k, v in spec["meta"].items()
    )

    slide_cards = "".join(_slide_card_html(s, palette) for s in spec["slides"])

    warnings_html = ""
    if warnings:
        items = "".join(f"<li>{escape(w)}</li>" for w in warnings)
        warnings_html = f'<section class="warnings"><h3>⚠ Variety check</h3><ul>{items}</ul></section>'

    questions_html = ""
    if spec["open_questions"]:
        items = "".join(f"<li>{escape(q)}</li>" for q in spec["open_questions"])
        questions_html = f'<section class="questions"><h3>Open Questions</h3><ul>{items}</ul></section>'

    title = escape(spec["title"] or "Untitled Deck")
    theme_label = escape(palette["name"])
    theme_reason = escape(spec["theme_reason"])
    slide_count = len(spec["slides"])

    return _HTML_TEMPLATE.format(
        title=title,
        theme_label=theme_label,
        theme_reason=theme_reason,
        slide_count=slide_count,
        meta_rows=meta_rows,
        palette_chips=palette_chips,
        warnings_html=warnings_html,
        slide_cards=slide_cards,
        questions_html=questions_html,
    )


def _slide_card_html(slide: dict, palette: dict) -> str:
    wire = _wireframe_svg(slide["layout"], palette)
    visual_tag = ""
    if slide["svg"] and slide["svg"] not in ("—", "-"):
        visual_tag = f'<span class="tag tag-svg">SVG · {escape(slide["svg"])}</span>'
    return f"""
    <article class="slide-card">
      <div class="slide-thumb" style="background:{palette['bg']}">
        {wire}
      </div>
      <div class="slide-meta">
        <div class="slide-num">{escape(slide['n'])}</div>
        <h4>{escape(slide['title'])}</h4>
        <div class="slide-tags">
          <span class="tag">{escape(slide['layout'])}</span>
          {visual_tag}
        </div>
        <p class="slide-msg">{escape(slide['message'])}</p>
        {f'<p class="slide-notes">{escape(slide["notes"])}</p>' if slide['notes'] and slide['notes'] != '—' else ''}
      </div>
    </article>
    """


def _wireframe_svg(layout: str, palette: dict) -> str:
    """Tiny abstract wireframe per layout family. Goal: convey shape, not detail."""
    text, accent, card, muted = palette["text"], palette["accent"], palette["card"], palette["muted"]
    layout_lower = layout.lower()

    def rect(x, y, w, h, fill, opacity=1.0):
        return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" opacity="{opacity}" rx="2"/>'

    def line(x1, y1, x2, y2, stroke):
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="1"/>'

    def circle(cx, cy, r, fill):
        return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>'

    body = ""
    if "title" in layout_lower and "two" in layout_lower:
        body = rect(10, 35, 80, 8, text, 0.9) + rect(10, 50, 50, 4, muted, 0.6) + \
               circle(20, 75, 4, accent) + circle(35, 75, 4, accent)
    elif "title" in layout_lower or "thank" in layout_lower:
        body = rect(10, 35, 80, 8, text, 0.9) + rect(10, 50, 50, 4, muted, 0.6) + \
               rect(10, 75, 30, 3, accent, 0.8)
    elif "agenda" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + "".join(
            rect(10, 30 + i * 12, 80, 6, card, 0.7) for i in range(4)
        )
    elif "section" in layout_lower:
        body = rect(8, 40, 14, 14, accent, 0.9) + rect(28, 42, 60, 6, text, 0.9) + \
               rect(28, 55, 40, 3, muted, 0.6)
    elif "two column" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + rect(10, 28, 38, 50, card, 0.7) + \
               rect(52, 28, 38, 50, card, 0.7)
    elif "three column" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + rect(10, 28, 25, 50, card, 0.7) + \
               rect(38, 28, 25, 50, card, 0.7) + rect(66, 28, 25, 50, card, 0.7)
    elif "process flow" in layout_lower or "step" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + "".join(
            rect(10 + i * 28, 40, 22, 25, card, 0.7) + circle(21 + i * 28, 52, 4, accent)
            for i in range(3)
        ) + line(34, 52, 38, 52, muted) + line(62, 52, 66, 52, muted)
    elif "comparison" in layout_lower or "table" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + rect(10, 28, 80, 6, accent, 0.6) + \
               "".join(rect(10, 36 + i * 8, 80, 6, card, 0.5) for i in range(5))
    elif "architecture" in layout_lower or "hub" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + circle(50, 55, 8, accent) + \
               circle(25, 40, 5, card) + circle(75, 40, 5, card) + \
               circle(25, 70, 5, card) + circle(75, 70, 5, card) + \
               line(30, 42, 44, 53, muted) + line(70, 42, 56, 53, muted) + \
               line(30, 68, 44, 57, muted) + line(70, 68, 56, 57, muted)
    elif "radial" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + circle(50, 52, 9, accent) + \
               "".join(
                   circle(50 + 25 * round(__import__("math").cos(a), 3),
                          52 + 22 * round(__import__("math").sin(a), 3), 5, card)
                   for a in [0, 1.26, 2.51, 3.77, 5.03]
               )
    elif "summary grid" in layout_lower or "multi-card" in layout_lower or "key points" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + "".join(
            rect(10 + (i % 2) * 42, 28 + (i // 2) * 26, 38, 22, card, 0.7) for i in range(4)
        )
    elif "venn" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + circle(40, 55, 18, accent) + \
               circle(60, 55, 18, palette["accent2"])
    elif "image hero" in layout_lower or "full image" in layout_lower:
        body = rect(0, 0, 100, 80, card, 0.8) + rect(0, 60, 100, 20, palette["bg"], 0.7) + \
               rect(10, 65, 60, 6, text, 0.9)
    elif "image + text" in layout_lower or "screenshot" in layout_lower or "dashboard" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + rect(10, 28, 38, 50, card, 0.8) + \
               rect(52, 28, 38, 6, text, 0.7) + rect(52, 38, 38, 4, muted, 0.5) + \
               rect(52, 46, 38, 4, muted, 0.5) + rect(52, 54, 38, 4, muted, 0.5)
    elif "do" in layout_lower and "don" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + rect(10, 28, 38, 50, "#3FB950", 0.5) + \
               rect(52, 28, 38, 50, "#F85149", 0.5)
    elif "donut" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + circle(40, 55, 18, accent) + \
               circle(40, 55, 9, palette["bg"])
    elif "timeline" in layout_lower or "evolution" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + line(10, 55, 90, 55, muted) + \
               "".join(circle(15 + i * 18, 55, 4, accent) for i in range(5))
    elif "cta" in layout_lower or "full-color" in layout_lower:
        body = rect(0, 0, 100, 80, accent, 0.9) + rect(15, 30, 70, 8, text, 0.95) + \
               rect(15, 48, 50, 4, palette["bg"], 0.8)
    elif "cross quadrant" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + line(50, 28, 50, 78, muted) + \
               line(10, 53, 90, 53, muted) + circle(28, 40, 4, accent) + \
               circle(72, 40, 4, accent) + circle(28, 65, 4, accent) + circle(72, 65, 4, accent)
    elif "case study" in layout_lower:
        body = rect(10, 15, 30, 8, accent, 0.5) + rect(45, 17, 45, 4, text, 0.7) + \
               rect(10, 30, 80, 14, card, 0.7) + rect(10, 47, 80, 14, card, 0.7) + \
               rect(10, 64, 80, 14, card, 0.7)
    elif "data" in layout_lower and "citation" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + \
               "".join(rect(15 + i * 14, 70 - i * 8, 8, i * 8 + 8, accent, 0.7) for i in range(5)) + \
               rect(10, 75, 80, 4, muted, 0.5)
    elif "feature" in layout_lower and "badge" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + \
               "".join(rect(10, 28 + i * 10, 22, 6, accent, 0.5) for i in range(4)) + \
               rect(40, 28, 50, 50, card, 0.8)
    elif "content card" in layout_lower:
        body = rect(10, 15, 50, 6, text, 0.9) + rect(10, 28, 80, 50, card, 0.7) + \
               rect(15, 35, 12, 12, accent, 0.7) + rect(32, 35, 50, 4, text, 0.7) + \
               "".join(rect(15, 52 + i * 6, 70, 3, muted, 0.5) for i in range(3))
    else:
        body = rect(10, 15, 50, 6, text, 0.9) + rect(10, 28, 80, 50, card, 0.5) + \
               "".join(rect(15, 35 + i * 8, 70, 3, muted, 0.5) for i in range(5))

    return f'<svg viewBox="0 0 100 80" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet">{body}</svg>'


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{title} — Design Preview</title>
<style>
  :root {{
    --bg: #0E1116;
    --panel: #161B22;
    --border: #30363D;
    --text: #F0F6FC;
    --muted: #8B949E;
    --accent: #58A6FF;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: -apple-system, "SF Pro Display", "Pretendard", sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.5;
  }}
  header {{
    padding: 32px 48px 24px; border-bottom: 1px solid var(--border);
  }}
  header h1 {{ margin: 0 0 8px; font-size: 28px; font-weight: 700; }}
  header .sub {{ color: var(--muted); font-size: 14px; }}
  .container {{ max-width: 1280px; margin: 0 auto; padding: 32px 48px; }}
  .grid-2 {{ display: grid; grid-template-columns: 320px 1fr; gap: 32px; }}
  .panel {{
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 8px; padding: 20px;
  }}
  .panel h3 {{ margin: 0 0 16px; font-size: 14px; text-transform: uppercase;
                letter-spacing: 0.05em; color: var(--muted); }}
  .meta-row {{ display: flex; justify-content: space-between; padding: 6px 0;
              border-bottom: 1px solid var(--border); font-size: 13px; }}
  .meta-row:last-child {{ border-bottom: none; }}
  .meta-key {{ color: var(--muted); }}
  .chip {{ display: flex; align-items: center; gap: 8px; padding: 6px 0;
          font-size: 12px; }}
  .swatch {{ width: 18px; height: 18px; border-radius: 4px;
             border: 1px solid var(--border); flex: none; }}
  .chip-label {{ flex: 1; }}
  .chip-hex {{ color: var(--muted); font-family: ui-monospace, monospace; font-size: 11px; }}
  .warnings {{ background: rgba(255, 165, 0, 0.08); border: 1px solid #FF9F43;
              border-radius: 8px; padding: 16px 20px; margin-bottom: 24px; }}
  .warnings h3 {{ margin: 0 0 8px; color: #FF9F43; font-size: 14px; }}
  .warnings ul {{ margin: 0; padding-left: 20px; font-size: 13px; }}
  .questions {{ background: rgba(88, 166, 255, 0.06); border: 1px solid var(--accent);
                border-radius: 8px; padding: 16px 20px; margin-top: 24px; }}
  .questions h3 {{ margin: 0 0 8px; color: var(--accent); font-size: 14px; }}
  .questions ul {{ margin: 0; padding-left: 20px; font-size: 13px; }}
  .slides-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 20px; margin-top: 24px;
  }}
  .slide-card {{
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 8px; overflow: hidden;
  }}
  .slide-thumb {{
    aspect-ratio: 16 / 9; padding: 0; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: center;
  }}
  .slide-thumb svg {{ width: 100%; height: 100%; }}
  .slide-meta {{ padding: 14px 16px; }}
  .slide-num {{ color: var(--muted); font-size: 11px; font-family: ui-monospace, monospace;
                margin-bottom: 4px; }}
  .slide-meta h4 {{ margin: 0 0 8px; font-size: 15px; font-weight: 600; }}
  .slide-tags {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }}
  .tag {{ font-size: 10px; padding: 2px 8px; border-radius: 10px;
          background: rgba(139, 148, 158, 0.15); color: var(--muted);
          text-transform: uppercase; letter-spacing: 0.04em; }}
  .tag-svg {{ background: rgba(88, 166, 255, 0.15); color: var(--accent); }}
  .slide-msg {{ font-size: 12px; color: var(--muted); margin: 0 0 4px; line-height: 1.4; }}
  .slide-notes {{ font-size: 11px; color: var(--muted); margin: 4px 0 0;
                  font-style: italic; }}
  .approval-banner {{
    background: linear-gradient(90deg, rgba(88, 166, 255, 0.12), rgba(88, 166, 255, 0.04));
    border: 1px solid var(--accent); border-radius: 8px;
    padding: 16px 20px; margin-top: 32px; font-size: 14px;
  }}
  .approval-banner strong {{ color: var(--accent); }}
</style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <div class="sub">{theme_label} · {slide_count} slides · {theme_reason}</div>
  </header>
  <div class="container">
    <div class="grid-2">
      <aside>
        <div class="panel">
          <h3>Meta</h3>
          {meta_rows}
        </div>
        <div class="panel" style="margin-top: 20px;">
          <h3>Color Theme</h3>
          {palette_chips}
        </div>
      </aside>
      <main>
        {warnings_html}
        <h3 style="font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin: 0;">Slide Outline</h3>
        <div class="slides-grid">
          {slide_cards}
        </div>
        {questions_html}
        <div class="approval-banner">
          <strong>Next step:</strong> Review the spec above. Reply
          <code>승인</code> / <code>go</code> / <code>OK</code> to start the PPTX build,
          or describe changes you'd like in the spec first.
        </div>
      </main>
    </div>
  </div>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a myslide design spec to an HTML preview."
    )
    parser.add_argument("spec", type=Path, help="Path to design spec markdown")
    parser.add_argument("-o", "--output", type=Path,
                        help="HTML output path (default: alongside spec)")
    parser.add_argument("--no-open", action="store_true",
                        help="Don't auto-open in browser")
    args = parser.parse_args()

    if not args.spec.exists():
        print(f"Error: spec not found: {args.spec}", file=sys.stderr)
        return 2

    md = args.spec.read_text(encoding="utf-8")
    try:
        spec = parse_spec(md)
    except ValueError as e:
        print(f"Error parsing spec: {e}", file=sys.stderr)
        return 1

    html = render_html(spec)
    out = args.output or args.spec.with_suffix(".preview.html")
    out.write_text(html, encoding="utf-8")
    print(f"Preview written: {out}")
    print(f"Slides: {len(spec['slides'])} | Theme: {THEME_PALETTES[spec['theme']]['name']}")

    if not args.no_open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
