# Content Density & Structural Specification

> This document defines the ABSOLUTE MINIMUM structural density required for a production-grade UI. AI models default to lazy, abstract vibes (e.g. "a gray card with a shape"). This spec bans abstraction and forces concrete data structures.

## 1. Card & Component Density Floor
A "card" is never just a title and an empty box. EVERY standard data card MUST contain at least THREE of the following distinct sub-elements:
- A quantitative badge or status pill (e.g., "Active", "+14%", "3 items")
- A micro-data visualization (e.g., a 5-bar sparkline, a radial progress ring, a segmented progress bar)
- An interactive utility (e.g., a "More options" ellipsis, a "View details" ghost button)
- Structured metadata rows (e.g., an icon + label + value layout)
- A highly-styled visual thumbnail (NOT a placeholder or single floating shape, see section 3)

**Failure Condition**: A single shape sitting in a large empty container is an automatic rejection.

## 2. Section Density Floor
A page section is never just a massive H2 and a single paragraph. Every major section MUST contain at least TWO of the following structural blocks:
- A descriptive header block (Header + Subhead + Action CTA)
- A data grid or card layout (meeting the Card Density Floor)
- A structured list, timeline, or steps breakdown
- An interactive component (tabs, accordion, filter bar)

## 3. The "Visual Thumbnail" Specification
When an instruction calls for a "styled visual treatment" or "thumbnail", you must NEVER output a generic abstract shape or a flat gradient. 

You must compose a semantic, pseudo-realistic UI graphic using CSS/SVG. Examples of acceptable density:
- **Analytics/Data**: A mini line chart with an x-axis, y-axis grid lines, a shaded area under the curve, and a tooltip dot.
- **Node/Graph**: 3-4 connected nodes with actual labels ("API", "Database", "Client"), dashed connector lines, and subtle pulse animations.
- **System/Architecture**: A stacked block diagram representing layers (e.g., a base layer, a middleware block, and top-level apps).

**Failure Condition**: A single `<div className="w-16 h-16 bg-blue-500 rounded-full" />` floating in empty space is an automatic rejection.

## 4. Typography Density
Do not use a single font-weight across an entire headline or sentence. 
- Mix weights and styles to create emphasis (e.g., "The future of **generative** *UI architecture*").
- Pair display fonts (headings) with a utilitarian mono font (for metadata, numbers, and tags) and a readable sans-serif (for body).

## 5. Motion Classification
Do not rely solely on "hover" animations. Every page MUST feature:
- **Ambient Motion**: At least one continuously running, subtle animation that exists BEFORE the user interacts. Examples: A slow gradient mesh rotation, a very slow translating background grid, a pulse on an active status dot, or a slow marquee scroll.
- **Reactive Motion**: Snappy, physics-based (spring) transitions on hover, click, and focus.
