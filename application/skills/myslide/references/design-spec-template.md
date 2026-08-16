# Design Spec — Pre-PPTX Planning Document

A design spec is a single markdown file the agent produces **before** any
PptxGenJS code runs. The user reviews and approves it (optionally with the
HTML preview from `scripts/render_design_preview.py`). This catches structural
mistakes — wrong slide order, repeated layouts, missing diagrams — at a stage
where they cost minutes to fix, not hours.

Save the spec to `<user's working dir>/design-specs/<deck-name>.md` (create
the directory if needed). The spec lives alongside the deck the user is
building, not inside the skill repo. The file becomes the source of truth
for the PPTX build step.

## When to produce a spec

| Scope | Spec required? | Preview required? |
|-------|---------------|-------------------|
| 1-2 slides, single edit | No — proceed directly | No |
| 3-7 slide deck | Yes — markdown only | Optional |
| 8+ slide deck | Yes — markdown | Yes — HTML preview |
| User says "design first" / "plan first" / "디자인 먼저" | Always full | Always full |

The reason for the split: a quick one-pager doesn't benefit from the gate
(the friction outweighs the savings), but multi-slide decks are where slide
order, layout variety, and theme choice actually drive the most rework.

## Spec structure

The spec has four sections — Meta, Theme, Slides, Open Questions. Use the
template below verbatim. Keep prose short; the spec is a working document,
not documentation.

```markdown
# Design Spec — <deck title>

## Meta
- **Audience**: <who's in the room — execs, builders, customers, students>
- **Duration**: <e.g., 20 min, 45 min keynote>
- **Goal**: <one sentence — what the audience should believe/do after>
- **Slide count**: <number>
- **Generated**: <YYYY-MM-DD>

## Theme
- **Theme**: Dark (reInvent) | Light (L100/field enablement)
- **Reasoning**: <why this theme fits the audience/context>
- **Palette accent**: <if light theme: primary accent color choice>

## Slides

| # | Title | Layout | Key Message | Visual | SVG/Diagram | Notes |
|---|-------|--------|-------------|--------|-------------|-------|
| 1 | <title> | Title | <one-liner> | gradient bg | — | Two-speaker? |
| 2 | <title> | Agenda | 4 items | — | — | |
| 3 | <title> | Section Header | "01" | swirl bg | — | |
| 4 | <title> | Hub-Spoke | <pain → hub → solution> | SVG | radial 5-node | text on right |
| 5 | <title> | Architecture | <data flow desc> | SVG | high-level | EventBridge center |
| 6 | <title> | Comparison Table | <2 options compared> | table | — | 4 rows max |
| 7 | <title> | Process Flow | <3 steps> | SVG | horizontal | left→right |
| 8 | <title> | Summary Grid | 4 takeaways | — | — | 2x2 |
| 9 | Thank You | Thank You | — | gradient bg | — | |

## Open Questions

<list anything you need the user to confirm before building — e.g.,
- "Should slide 5 use Bedrock or AgentCore as the hub?"
- "Do we have customer logos for slide 6 case study?">
```

### Layout column — allowed values

Use these exact strings to match the patterns in `slide-patterns.md` and
`light-theme.md`. The HTML preview generator keys on these values.

**Both themes:**
- `Title`, `Title (Two Speakers)`, `Agenda`, `Section Header`
- `Content Card`, `Two Column Card`, `Three Column`
- `Process Flow`, `Comparison Table`, `Architecture`
- `Venn`, `Screenshot+Text`, `Summary Grid`
- `Multi-Card Grid`, `Image Hero`, `Image + Text Split`
- `Full Image Background`, `Thank You`

**Light theme additions:**
- `Section Divider (Light)`, `Data + Citation`, `Key Points Grid`
- `Feature Badges + Screenshot`, `Full-Color Background`
- `Step Guide`, `Customer Case Study`, `Do's vs Don'ts`
- `CTA Slide`, `Dashboard Evidence`

**Hybrid (SVG visual + native text):**
- `Hub-Spoke`, `Radial 5-node`, `Horizontal Icon Strip`
- `Cross Quadrant`, `Donut Chart`, `Timeline`, `Evolution`

### Visual / SVG columns

- **Visual**: short description of the dominant visual element
  — e.g., `gradient bg`, `SVG`, `screenshot`, `table`, `hero image`, `—` (text only)
- **SVG/Diagram**: the diagram pattern if any
  — e.g., `hub-spoke`, `radial 5-node`, `architecture`, `process flow`,
  `donut`, `timeline`, `cross quadrant`, `—`

## Layout variety check

Before showing the spec to the user, scan the Layout column and verify:

1. **No 3+ identical layouts in a row.** This is the core "Visual Diversity"
   rule from SKILL.md. If you see `Content Card / Content Card / Content Card`
   in slides 3-5, the deck will feel monotonous — split with a Section Header
   or swap one card for a hybrid SVG layout.
2. **At least one SVG/diagram slide every 4-5 slides.** Pure text decks
   feel academic; visuals carry the narrative.
3. **Section Headers placed for narrative pivots**, not as filler. The
   "Specific → General" pattern in SKILL.md (case studies first, summary
   header last) often beats the default.

If any of these fail, fix the spec before showing it to the user — don't
make the user catch your variety problems.

## Approval flow

1. Write spec to `<user working dir>/design-specs/<deck-name>.md`
2. (Optional, for 8+ slide decks) Render HTML preview:
   ```bash
   python3 {skill_path}/scripts/render_design_preview.py <user working dir>/design-specs/<deck-name>.md
   ```
3. Show the user the spec path (and preview URL if rendered)
4. Wait for explicit approval — words like "go", "good", "승인", "진행", "OK"
5. Only then start the PPTX build pipeline (background generation, PptxGenJS, etc.)

If the user requests changes, edit the spec, re-render preview if applicable,
and ask again. Don't start building partially-approved specs — the cost
of changing slide 4 mid-build is much higher than editing one row in a table.

## Example

The spec block under "Spec structure" above is the authoritative template —
copy it, fill in values for your deck, and save. The template columns map
1:1 to what `render_design_preview.py` expects, so following the format
guarantees the preview renders correctly.
