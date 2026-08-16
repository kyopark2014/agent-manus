# MySlide - AWS-Themed Presentation Generator

Create professional PowerPoint presentations with two AWS design themes:
**Dark** (reInvent 2023/2025) and **Light** (L100/field enablement).
SVG architecture diagrams, cross-skill integration, and conversational slide editing.

## Features

- **Dual Theme Support**: Dark (reInvent gradient) and Light (white + gradient blobs)
- **25+ Slide Layouts**: Title, Agenda, Section Header, Content Card, Two/Three Column,
  Key Points Grid, Do's vs Don'ts, CTA, Customer Case Study, Process Flow, Architecture,
  Comparison Table, Screenshot+Text, Summary Grid, Multi-Card Grid, Thank You, and more
- **Design Spec Gate**: Pre-build markdown spec + HTML wireframe preview for 3+ slide
  decks — catches structural rework (wrong order, monotonous layouts) at the cheapest stage
- **SVG Diagrams**: Auto-generate architecture and flow diagrams with 304 AWS service icons
  (including 56 Bedrock AgentCore component variants)
- **Cross-Skill Integration**: `svg-diagram` for pixel-perfect diagram generation
- **Animations**: OOXML-based animation system with JSON spec and Python post-processor
- **Conversational Editing**: Modify specific slides by number via natural language
- **Parallel Generation**: Sub-agent strategy (8+ slides) and team-up strategy (15+ slides)
- **Two-Phase QA**: Programmatic validation + visual inspection (kiro or subagent)

## Quick Start

```bash
# Trigger with:
/myslide
# or natural language: "AWS 프레젠테이션 만들어줘", "create AWS slides"
# Light theme: "L100 교육 자료 만들어줘", "training deck", "light theme"
```

## Theme Selection

| Context | Theme | Trigger |
|---------|-------|---------|
| reInvent, Summit keynotes | **Dark** | Default |
| L100/L200 field enablement | **Light** | "L100", "training deck", "밝은 테마" |
| Customer-facing training | **Light** | "customer-facing", "교육 자료" |
| Internal workshops | **Light** | "workshop", "white background" |
| Technical deep-dives | Either | User preference |

## Default Presenter

| Field | Value |
|-------|-------|
| Korean Name | 발표자 |
| English Name | Name |
| Title | Solutions Architect |
| Company | Amazon Web Services |
| Email | email@amazon.com |

## Theme Colors

### Dark Theme (reInvent 2023)

| Role | Hex | Usage |
|------|-----|-------|
| Background | `#09051B` | Deep purple-black base |
| Orange | `#F66C02` | Primary emphasis, key terms |
| Magenta | `#C91F8A` | Secondary emphasis, borders |
| Purple | `#5600C2` | Gradient accents |
| Dark Navy | `#161E2D` | Card/container backgrounds |
| White | `#FFFFFF` | Body text, headings |

### Light Theme (L100/Field Enablement)

| Role | Hex | Usage |
|------|-----|-------|
| Background | `#FFFFFF` | White base |
| Sky Blue | `#4FC3F7` | Table headers, bullets, links |
| Purple | `#6B46C1` | Architecture labels, step badges |
| Coral | `#C96842` | Key stat emphasis, CTA highlights |
| AWS Orange | `#FF9900` | Internal badge, numbered badges |
| Card Fill | `#F5F0EB` | Cream/beige card backgrounds |

## Directory Structure

Runtime path in this repository: **`application/skills/myslide`** (the agent’s `WORKING_DIR` is `application/`, so this folder is **`WORKING_DIR/skills/myslide`**).

Generated assets go under **`{workspace}/artifacts/`** (project root sibling to `application/`), not `/tmp`:
- `myslide-assets/` — backgrounds, SVG/PNG, generated images
- `myslide-parts/` — per-slide PptxGenJS snippets
- `myslide-qa/` — QA render outputs (PDF, JPEG)

```
myslide/
├── SKILL.md                          # Main skill instructions (dual theme)
├── README.md                         # This file
├── icons/                            # 304 official AWS service icons (SVG; incl. 56 AgentCore variants)
├── references/
│   ├── aws-theme.md                  # Dark theme: colors, fonts, JS constants
│   ├── light-theme.md                # Light theme: colors, patterns, JS constants
│   ├── slide-patterns.md             # 19+ layout patterns with PptxGenJS code
│   ├── pptxgenjs.md                  # PptxGenJS creation guide
│   ├── editing.md                    # Existing PPTX editing workflow
│   ├── animations.md                 # OOXML animation primitives
│   ├── design-spec-template.md       # Pre-build design spec template + approval flow
│   ├── pptx-overlay.md               # Overlay workflow for existing decks
│   └── image-generation-integration.md  # sd35l / nova2-omni (application/skills)
└── scripts/
    ├── create_aws_slide.py           # Background/SVG/logo asset generator
    ├── apply_animations.py           # Inject OOXML animations from JSON
    ├── qa_validate.py                # Programmatic QA (bounds, fonts, shapes)
    ├── render_design_preview.py      # Design spec → HTML preview (wireframes + palette)
    ├── thumbnail.py                  # Thumbnail grid for visual overview
    ├── clean.py                      # Clean PPTX XML
    ├── add_slide.py                  # Add slides to existing PPTX
    └── office/
        ├── soffice.py                # PPTX -> PDF conversion (LibreOffice)
        ├── unpack.py                 # Unpack PPTX to XML
        ├── pack.py                   # Repack XML to PPTX
        ├── helpers/                  # merge_runs, simplify_redlines
        ├── validators/               # PPTX/DOCX schema validators
        └── schemas/                  # ISO/IEC 29500 XSD schemas
```

## Dependencies

| Package | Type | Purpose |
|---------|------|---------|
| `pptxgenjs` | npm | PPTX creation from scratch |
| `sharp` | npm | SVG to PNG conversion (gradient cards, blobs) |
| `Pillow` | pip | Background gradient image generation |
| `python-pptx` | pip | PPTX reading, editing, and animation injection |
| `cairosvg` | pip | SVG to PNG conversion |
| `markitdown[pptx]` | pip | Text extraction from PPTX |
| `pdftoppm` (poppler) | system | PDF to slide images (QA) |
| `soffice` (LibreOffice) | system | PPTX to PDF conversion |

## Design Spec Workflow

For 3+ slide decks, MySlide produces a **markdown design spec** and (for 8+ slides)
an **HTML wireframe preview** before any PptxGenJS code is written. This catches
structural rework — wrong slide order, monotonous layouts, missing diagrams — at
seconds-to-fix stage rather than after the build.

```bash
# 1. Agent writes design-specs/<deck-name>.md (slide table + theme + open questions)
# 2. Render an HTML preview for visual review
python3 scripts/render_design_preview.py design-specs/<deck-name>.md
# Opens in browser: theme palette chips + per-slide wireframe thumbnails.
# Variety warnings (3-streak layouts, no-diagram decks) appear at the top.
```

The user reviews and says "go" / "승인" / "OK" before the agent moves to
PptxGenJS generation. See `references/design-spec-template.md` for the full
template and gate rules (1-2 slides skip the gate; "design first" / "디자인 먼저"
always engages it).

## Asset Generation

```bash
# Generate all assets at once ({workspace} = repo root containing application/)
python3 scripts/create_aws_slide.py full-setup --output-dir {workspace}/artifacts/myslide-assets/

# Individual commands
python3 scripts/create_aws_slide.py backgrounds --output-dir {workspace}/artifacts/myslide-assets/
python3 scripts/create_aws_slide.py svg-diagram --elements "VPC,Lambda,S3,Bedrock" --output {workspace}/artifacts/myslide-assets/arch.png
python3 scripts/create_aws_slide.py aws-logo --output {workspace}/artifacts/myslide-assets/aws-logo.png
```

## QA Workflow

```bash
# Phase 1: Programmatic (fast, catches hidden issues)
python3 scripts/qa_validate.py output.pptx

# Phase 2: Visual (delegate to kiro or subagent)
# Convert to images, then inspect alignment, colors, readability
```

## Version

- **v1.1.0** - Add Light theme (L100/field enablement), cross-skill integration, animations
- **v1.0.0** - Initial release with AWS reInvent 2023 dark design system
- Author: Jesam Kim
- License: MIT
