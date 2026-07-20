## HARD REJECT — if ANY of these appear, the design has failed:

### Placeholder Content (INSTANT FAIL — check this FIRST)
- Any visible text like "placeholder-1", "placeholder-thumbnail", "Lorem ipsum", "Image goes here"
- Empty boxes where images should be, showing no styled visual treatment
- Raw data keys or variable names rendered as user-facing text
- "Coming soon..." or "Under construction" stub pages with no real content

### Color
- Warm cream (#F4F1EA) + terracotta (#D97757) — the 2024 AI default palette
- Pure black (#000 or near-black #080808-#111111) background + single neon accent (lime, cyan, hot pink) — the "vibe-coded dark mode" look
- Rainbow gradients or more than 3 colors used prominently
- Using opacity/transparency as a substitute for actual color choices
- Hardcoded rgba(0,0,0,...) colors that break when the background color changes

### Layout & Density (Figma/shadcn Standard)
- Centered hero with "big number + small label + gradient blob" when the content doesn't call for it
- Numbered section markers (01/ 02/ 03/) as decoration on non-sequential content
- Newspaper-column layout when the content isn't editorial
- Everything centered with no left-alignment anywhere
- Cards/grid items with inconsistent sizes or random misalignment
- Content overflowing its container
- "Mushed" narrow layouts: Cards or main content squeezed into a tiny center column (e.g., max-width: 600px for a grid of cards). Grids MUST use standard wide containers (e.g., max-width: 1200px) so cards breathe.
- Low-density layouts: Pages with massive empty gaps and very little content, looking like a "child's mess" rather than a professional app. We expect high-density, Shadcn-level UI polish.

### Typography
- Default system fonts (no Google Fonts loaded)
- More than 2 font families (3 is acceptable only if the third is a mono font for code/metadata)
- Display text and body text using the same weight (headings MUST be visually heavier)
- Inconsistent heading sizes (h2 larger than h1, etc.)

### Animation
- More than 3 distinct animation types on one page
- Animations longer than 500ms
- Parallax scrolling when the content doesn't benefit from depth
- Scroll-triggered animations on every single element
- "Floating" decorative shapes/blobs

### Components & Navigation
- Bootstrap or Tailwind with zero customization (visible defaults)
- Unstyled focus states (browser default blue outline)
- Buttons with no hover/active state transitions
- Cards that all look identical with no visual hierarchy
- Generic placeholder images (gradient squares only count if they look intentional and styled)
- Browser chrome mockup dots using gray circles instead of realistic macOS colors
- Barebones, simple navbars (e.g., just a logo and 3 links pushed to the left). A Shadcn-level navbar should have balanced alignment (logo left, links center/right, and a right-aligned CTA or utility like dark-mode/social icons), with proper padding, borders, and sticky behavior if appropriate.

## PASS CRITERIA — the design must show:
- A specific point of view tied to what the app actually IS
- Type pairing that looks intentional (not just "whatever sans-serif")
- Consistent spacing rhythm (eyeball test: could you overlay a 8px grid and it aligns?)
- Color restraint (2-3 colors max, used with purpose)
- Motion only where it serves UX (hover feedback, page transitions, loading states)
- No visible placeholder content of any kind
- Images/thumbnails that look intentional and styled
- The whole thing reads like a real product, not a demo/template
