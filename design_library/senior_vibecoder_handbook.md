# The Senior Vibe Coder Handbook
## A Complete Reference for AI Agents Building Production-Quality Web Applications

> This handbook is the accumulated wisdom of what separates good UI from garbage. Every AI model in this pipeline — architect, builder, critic — should internalize these principles. This is not theory. These are the rules that, when followed, produce apps that look like a real team built them, and when broken, produce apps that scream "AI made this."

---

## Part 1: The Eye Test — What Humans See Instantly

### 1.1 The 3-Second Rule
When a human opens your app, they form an opinion in 3 seconds. In those 3 seconds, they notice:
1. **Is the background a real color or a lazy default?** Pure black (#000) and warm cream (#F4F1EA) are the two laziest choices. Pick something with character.
2. **Do the colors work together?** A random accent color slapped onto a neutral background looks AI-generated. Colors should feel intentional — as if a designer chose them together.
3. **Is there visual hierarchy?** If everything is the same size and weight, the page looks flat. Headings should be OBVIOUSLY bigger. Metadata should be OBVIOUSLY quieter.

### 1.2 The Placeholder Test (Instant Fail)
A production app NEVER shows:
- The word "placeholder" anywhere visible
- "Lorem ipsum" as real content
- "Image goes here" or empty gray boxes
- "Coming soon..." stub pages
- Variable names or data keys rendered as text (e.g., "thumbnail-1")
- Generic stock photo URLs or broken image icons

If ANY of these are visible, the app has failed. Period. No exceptions.

### 1.3 The Squint Test
Squint at your app (or blur the screenshot). You should still be able to identify:
- Where the navigation is
- What the main content area is
- Where the primary CTA (call-to-action) is
- The visual hierarchy (what's most important → least important)

If everything blurs into a flat, same-weight mess, the hierarchy has failed.

---

## Part 2: Color — The Single Biggest Tell

### 2.1 Banned Palettes (AI Dead Giveaways)
These are so overused by AI coding agents that they're now recognized as "vibe-coded" on sight:

| Banned Pattern | Why It's Bad |
|---|---|
| Warm cream (#F4F1EA) + terracotta (#D97757) | The 2024 AI default. Every single AI-coded portfolio uses this. |
| Pure black (#000-#111) + neon green/cyan/pink | The "hacker/dark mode" AI default. Boring and overdone. |
| Rainbow gradients | Screams "AI added color because it could." |
| All-gray with one random blue accent | The "I didn't actually design anything" look. |

### 2.2 How to Choose Real Colors
**Start with the background.** Not pure white (#FFF) and not pure black (#000). Pick something with warmth or coolness:
- Warm stone: #FAF8F5 (warm but NOT cream)
- Cool slate: #F8F9FB (cool but NOT clinical)  
- Deep navy: #0A1628 (dark but NOT black)
- Warm charcoal: #1C1917 (dark but NOT black)

**Pick ONE accent color with intention.** The accent should:
- Have enough saturation to stand out against the background
- NOT be a primary color (pure red, blue, green). Use nuanced versions.
- Appear in exactly 3 places: links/CTAs, active/selected states, and one decorative element

**Good accent examples:**
- Terracotta (if the background ISN'T cream): #C05533
- Indigo: #4F46E5
- Teal: #0D9488
- Amber: #D97706
- Rose: #E11D48

### 2.3 The Token Rule
NEVER use hardcoded colors in CSS. Every color must be a CSS custom property:
```css
/* ❌ BAD — breaks when theme changes */
border: 1px solid rgba(0, 0, 0, 0.1);
background: rgba(0, 0, 0, 0.02);

/* ✅ GOOD — works with any background */
border: 1px solid var(--color-border);
background: var(--color-hover-bg);
```

---

## Part 3: Typography — The Craft Signal

### 3.1 The Weight Hierarchy Rule
This is non-negotiable:
- **Headings (h1–h3):** Font-weight 600 or 700. NEVER 400. A heading at 400 weight is indistinguishable from body text.
- **Body text:** Font-weight 400 or 500. NEVER bold.
- **Metadata/labels:** Font-weight 400–500, smaller size, lighter color.

If your h1 and body paragraph look the same weight, you've failed.

### 3.2 The Type Scale Rule
Use a consistent scale with clear steps:
- If your body text is 16px (1rem), your h1 should be AT LEAST 2x larger (32px+).
- Never use adjacent sizes that are too close (e.g., 14px and 15px are indistinguishable).
- Display text (2xl+) should have tighter line-height (1.1) and negative letter-spacing (-0.02em).

### 3.3 The Mono Font Rule
Monospace fonts are ONLY for:
- Code snippets
- Metadata labels (dates, tags, version numbers)
- Terminal/CLI output

NEVER use mono for headings, body text, or navigation.

### 3.4 Font Loading
Always load custom fonts. Default system fonts are an instant tell:
```css
/* ❌ Default system font stack = lazy */
font-family: system-ui, sans-serif;

/* ✅ Intentional font choice */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
font-family: 'Inter', sans-serif;
```

---

## Part 4: Layout — Structure Creates Meaning

### 4.1 The Max-Width Rule & Layout Width
Content containers MUST have a max-width, but they MUST NOT be artificially squeezed ("mushed"). Full-width text is unreadable, but grids need space:
- **Reading text:** Max 65ch (about 600px - 800px)
- **Card grids:** Max 1000px - 1200px. NEVER cram a grid of cards into a 600px container; it looks like a child's mess.
- **Full-bleed images:** Can go wider, but still need margin from viewport edges

### 4.2 The Spacing Rhythm Rule
Use a consistent spacing scale (4px or 8px base). Common scale:
```
4, 8, 12, 16, 24, 32, 48, 64, 96, 128
```
NEVER use arbitrary values like 13px, 37px, or 51px. If your spacing doesn't come from a scale, the rhythm is broken and it looks amateur.

### 4.3 The Alignment Rule
- Content should be left-aligned by default (this is how people read)
- Centered content is ONLY for hero sections, empty states, and short UI elements
- If EVERYTHING is centered, the layout looks like a PowerPoint slide
- Right-aligned content is ONLY for numbers in tables and metadata in list items

### 4.4 The Grid Rule for Cards
- All cards in a row must be the same height (use CSS Grid with `grid-template-rows: 1fr` or flexbox `align-items: stretch`)
- Card spacing must be consistent (use `gap`, not margins)
- If cards have images, all images must have the same aspect ratio
- If a grid has 3+ items, it should be responsive (1 column on mobile, 2–3 on desktop)

### 4.5 Visual Separation
Sections need visual boundaries. Options (pick ONE per app, be consistent):
- Subtle background color changes between sections
- Thin divider lines (1px, using `var(--color-border)`)
- Generous spacing (2–3x normal spacing between sections)

NEVER use thick borders, heavy drop shadows, or colored backgrounds for every section.

---

## Part 5: Components — The Devil in the Details

### 5.1 Interactive States (Required for Every Clickable Element)
Every button, link, and card MUST have:
- **Default state:** Clear visual distinction from non-interactive text
- **Hover state:** Subtle change (color shift, underline appear, slight lift). NOT dramatic (no 3D rotations, no color inversions)
- **Focus state:** Visible outline or ring (for keyboard users). NEVER remove the focus outline without adding a replacement.
- **Active/pressed state:** Slight scale-down (transform: scale(0.98)) or color darken

### 5.2 Browser Chrome Mockups
When showing a "browser window" mockup for project screenshots:
- Use realistic macOS dots: red (#FF6058), yellow (#FFC02E), green (#27CA40)
- NOT gray circles (this looks unfinished)
- The browser bar should have a subtle background (#F7F7F7 light, #2A2A2A dark)
- Content area should show a styled visual treatment — NEVER raw placeholder text

### 5.3 Empty States and Placeholders
Instead of showing "placeholder-1" text, use:
- **CSS gradients** with nth-child selectors for variety per card
- **SVG patterns** (dots, lines, geometric shapes)
- **Generated images** using the image generation tool
- **Styled abstract shapes** that suggest the content type

### 5.4 Forms and Inputs
- Inputs must have visible borders (not just a bottom line on light backgrounds — those disappear)
- Labels should be outside/above the input, not inside as placeholder text (placeholder text disappears when you type)
- Error states should use red/pink tones with clear error messages
- Submit buttons should be visually prominent (filled, not outlined)

### 5.5 Navigation / Navbars
- A premium Shadcn-level navbar is NEVER just a logo and 3 links pushed to the left.
- Always include balanced layout: Logo on the far left, Navigation links in the center (or left-aligned next to logo), and Actions/Utilities (like a CTA button, dark mode toggle, search icon, or social links) on the far right.
- Ensure the navbar spans the full width of the layout container and has adequate padding (e.g., `py-4`) and possibly a subtle bottom border or shadow.

---

## Part 6: Responsive Design — Not Optional

### 6.1 Breakpoints
Design for 3 sizes:
- **Mobile:** < 768px (1 column, stacked layout)
- **Tablet:** 768px–1024px (2 columns, adapted grid)
- **Desktop:** > 1024px (full layout)

### 6.2 Mobile-First Rules
- Navigation should collapse into a hamburger menu or minimal nav on mobile
- Cards should stack into 1 column
- Text size should NOT shrink below 14px
- Touch targets should be at least 44x44px
- Horizontal scrolling is NEVER acceptable

---

## Part 7: Backend & Architecture Decisions

### 7.1 When to Use What
| Scenario | Choice |
|---|---|
| Simple landing page / portfolio | Vanilla HTML + CSS + JS, or Vite + React |
| Multi-page app with routing | React + React Router, or Next.js |
| App with real data needs | Next.js with API routes, or separate Express backend |
| Complex state management | React Context for simple, Zustand for moderate, Redux for complex |

### 7.2 Project Structure
Keep it clean and predictable:
```
src/
  components/       # Reusable UI components (grouped by feature)
    layout/          # Header, Footer, PageContainer
    home/            # Home-page-specific components
    work/            # Work-page-specific components
  pages/             # Page-level components (one per route)
  styles/            # CSS files (one per component or feature area)
  data/              # Mock data, constants
  utils/             # Helper functions
  hooks/             # Custom React hooks (if applicable)
```

### 7.3 CSS Strategy
- Use CSS custom properties (variables) for all colors, spacing, and fonts
- Use ONE approach: either CSS Modules, plain CSS with BEM-style naming, or Tailwind. Don't mix.
- NEVER use inline styles for layout or colors (only for truly dynamic values like calculated positions)
- Keep specificity low: use class selectors, not IDs or element selectors

### 7.4 Data Architecture
- Mock data should be realistic, not "Test Item 1", "Test Item 2"
- Keep mock data in a dedicated file (e.g., `data/mockProjects.ts`)
- Type your data with TypeScript interfaces
- If a component expects an image URL, the mock data should either reference a real image or the component should handle the "no image" case gracefully (styled fallback, NOT broken icon)

---

## Part 8: Common AI Failure Modes (Anti-Patterns)

### 8.1 The "Everything Centered" Disease
AI loves centering everything. Real apps use left-alignment for most content and centering only for heroes and empty states.

### 8.2 The "Palette Ping-Pong" 
When rejected for warm cream, AI panic-switches to pure black. When rejected for black, it switches back to cream. The fix: choose a SPECIFIC, nuanced palette (warm stone, cool slate, deep navy) that is NEITHER banned option.

### 8.3 The "Placeholder Leak"
AI code often renders data field values as visible text. If your data has `thumbnail: "placeholder-1"`, the component should NOT render the string "placeholder-1" — it should use CSS to create a visual treatment or conditionally hide the text.

### 8.4 The "Hardcoded Color" Trap
Using `rgba(0, 0, 0, 0.1)` for borders works on light backgrounds but creates invisible borders on dark backgrounds. ALWAYS use CSS variables so colors adapt to any theme.

### 8.5 The "Same Weight Everywhere" Problem
AI often uses font-weight 400 for everything — headings, body, labels. This makes the page look flat. Headings MUST be heavier (600+).

### 8.6 The "Motion Soup"
AI loves adding animations to everything. Real apps use motion sparingly:
- Hover state transitions: 150–200ms
- Page transitions: 200–300ms
- Loading animations: purposeful, not decorative
- NO scroll-triggered reveals on every element
- NO floating decorative shapes

---

## Part 9: The Checklist (Use Before Declaring "Done")

Before any step is "complete," verify:

- [ ] No visible placeholder text anywhere
- [ ] All images/thumbnails show styled visual content (not raw text)
- [ ] Colors use CSS variables, not hardcoded values
- [ ] Headings are visually heavier than body text
- [ ] Interactive elements have hover and focus states
- [ ] Layout is responsive at 768px and 1024px breakpoints
- [ ] Card grids have consistent sizing and spacing
- [ ] No TypeScript or compilation errors
- [ ] No console errors or routing warnings
- [ ] The app would not embarrass you if a hiring manager saw it
