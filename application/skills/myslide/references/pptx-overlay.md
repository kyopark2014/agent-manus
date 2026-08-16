# PPTX Overlay Pattern (python-pptx)

How to add elements to an existing PPTX file without regenerating the whole slide.
Use this when the customer (or their teammate) has already drawn something in
PowerPoint and you just need to add a few more nodes, arrows, or labels.

This is complementary to the from-scratch PptxGenJS workflow. Choose overlay when:
- The existing slide has hand-drawn or imported shapes you don't want to replicate
- The customer has explicit aesthetic preferences baked into their file
- You only need to add a small, well-bounded region (e.g., a new external system group)

Don't use overlay when you need to change more than ~20% of the existing shapes —
it's easier to regenerate from scratch at that point.

## Why python-pptx (not PptxGenJS)

PptxGenJS generates new PPTX from a JS description. It has no way to read and
preserve an existing file. For overlay work, python-pptx is the right tool
because it opens, mutates, and saves — leaving everything else untouched.

## The Core Workflow

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree

SRC = "/path/to/engineer-drawn.pptx"
DST = "/path/to/output-with-overlay.pptx"

pres = Presentation(SRC)
slide = pres.slides[0]

# ... add shapes, connectors, text boxes ...

pres.save(DST)
```

Always write to a different filename than the source so the original is preserved
in case the overlay needs to be rerun.

## Step 1: Enumerate Existing Shapes First

Before adding anything, dump the shapes in the target slide so you know where
the empty space actually is. Rendered screenshots lie — the coordinate grid you
see in a JPG is not the grid PowerPoint uses internally.

```python
for i, sh in enumerate(slide.shapes):
    x = sh.left / 914400 if sh.left is not None else None  # EMU → inches
    y = sh.top / 914400 if sh.top is not None else None
    w = sh.width / 914400 if sh.width is not None else None
    h = sh.height / 914400 if sh.height is not None else None
    text = sh.text_frame.text[:40] if sh.has_text_frame else ""
    print(f"{i:3d} {str(sh.shape_type)[:20]:20s} x={x} y={y} w={w} h={h} text={text!r}")
```

python-pptx stores coordinates in EMU (English Metric Units). 914400 EMU = 1 inch.
Always convert to inches for human reasoning, then convert back with `Inches()`
when building new shapes.

## Step 2: The `add_connector` Trap (read this before drawing any arrow)

**`add_connector(type, begin_x, begin_y, end_x, end_y)` takes endpoint coordinates,
NOT width/height.**

This is the single biggest source of broken arrows in overlay scripts. The
python-pptx documentation uses parameter names `left, top, width, height` in
some places, which leads people to pass widths. If you do that, the arrow
starts at the correct left/top but extends by `width` inches to the right and
`height` inches down — often putting the endpoint in the slide title area and
creating a dramatic diagonal line.

```python
# WRONG — width/height semantics
conn = slide.shapes.add_connector(1, Inches(x1), Inches(y1),
                                  Inches(abs(x2-x1)), Inches(abs(y2-y1)))

# CORRECT — endpoint semantics (python-pptx handles flipH/flipV internally)
conn = slide.shapes.add_connector(1, Inches(x1), Inches(y1),
                                  Inches(x2), Inches(y2))
```

You don't need to set `flipH`/`flipV` yourself. python-pptx computes them from
the coordinate order and writes them to the OOXML automatically.

### Verify after rendering

If an arrow renders as diagonal when you expected L-shape, the first thing to
check is the saved file's XML. Unpack with `scripts/office/unpack.py` and grep
for `<p:cxnSp>`:

```python
import re
with open(unpacked_dir + "/ppt/slides/slide1.xml") as f:
    xml = f.read()
for cxn in re.findall(r'<p:cxnSp>.*?</p:cxnSp>', xml, re.DOTALL):
    off = re.search(r'<a:off x="(-?\d+)" y="(-?\d+)"', cxn)
    ext = re.search(r'<a:ext cx="(\d+)" cy="(\d+)"', cxn)
    flip = re.search(r'<a:xfrm([^>]*)>', cxn)
    if off and ext:
        print(f"off=({int(off.group(1))/914400:.2f},{int(off.group(2))/914400:.2f})",
              f"ext=({int(ext.group(1))/914400:.2f},{int(ext.group(2))/914400:.2f})",
              f"xfrm={flip.group(1) if flip else ''}")
```

If `ext` (size) values are much larger than your intended line length, you
passed width/height to `add_connector` by mistake.

## Step 3: Dashed Lines and Arrowheads

`python-pptx` has no high-level API for dash patterns or arrowheads. You have
to inject OOXML children into the `<a:ln>` element yourself.

```python
def set_dashed_and_arrows(ln_elem, dash="dash", begin_arrow=False,
                          end_arrow=True, arrow_size="med"):
    """Add prstDash + headEnd/tailEnd children to an <a:ln>."""
    prst = etree.SubElement(ln_elem, qn('a:prstDash'))
    prst.set('val', dash)  # "solid", "dash", "dashDot", ...
    if begin_arrow:
        h = etree.SubElement(ln_elem, qn('a:headEnd'))
        h.set('type', 'triangle'); h.set('w', arrow_size); h.set('len', arrow_size)
    if end_arrow:
        t = etree.SubElement(ln_elem, qn('a:tailEnd'))
        t.set('type', 'triangle'); t.set('w', arrow_size); t.set('len', arrow_size)
```

Use like so:

```python
conn = slide.shapes.add_connector(1, Inches(x1), Inches(y1),
                                  Inches(x2), Inches(y2))
conn.line.color.rgb = RGBColor(0x8C, 0x4F, 0xFF)
conn.line.width = Pt(1.25)
ln = conn.line._get_or_add_ln()
set_dashed_and_arrows(ln, dash="dash", begin_arrow=True, end_arrow=True)
```

`_get_or_add_ln()` is the right hook — it returns the existing `<a:ln>` or
creates one. Don't manually build the element tree.

## Step 4: Text Boxes Without Padding

By default, python-pptx text boxes inherit PowerPoint's default margins
(0.1 inch each side). When you're placing labels under icons or next to other
shapes, this padding makes layouts drift. Zero the margins for precise alignment:

```python
tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
tf = tb.text_frame
tf.margin_left = 0
tf.margin_right = 0
tf.margin_top = 0
tf.margin_bottom = 0
tf.word_wrap = True
tf.vertical_anchor = MSO_ANCHOR.TOP
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
run = p.add_run()
run.text = "Label"
run.font.size = Pt(9)
run.font.bold = True
run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
run.font.name = "Noto Sans KR"  # or the font the engineer already used
```

## Step 5: Dashed Container Borders

Group boxes (external systems, logical groupings) typically use dashed borders.
python-pptx can set solid borders easily but dashed requires the same OOXML
trick as connectors:

```python
box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              Inches(x), Inches(y), Inches(w), Inches(h))
box.fill.background()  # no fill — show whatever is underneath
box.line.color.rgb = RGBColor(0x5B, 0x67, 0x70)
box.line.width = Pt(1.2)
ln = box.line._get_or_add_ln()
prst = etree.SubElement(ln, qn('a:prstDash'))
prst.set('val', 'dash')
```

`box.fill.background()` is not well-documented but it's the correct idiom for
"transparent fill". Don't use `box.fill.solid()` with a white RGB — that's
opaque white, which would cover anything beneath the shape.

## Common QA Failures and Root Causes

| Symptom in rendered PNG | Actual root cause | Fix |
|-------------------------|-------------------|-----|
| Arrow is diagonal when you wanted L-shape | Passed `width, height` to `add_connector` instead of `end_x, end_y` | Use endpoint semantics |
| Arrow crosses over slide title | Same as above — endpoint ended up at `(x1+w, y1+h)` which is off-slide | Same |
| Dashed line shows as solid | Forgot `prstDash` injection, or wrote it on the wrong element | Target `<a:ln>` via `_get_or_add_ln()` |
| Text label wraps unexpectedly | Text box width too narrow once default margins (0.2" total) are subtracted | Zero the margins on `text_frame` |
| Label ends at slide edge or clips | Anchor + width exceed slide width (13.333" on 16:9 wide) | Check `anchor_x + width <= 13.1` as safety margin |
| Container box covers other shapes | Used `fill.solid()` with white instead of `fill.background()` | Use `fill.background()` for transparent group boxes |
| Arrowhead missing | `tailEnd`/`headEnd` not injected, or injected on wrong element | Use the `set_dashed_and_arrows` helper |

## When the First Render Fails

This is expected — overlay work usually needs 1-2 correction cycles because
the empty space you imagined from the screenshot doesn't match the real
coordinate space.

The recovery loop is:

1. Regenerate PPTX
2. Convert to image (`scripts/office/soffice.py` → `pdftoppm`)
3. **Delegate visual QA to a subagent** (don't read the image in the main agent —
   context-expensive)
4. If subagent reports "diagonal arrow" / "arrow in title": unpack XML,
   verify `<a:off>` / `<a:ext>` values match your intent. Fix the call site.
5. Rerun

The XML verification step is cheap (regex, a few lines) and catches the
add_connector trap immediately. Do it after every change to a connector
until you have confidence the helper wrapper is correct.

## Arrow-Icon Collision Pre-Check

Before drawing any diagonal or long connector, trace its path mentally against
the list of existing shapes you dumped in Step 1. If the straight line between
start and end passes through the bounding box of any existing icon or text box,
the rendered arrow will appear to pierce that element — looks like a bug even
if the data is technically correct.

Two ways to fix:

1. **Route orthogonally with two segments.** Instead of one diagonal connector,
   add two perpendicular lines (vertical + horizontal) that go around the
   obstacle. Hide the arrowhead on the first segment, put it on the second.
   This is the same L-shape / Z-shape routing used in the `aws-diagram` skill.

2. **Pick a different endpoint edge.** If you're attaching to an icon, try its
   top/bottom edge instead of left/right (or vice versa). A vertical approach
   often clears an obstacle that a horizontal approach would collide with.

For dense slides with many existing shapes, favor keeping arrows SHORT. The
more empty space the connector traverses, the more likely it is to collide
with something the next time the slide layout shifts. Short arrows to/from
nearby anchor points are more robust than long arrows across the slide.

The general principle (borrowed from `slide-patterns.md > Arrow Routing Rules`):
orthogonal routing signals "intentional architecture", diagonal routing signals
"informal sketch". Overlay work usually means you're adding to an architecture
diagram, so default to orthogonal.

## Reusable Helper Module

If you find yourself using this pattern on more than one project, extract the
helpers to a small module:

```python
# overlay_helpers.py
def add_line(slide, x1, y1, x2, y2, color, weight_pt=1.25,
             dash="dash", begin_arrow=False, end_arrow=False):
    if x1 == x2 and y1 == y2:
        return None
    conn = slide.shapes.add_connector(1, Inches(x1), Inches(y1),
                                      Inches(x2), Inches(y2))
    conn.line.color.rgb = color
    conn.line.width = Pt(weight_pt)
    ln = conn.line._get_or_add_ln()
    set_dashed_and_arrows(ln, dash, begin_arrow, end_arrow)
    return conn

def add_dashed_box(slide, x, y, w, h, border_color, border_pt=1.2):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                  Inches(x), Inches(y), Inches(w), Inches(h))
    box.fill.background()
    box.line.color.rgb = border_color
    box.line.width = Pt(border_pt)
    ln = box.line._get_or_add_ln()
    prst = etree.SubElement(ln, qn('a:prstDash')); prst.set('val', 'dash')
    return box

def add_label(slide, x, y, w, h, text, size_pt=9, bold=False,
              color=RGBColor(0, 0, 0), align="center", font="Noto Sans KR"):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    p.alignment = {"center": PP_ALIGN.CENTER, "left": PP_ALIGN.LEFT,
                   "right": PP_ALIGN.RIGHT}.get(align, PP_ALIGN.LEFT)
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size_pt); run.font.bold = bold
    run.font.color.rgb = color; run.font.name = font
    return tb
```

This covers ~90% of overlay use cases (lines, boxes, labels). Extend as needed.
