# AWS Light Theme Design System (L100/Field Enablement Style)

Based on analysis of AWS internal L100 training decks (e.g., "Claude Code on Bedrock").
This theme is the standard for AWS field enablement, customer-facing L100/L200 presentations,
and internal training materials. It contrasts with the dark reInvent theme by using white
backgrounds with soft gradient accents.

## When to Use This Theme

| Context | Theme |
|---------|-------|
| AWS reInvent, Summit keynotes | Dark (reInvent 2023/2025) |
| **L100/L200 field enablement** | **Light (this theme)** |
| **Customer-facing training** | **Light** |
| **Internal AWS workshops** | **Light** |
| **Sales enablement decks** | **Light** |
| Technical deep-dives, demos | Either (user preference) |
| Executive briefings | Either |

**Trigger phrases**: "L100", "L200", "field enablement", "training deck", "white background",
"light theme", "밝은 테마", "흰 배경", "교육 자료", "customer-facing presentation"

---

## Color Palette

### Core Colors (5-color discipline)

| Role | HEX | RGB | Usage |
|------|-----|-----|-------|
| **Background** | `#FFFFFF` | 255,255,255 | Slide background (pure white) |
| **Primary Text** | `#1A1A1A` | 26,26,26 | Headings, body text |
| **Sky Blue Accent** | `#4FC3F7` | 79,195,247 | Table headers, bullet points, links |
| **Card Background** | `#F5F0EB` | 245,240,235 | Cream/beige card fills |
| **Secondary Text** | `#666666` | 102,102,102 | Captions, descriptions |

### Extended Accent Palette (use sparingly for specific contexts)

| HEX | Name | Usage |
|-----|------|-------|
| `#C96842` | Terracotta/Coral | Key stat emphasis, CTA highlights, warm illustrations |
| `#E07A5F` | Light Coral | Chart bars, secondary warm accent |
| `#6B46C1` | Purple | Architecture labels, step badges, container borders |
| `#2196F3` | Blue | Data emphasis, "leader" callouts, hyperlinks |
| `#FF9900` | AWS Orange | "AWS Internal" label badge, numbered step badges |
| `#333333` | Dark Charcoal | Title text when extra contrast needed |
| `#F5F5F5` | Light Gray | Alternate card/section backgrounds |
| `#F8F7FA` | Lavender Tint | Subtle alternate background for data slides |
| `#C8B8A0` | Warm Tan | Feature badge/pill backgrounds |

### Semantic Color Coding

| Purpose | Color | Example |
|---------|-------|---------|
| Do's / Positive | `#4CAF50` (Green) | Do's column header, success indicators |
| Don'ts / Negative | `#F44336` (Red) | Don'ts column header, warning indicators |
| Alert/Important | `#00FF00` (Bright Green) | Critical message banners |
| AWS Internal | `#FF9900` (AWS Orange) | Top-right "AWS Internal" badge |

---

## Section Divider Gradient Blobs

Section dividers use **soft, organic gradient blobs** (not solid fills) positioned
at corners of the slide. Different sections use different color families to signal
topic transitions.

### Gradient Blob Families

| Family | Colors | Position | Used For |
|--------|--------|----------|----------|
| **Warm (Pink-Magenta-Orange)** | Pink → Magenta → Orange | Right side, diagonal | Product/feature sections |
| **Cool (Purple-Cyan-Lavender)** | Lavender → Purple → Cyan/Turquoise | Right-top to center | Technical/architecture sections |
| **Mixed (Purple-Green-Blue)** | Purple → Teal → Sky Blue | Right-top to bottom | Solution/guidance sections |
| **Peach (Soft Orange)** | Soft peach → Light orange | Bottom-left corner | Content backgrounds (subtle) |

### SVG Implementation for Gradient Blobs

Generate soft gradient blobs as SVG, convert to PNG, and embed as slide background:

```javascript
// Warm gradient blob (pink-magenta-orange) for section dividers
function createWarmGradientBlob(slideW = 13.33, slideH = 7.5) {
  const pxW = Math.round(slideW * 96);
  const pxH = Math.round(slideH * 96);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${pxW}" height="${pxH}">
    <defs>
      <radialGradient id="blob1" cx="85%" cy="35%" r="50%">
        <stop offset="0%" stop-color="#FF6B9D" stop-opacity="0.6"/>
        <stop offset="40%" stop-color="#C850C0" stop-opacity="0.4"/>
        <stop offset="70%" stop-color="#FF9A5C" stop-opacity="0.2"/>
        <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <rect width="${pxW}" height="${pxH}" fill="#FFFFFF"/>
    <rect width="${pxW}" height="${pxH}" fill="url(#blob1)"/>
  </svg>`;
}

// Cool gradient blob (lavender-purple-cyan) for section dividers
function createCoolGradientBlob(slideW = 13.33, slideH = 7.5) {
  const pxW = Math.round(slideW * 96);
  const pxH = Math.round(slideH * 96);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${pxW}" height="${pxH}">
    <defs>
      <radialGradient id="blob2" cx="80%" cy="30%" r="55%">
        <stop offset="0%" stop-color="#B388FF" stop-opacity="0.5"/>
        <stop offset="40%" stop-color="#7C4DFF" stop-opacity="0.3"/>
        <stop offset="70%" stop-color="#80DEEA" stop-opacity="0.2"/>
        <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <rect width="${pxW}" height="${pxH}" fill="#FFFFFF"/>
    <rect width="${pxW}" height="${pxH}" fill="url(#blob2)"/>
  </svg>`;
}
```

---

## Typography

### Font Stack (Same as Dark Theme)

| Weight | Font Name | Fallback |
|--------|-----------|----------|
| **Display Light** | Amazon Ember Display Light | Calibri Light |
| **Bold** | Amazon Ember Display Bold | Arial Bold |
| **Regular** | Amazon Ember | Calibri |

### Size Scale (Light Theme)

Light theme uses **thinner font weights** for titles (Light instead of Heavy):

| Element | Size (pt) | Weight | Color |
|---------|-----------|--------|-------|
| Section divider title | 48-54 | **Light** | `#1A1A1A` |
| Slide title | 32-40 | Regular | `#1A1A1A` |
| Subtitle / keyword emphasis | 20-28 | Bold | `#1A1A1A` |
| Category label (ALL CAPS) | 14-16 | Bold + letter-spacing | `#6B46C1` (Purple) |
| Body text | **15-16** | Regular | `#333333` |
| Bullet items | **15-16** | Regular | `#333333` |
| Table cell text | **15-16** | Regular | `#333333` |
| Key stat / hero number | 36-48 | Bold | `#C96842` (Coral) or `#2196F3` (Blue) |
| Hyperlinks | 14-16 | Regular + underline | `#2196F3` (Blue) |
| Italic callout | 14-16 | Italic | `#666666` |
| Footer / copyright | 8 | Regular | `#999999` |

**Critical**: Same as dark theme, body text must NEVER go below 15pt.

---

## Layout Patterns (Light Theme Specific)

### 1. Title Slide

Left-aligned title with 3D geometric decoration on right side.
- Title: Large bold, dark text, left-center area
- Subtitle: Light italic below title
- Partner logos: top-left — **only if the presentation involves a specific partner.
  Do NOT add partner logos (e.g., "aws + Anthropic") by default.**
- AWS logo: bottom-right
- Background: Lavender-purple-cyan gradient blobs on right half
- 3D geometric shapes (cubes, hexagons) with cyan/coral/lavender outlines

### 2. Section Divider

Minimal text-only with gradient blob accent:
- Large title: left-bottom, ~48pt Light weight
- Background: White + gradient blob (varies by section, see Gradient Blob Families)
- No content, no icons
- Footer: AWS logo bottom-left, copyright center, page number bottom-right

### 3. Agenda Slide

Clean numbered list with left accent bar:
- Left edge: Thin sky blue vertical accent bar (~8px wide, `#4FC3F7`)
- Title: "Agenda" top-left, ~36pt
- Items: Numbered list, ~20pt, regular weight
- Background: Pure white

### 4. Data + Citation (2-Column)

Left text/quote + right data visualization:
- Left: Title with blue keyword highlight, italic citation below
- Right: Horizontal bar chart on cream/beige card background
- Key stat in blue bold for emphasis
- Company logos next to data points
- Background: Light gray (`#F5F5F5`)

### 5. Benchmark Chart

Left description + right vertical bar chart:
- Multi-color coded bars (coral, olive, steel blue, warm gray)
- Semi-transparent vs opaque bars for variant comparison
- Clean axis labels, legend below

### 6. Three-Column Product Cards

Top title + 3 equal-width cards:
- Each card: Product screenshot + title + description
- Card background: cream/beige (`#F5F0EB`)
- "Focus" card highlighted with **orange dashed border** (`#FF9900`, dashed)
- Orange italic label below focus card

### 7. Feature List + Screenshot (2-Column)

Left: Feature labels in **warm tan pill badges** (`#C8B8A0` background) + descriptions
Right: Product terminal/IDE screenshot (dark theme captured UI)
- Pill badges: rounded rectangle, tan fill, dark text
- Background: Lavender tint (`#F8F7FA`)
- Bottom: Coral/pink accent description text

### 8. Full-Color Background Slide

Entire slide uses a single bold color:
- Background: Solid terracotta/coral (`#C96842`)
- All text: White
- Screenshot: Right side with product UI
- Use sparingly: maximum 1 per deck for visual rhythm break

### 9. Key Points Grid (2x3 or 2x4)

Upper title + grid of key points:
- Each point: **Purple ALL-CAPS label** (letter-spacing wide) + dark description text
- 2x3 or 2x4 grid with generous spacing
- Thin horizontal dividers between rows (optional)
- Background: White with subtle peach gradient bottom-left

### 10. Step Guide with Screenshots

Numbered steps with purple circle badges:
- Purple circle badges (`#6B46C1`) with white numbers (1, 2, 3...)
- Purple connecting arrows between steps
- Lavender background boxes for service icons
- Dark terminal screenshot for application steps
- Purple label strips for category identification

### 11. Table Slide

Clean data table with colored header:
- Header row: Sky blue background (`#4FC3F7`) + white text
- Data rows: White background + thin gray dividers
- No alternating row colors
- Left-aligned text in cells

### 12. Bullet List + QR Code (2-Column)

Left: Structured bullet list with bold keyword highlights
Right: Large QR code image + sky blue link text below
- Background: White
- Hyperlinks: Sky blue, underlined

### 13. Customer Case Study (Complex)

Multi-section with logo, challenge/solution/result:
- Top: Orange-yellow gradient banner label
- Left: Customer logo + company description
- Right: Challenge/Solution/Result sections with **purple labels**
- Bottom: Gray band with **pill-shaped category tags** (purple border)

### 14. Do's vs Don'ts Comparison

Two-column comparison table:
- Left header: Green checkmark icon + "Do's" on light green background
- Right header: Red X icon + "Don'ts" on light pink background
- Body: Bullet lists on cream/yellow background
- Clean separation between columns

### 15. Call to Action (CTA) Slide

Product showcase + numbered action items:
- Left: Terminal/product screenshot (dark background capture)
- Right: Numbered items with **orange circle badges** (`#FF9900`) containing white numbers
- Each item on light gray rounded card/band
- Clear, actionable next steps

### 16. Architecture Diagram (Light Background)

AWS architecture with light background:
- White background + subtle peach gradient accent (top-right)
- **Purple container borders** (dashed/solid) for logical grouping
- **Purple numbered circle badges** for step sequence
- AWS service icons in official colors
- Black arrows for flow connections
- Left: numbered description list, Right: diagram

### 17. Dashboard Screenshot Slide

Real product UI evidence:
- Left: 4 key features as bold keyword + description pairs
- Right: Full dashboard screenshot with colored stat cards (green, blue, orange, purple)
- Screenshot shows actual CloudWatch/Solutions Library UI

### 18. Thank You / Closing Slide

Full gradient background with minimal text:
- Background: Full lavender → purple → cyan/turquoise gradient
- "Thank you!" text: Large Light weight, left-center
- AWS logo: Large, bottom-right, dark color
- Copyright: Bottom-left

---

## PptxGenJS Constants (Light Theme)

```javascript
const AWS_LIGHT_THEME = {
  layout: "LAYOUT_WIDE",  // 13.33" x 7.50"

  colors: {
    bgBase: "FFFFFF",
    primaryText: "1A1A1A",
    secondaryText: "666666",
    bodyText: "333333",
    skyBlue: "4FC3F7",
    blue: "2196F3",
    cardBg: "F5F0EB",
    lightGray: "F5F5F5",
    lavenderTint: "F8F7FA",
    coral: "C96842",
    lightCoral: "E07A5F",
    purple: "6B46C1",
    awsOrange: "FF9900",
    warmTan: "C8B8A0",
    footerGray: "999999",
    dividerGray: "E0E0E0",
    // Semantic
    doGreen: "4CAF50",
    dontRed: "F44336",
    alertGreen: "00FF00",
    // Chart colors
    chartCoral: "E07A5F",
    chartOlive: "81B29A",
    chartBlue: "5B7DB1",
    chartGray: "C4B9A8",
  },

  fonts: {
    heading: "Amazon Ember Display",
    headingLight: "Amazon Ember Display Light",
    body: "Amazon Ember",
    fallbackHeading: "Calibri",
    fallbackBody: "Calibri",
    code: "Consolas",
  },

  positions: {
    title: { x: 0.5, y: 0.33, w: 12.33, h: 0.8 },
    contentArea: { x: 0.5, y: 1.4, w: 12.33, h: 5.2 },
    footer: { x: 0.47, y: 7.15 },
    copyright: { x: 1.3, y: 7.15 },
    pageNumber: { x: 12.5, y: 7.15 },
    awsInternalBadge: { x: 11.5, y: 0.15, w: 1.5, h: 0.35 },
  },

  // Standard slide footer
  addFooter: (slide, pageNum, pres) => {
    // AWS logo bottom-left
    slide.addImage({ path: 'icons/aws-logo-dark.svg', x: 0.47, y: 7.15, w: 0.7, h: 0.25 });
    // Copyright center
    slide.addText('2025, Amazon Web Services, Inc. or its affiliates. All rights reserved.', {
      x: 1.3, y: 7.15, w: 8, h: 0.25,
      fontSize: 8, color: '999999', fontFace: 'Amazon Ember',
    });
    // Page number right
    if (pageNum) {
      slide.addText(String(pageNum), {
        x: 12.5, y: 7.15, w: 0.5, h: 0.25,
        fontSize: 8, color: '999999', align: 'right',
      });
    }
  },
};
```

---

## Cross-Skill Integration

### svg-diagram Skill

Use `svg-diagram` for generating diagrams on light backgrounds. Adjust color settings:

```
When generating SVG diagrams for light-theme slides:
- Background: transparent (fill="none") or white
- Text color: #1A1A1A (dark) instead of white
- Container borders: #6B46C1 (purple) or #4FC3F7 (sky blue)
- Arrow color: #333333 (dark charcoal)
- Service icon labels: #333333
- Accent highlights: #C96842 (coral) or #2196F3 (blue)
```

Hub-spoke and architecture diagrams work the same way as dark theme, but with
inverted text colors and lighter container fills.

---

## AWS Internal Badge Pattern

**CONDITIONAL**: Only add this badge when the user explicitly states the presentation
is an AWS internal document. NEVER include by default. Ask if unsure.

Some internal slides include an "AWS Internal" badge in the top-right corner:

```javascript
// AWS Internal badge (top-right corner)
slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
  x: 11.5, y: 0.15, w: 1.5, h: 0.35,
  fill: { color: "FF9900" },
  rectRadius: 0.05,
});
slide.addText("AWS Internal", {
  x: 11.5, y: 0.15, w: 1.5, h: 0.35,
  fontSize: 10, bold: true, color: "FFFFFF",
  align: "center", valign: "middle",
  fontFace: "Amazon Ember",
});
```

---

## Pill-Shaped Category Tags

Used for categorization in customer case studies and feature labels:

```javascript
// Pill-shaped tag with purple border
function addPillTag(slide, text, x, y, w = null) {
  const tagW = w || (text.length * 0.12 + 0.4);
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w: tagW, h: 0.35,
    fill: { type: 'none' },
    line: { color: "6B46C1", width: 1 },
    rectRadius: 0.18,
  });
  slide.addText(text, {
    x, y, w: tagW, h: 0.35,
    fontSize: 10, color: "6B46C1",
    align: "center", valign: "middle",
    fontFace: "Amazon Ember",
  });
}

// Example: category tags row
addPillTag(slide, "FINANCIAL SERVICES", 0.5, 6.5);
addPillTag(slide, "STARTUP", 2.8, 6.5);
addPillTag(slide, "AMAZON BEDROCK", 4.3, 6.5);
```

---

## Feature Badge (Warm Tan Pill)

Used for labeling features/capabilities:

```javascript
// Feature badge with warm tan background
function addFeatureBadge(slide, text, x, y) {
  const badgeW = text.length * 0.11 + 0.5;
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w: badgeW, h: 0.4,
    fill: { color: "C8B8A0" },
    rectRadius: 0.2,
  });
  slide.addText(text, {
    x, y, w: badgeW, h: 0.4,
    fontSize: 12, bold: true, color: "1A1A1A",
    align: "center", valign: "middle",
  });
}
```

---

## Numbered Step Badges

Two styles of step number badges:

```javascript
// Purple step badge (for architecture/technical steps)
function addPurpleStepBadge(slide, number, x, y, size = 0.45) {
  slide.addShape(pres.shapes.OVAL, {
    x, y, w: size, h: size,
    fill: { color: "6B46C1" },
  });
  slide.addText(String(number), {
    x, y, w: size, h: size,
    fontSize: 16, bold: true, color: "FFFFFF",
    align: "center", valign: "middle",
  });
}

// Orange step badge (for action items / CTA)
function addOrangeStepBadge(slide, number, x, y, size = 0.45) {
  slide.addShape(pres.shapes.OVAL, {
    x, y, w: size, h: size,
    fill: { color: "FF9900" },
  });
  slide.addText(String(number), {
    x, y, w: size, h: size,
    fontSize: 16, bold: true, color: "FFFFFF",
    align: "center", valign: "middle",
  });
}
```

---

## Table Styling (Light Theme)

```javascript
// Light theme table with sky blue header
const tableRows = [
  // Header row
  [
    { text: "Column A", options: { bold: true, color: "FFFFFF", fill: { color: "4FC3F7" } } },
    { text: "Column B", options: { bold: true, color: "FFFFFF", fill: { color: "4FC3F7" } } },
    { text: "Column C", options: { bold: true, color: "FFFFFF", fill: { color: "4FC3F7" } } },
  ],
  // Data rows
  [
    { text: "Value 1", options: { color: "333333" } },
    { text: "Value 2", options: { color: "333333" } },
    { text: "Value 3", options: { color: "333333" } },
  ],
];

slide.addTable(tableRows, {
  x: 1.0, y: 2.0, w: 11.33,
  fontSize: 15,
  fontFace: "Amazon Ember",
  border: { type: "solid", pt: 0.5, color: "E0E0E0" },
  colW: [3.77, 3.77, 3.79],
  rowH: [0.5, 0.45],
});
```

---

## Do's vs Don'ts Comparison Pattern

```javascript
// Do's header (green)
slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
  x: 0.5, y: 1.5, w: 5.9, h: 0.6,
  fill: { color: "E8F5E9" },  // Light green
  rectRadius: 0.08,
});
slide.addText([
  { text: "\u2713 ", options: { color: "4CAF50", fontSize: 20, bold: true } },
  { text: "Do's", options: { color: "333333", fontSize: 20, bold: true } },
], { x: 0.5, y: 1.5, w: 5.9, h: 0.6, valign: "middle" });

// Don'ts header (red)
slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
  x: 6.9, y: 1.5, w: 5.9, h: 0.6,
  fill: { color: "FFEBEE" },  // Light red
  rectRadius: 0.08,
});
slide.addText([
  { text: "\u2717 ", options: { color: "F44336", fontSize: 20, bold: true } },
  { text: "Don'ts", options: { color: "333333", fontSize: 20, bold: true } },
], { x: 6.9, y: 1.5, w: 5.9, h: 0.6, valign: "middle" });

// Content areas (cream background)
// Do's content
slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
  x: 0.5, y: 2.2, w: 5.9, h: 4.3,
  fill: { color: "FFFDE7" },  // Light cream
  rectRadius: 0.08,
});
// Don'ts content
slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
  x: 6.9, y: 2.2, w: 5.9, h: 4.3,
  fill: { color: "FFFDE7" },
  rectRadius: 0.08,
});
```

---

## Visual Rhythm Strategy

The L100 deck alternates between high-density and low-density slides to maintain engagement:

```
Section Divider (low)  →  2-Column Content (medium)  →  Table/Data (high)
    →  Key Points Grid (medium)  →  Screenshot (medium)  →  Section Divider (low)
```

**Rules for visual rhythm:**
1. Never place 3+ text-heavy slides in a row — insert a section divider or screenshot slide
2. After a data-dense slide (table, chart), follow with a simpler layout
3. Use 1 full-color background slide per deck maximum (for visual surprise)
4. Alternate gradient blob colors between sections for clear navigation
5. Mix 2-column and grid layouts — avoid repeating the same structure 3+ times
