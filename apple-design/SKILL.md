---
name: apple-design
description: Design system skill for apple. Activate when building UI components, pages, or any visual elements. Provides exact color tokens, typography scale, spacing grid, component patterns, and craft rules. Read references/DESIGN.md before writing any CSS or JSX.
---

# apple Design System

You are building UI for **apple**. Dark-themed, cool palette, sans-serif typography (SF Pro AR), compact density on a 4px grid, expressive motion.

## Visual Reference

**IMPORTANT**: Study ALL screenshots below before writing any UI. Match colors, typography, spacing, layout, and motion exactly as shown.

### Homepage

![apple Homepage](screenshots/homepage.png)

> Read `references/DESIGN.md` for full token details.

## Design Philosophy

- **Layered depth** — use shadow tokens to create a sense of physical layering. Each elevation level has a specific shadow.
- **Gradient accents** — gradients are used thoughtfully for emphasis, not decoration.
- **Type pairing** — SF Pro AR for body/UI text, SF Pro Text for headings/display. Never introduce a third typeface.
- **compact density** — 4px base grid. Every dimension is a multiple of 4.
- **cool palette** — the color temperature runs cool, matching the sans-serif typography.
- **Restrained accent** — `#0066cc` is the only pop of color. Used exclusively for CTAs, links, focus rings, and active states.
- **Expressive motion** — animations are an integral part of the experience. Use spring physics and layout animations.

## Color System

### Core Palette

| Role | Token | Hex | Use |
|------|-------|-----|-----|
| Background | `--background` | `#000000` | Page/app background |
| Surface | `--surface` | `#161617` | Cards, panels, modals |
| Text Primary | `--text-primary` | `#f4f8fb` | Headings, body text |
| Text Muted | `--text-muted` | `#e8e8ed` | Captions, placeholders |
| Accent | `--accent` | `#0066cc` | CTAs, links, focus rings |
| Border | `--border` | `#424245` | Dividers, card borders |

### Status Colors

| Status | Hex | Use |
|--------|-----|-----|
| Danger | `#b64400` | Errors, destructive actions |

### Extended Palette

- **sk-button-background:** `#0071e3`
- **r-globalnav-submenu-header-color:** `#86868b`
- **sk-blocklink-color:** `#2997ff`
- **sk-glyph-gray-secondary-alt:** `#d2d2d7` — Secondary text, placeholder text
- **sk-button-background-hover:** `#272729`
- **sk-dotnav-scrim-solid-iconcontrol-scrim-color-hover:** `#dfdfe3` — Modal/dialog backdrop overlay
- **sk-badge-text-color:** `#ff791b`
- **sk-badge-background:** `#f56300` — Warm accent — hover glow or decorative highlight

### CSS Variable Tokens

```css
--r-globalnav-background-opened: #fafafc;
--r-globalnav-background-opened-dark: #161617;
--r-globalnav-color-secondary: #333336;
--globalnav-background: none;
--r-globalnav-color-secondary: #E8E8ED;
--r-globalnav-color-secondary: #333336;
--globalnav-background: rgba(250,250,252,.92);
--globalnav-background: rgba(250,250,252,.8);
--globalnav-background: rgba(22,22,23,.88);
--globalnav-background: rgba(22,22,23,.8);
--globalnav-background: rgba(250,250,252,.92);
--globalnav-background: rgba(250,250,252,.8);
--r-globalnav-search-list-item-hover-background: rgb(245,245,247);
--r-globalnav-search-list-item-hover-background: rgb(29,29,31);
--r-globalnav-search-list-item-hover-background: rgb(245,245,247);
--globalmessage-segment-background: rgb(250,250,252);
--globalmessage-segment-scrim-background: rgba(0,0,0,.04);
--globalmessage-segment-border-color: rgba(0,0,0,.48);
--globalmessage-segment-background: rgb(22,22,23);
--globalmessage-segment-scrim-background: rgba(255,255,255,.08);
```

## Typography

### Font Stack

- **SF Pro AR** — Heading 1, Heading 2, Heading 3
- **SF Pro Text** — Body, Caption
- **SF Mono** — Code

### Type Scale

| Role | Family | Size | Weight |
|------|--------|------|--------|
| Heading 1 | SF Pro AR | 96px | 700 |
| Heading 2 | SF Pro AR | 89px | 700 |
| Heading 3 | SF Pro AR | 80px | 700 |
| Body | SF Pro Text | 17px | 400 |
| Caption | SF Pro Text | 12px | 400 |
| Code | SF Mono | 14px | 400 |

### Typography Rules

- Body/UI: **SF Pro AR**, Headings: **SF Pro Text** — these are the only display fonts
- Max 3-4 font sizes per screen
- Headings: weight 600-700, body: weight 400
- Use color and opacity for text hierarchy, not additional font sizes
- Line height: 1.5 for body, 1.2 for headings

## Spacing & Layout

### Base Grid: 4px

Every dimension (margin, padding, gap, width, height) must be a multiple of **4px**.

### Spacing Scale

`2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24` px

### Spacing as Meaning

| Spacing | Use |
|---------|-----|
| 4-8px | Tight: related items (icon + label, avatar + name) |
| 12-16px | Medium: between groups within a section |
| 24-32px | Wide: between distinct sections |
| 48px+ | Vast: major page section breaks |

### Border Radius

Scale: `.1764705882rem, .25rem, .5882352941rem, .75rem, 1px, 1.1764705882rem, 1.2px, 1.3em, 2rem, 2px, 3px, 4px, 5px, 6px, 8px, 10px, 12px, 13px, 17px, 18px, 19.5px, 20px, 21px, 27.5px, 28px, 30px, 32px, 35px, 99px, 999px, inherit, 100%, 100px, 109px, 129px, 980px`
Default: `17px`

### Container

Max-width: `1068px`, centered with auto margins.

### Breakpoints

| Name | Value |
|------|-------|
| xs | 320px |
| xs | 350px |
| xs | 360px |
| xs | 368px |
| xs | 375px |
| xs | 379px |
| xs | 393px |
| xs | 420px |
| xs | 433px |
| xs | 436px |
| xs | 460px |
| xs | 477px |
| xs | 478px |
| xs | 480px |
| sm | 550px |
| sm | 569px |
| sm | 605px |
| sm | 640px |
| md | 641px |
| md | 642px |
| md | 654px |
| md | 717px |
| md | 734px |
| md | 735px |
| md | 736px |
| md | 750px |
| md | 758px |
| md | 767px |
| md | 768px |
| lg | 833px |
| lg | 834px |
| lg | 863px |
| lg | 955px |
| lg | 959px |
| lg | 980px |
| lg | 1023px |
| lg | 1024px |
| xl | 1044px |
| xl | 1068px |
| xl | 1069px |
| xl | 1070px |
| xl | 1088px |
| xl | 1147px |
| 2xl | 1293px |
| 2xl | 1306px |
| 2xl | 1440px |
| 2xl | 1441px |

Mobile-first: design for small screens, layer on responsive overrides.

## Component Patterns

### Card

```css
.card {
  background: #161617;
  border: 1px solid #424245;
  border-radius: 17px;
  padding: 16px;
  box-shadow: inset 0 0 3px #f5f5f7;
}
```

```html
<div class="card">
  <h3>Card Title</h3>
  <p>Card content goes here.</p>
</div>
```

### Button

```css
/* Primary */
.btn-primary {
  background: #0066cc;
  color: #f4f8fb;
  border-radius: 17px;
  padding: 8px 16px;
  font-weight: 500;
  transition: opacity 150ms ease;
}
.btn-primary:hover { opacity: 0.9; }

/* Ghost */
.btn-ghost {
  background: transparent;
  border: 1px solid #424245;
  color: #f4f8fb;
  border-radius: 17px;
  padding: 8px 16px;
}
```

```html
<button class="btn-primary">Get Started</button>
<button class="btn-ghost">Learn More</button>
```

### Input

```css
.input {
  background: #000000;
  border: 1px solid #424245;
  border-radius: 17px;
  padding: 8px 12px;
  color: #f4f8fb;
  font-size: 14px;
}
.input:focus { border-color: #0066cc; outline: none; }
```

```html
<input class="input" type="text" placeholder="Search..." />
```

### Badge / Chip

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  background: #161617;
  color: #e8e8ed;
}
```

```html
<span class="badge">New</span>
<span class="badge">Beta</span>
```

### Modal / Dialog

```css
.modal-backdrop { background: rgba(0, 0, 0, 0.6); }
.modal {
  background: #161617;
  border: 1px solid #424245;
  border-radius: 980px;
  padding: 24px;
  max-width: 480px;
  width: 90vw;
  box-shadow: 8px 8px 16px 0#00000014;
}
```

```html
<div class="modal-backdrop">
  <div class="modal">
    <h2>Dialog Title</h2>
    <p>Dialog content.</p>
    <button class="btn-primary">Confirm</button>
    <button class="btn-ghost">Cancel</button>
  </div>
</div>
```

### Table

```css
.table { width: 100%; border-collapse: collapse; }
.table th {
  text-align: left;
  padding: 8px 12px;
  font-weight: 500;
  font-size: 12px;
  color: #e8e8ed;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid #424245;
}
.table td {
  padding: 12px;
  border-bottom: 1px solid #424245;
}
```

```html
<table class="table">
  <thead><tr><th>Name</th><th>Status</th><th>Date</th></tr></thead>
  <tbody>
    <tr><td>Item One</td><td>Active</td><td>Jan 1</td></tr>
    <tr><td>Item Two</td><td>Pending</td><td>Jan 2</td></tr>
  </tbody>
</table>
```

### Navigation

```css
.nav {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #424245;
}
.nav-link {
  color: #e8e8ed;
  padding: 8px 12px;
  border-radius: 17px;
  transition: color 150ms;
}
.nav-link:hover { color: #f4f8fb; }
.nav-link.active { color: #0066cc; }
```

```html
<nav class="nav">
  <a href="/" class="nav-link active">Home</a>
  <a href="/about" class="nav-link">About</a>
  <a href="/pricing" class="nav-link">Pricing</a>
  <button class="btn-primary" style="margin-left: auto">Get Started</button>
</nav>
```

### Extracted Components

These components were found in the codebase:

**Button** (`html`)

**Card** (`html`)
- Variants: `13`, `content`, `info`, `title`, `header`

**Navigation** (`html`)

**Badge** (`html`)

**Modal** (`html`)

**List** (`html`)

## Page Structure

The following page sections were detected:

- **Navigation** — Top navigation bar (14 items)
- **Hero** — Hero/banner section with headline and CTAs
- **Footer** — Page footer with links and info (76 items)
- **Stats** — Statistics/metrics display
- **Cards** — Grid of 49 card elements (49 items)
- **Features** — Feature/benefit cards grid (269 items)
- **Faq** — FAQ/accordion section
- **Cta** — Call-to-action section

When building pages, follow this section order and structure.

## Animation & Motion

This project uses **expressive motion**. Animations are part of the design language.

### CSS Animations

- `globalnav-chevron-slide-in-hover`
- `globalnav-chevron-hover-off`
- `globalnav-flyout-slide-forward-next`
- `globalnav-flyout-slide-forward-previous`
- `globalnav-flyout-slide-back-previous`

### Motion Tokens

- **Duration scale:** `0ms`, `0s`, `.1s`, `.12s`, `.15s`, `.16s`, `.19s`, `.24s`, `.32s`, `.4s`, `.5s`, `0.5s`, `.8s`, `1s`, `1ms`, `20ms`, `30ms`, `33.5ms`, `38ms`, `40ms`, `50ms`, `50.25ms`, `60ms`, `67ms`, `80ms`, `100ms`, `120ms`, `140ms`, `150ms`, `160ms`, `185ms`, `190ms`, `200ms`, `201ms`, `234ms`, `234.5ms`, `240ms`, `250ms`, `251.24999999999997ms`, `268ms`, `275ms`, `300ms`, `320ms`, `335ms`, `342ms`, `350ms`, `380ms`, `400ms`, `470ms`, `500ms`, `700ms`, `900ms`, `1000ms`, `1200ms`
- **Easing functions:** `cubic-bezier(.4,0,.6,1)`, `cubic-bezier(.4,0,.6,1),cubic-bezier(.4,0,.6,1),step-start`, `ease`, `cubic-bezier(.25,.1,.3,1)`, `cubic-bezier(1,.1,0,.3)`, `cubic-bezier(0.28,0.11,0.32,1)`, `cubic-bezier(0.4,0,0.6,1)`, `ease-out`, `ease-in`, `linear`, `ease-in-out`, `cubic-bezier(.4,.1,.4,1)`, `cubic-bezier(0,0,.2,1)`, `cubic-bezier(0,0,.5,1)`, `cubic-bezier(.15,0,.2,1)`, `cubic-bezier(.165,.84,.44,1)`, `cubic-bezier(0.15,0,0.2,1)`, `cubic-bezier(.455,.03,.515,.955)`, `cubic-bezier(.4,0,.3,2)`, `cubic-bezier(0.45,0,0.55,1)`, `cubic-bezier(0,0,0.5,1)`, `cubic-bezier(0.4,0.1,0.4,1)`, `cubic-bezier(0,0,0.2,1)`, `cubic-bezier(0.4,0,0.3,2)`, `cubic-bezier(1,0.1,0,0.3)`

### Motion Guidelines

- **Duration:** Use values from the duration scale above. Short (0ms) for micro-interactions, long (1200ms) for page transitions
- **Easing:** Use `cubic-bezier(.4,0,.6,1)` as the default easing curve
- **Direction:** Elements enter from bottom/right, exit to top/left
- **Reduced motion:** Always respect `prefers-reduced-motion` — disable animations when set

## Depth & Elevation

### Shadow Tokens

- Subtle: `inset 0 0 0 2px var(--tabnav-focus-color)`
- Raised (cards, buttons): `inset 0 0 3px #f5f5f7`
- Raised (cards, buttons): `inset 0 0 3px #1d1d1f`
- Raised (cards, buttons): `inset 1.8px 1.8px .5px -1.4px #6e6e73,inset -1.5px -1.5px .5px -1.1px #6e6e73`
- Raised (cards, buttons): `0 1px 3px rgba(0,0,0,.3)`
- Raised (cards, buttons): `var(--sk-tile-box-shadow)`

### Z-Index Scale

`0, 1, 2, 3, 4, 5, 9, 10, 11, 12, 15, 30, 1000, 9987, 9996, 9997, 9998, 9999, 10000, 10001, 11000, 11002, 99999, 9999999`

Use these exact values — never invent z-index values.

## Anti-Patterns (Never Do)

- **No zebra striping** — tables and lists use borders for separation
- **No invented colors** — every hex value must come from the palette above
- **No arbitrary spacing** — every dimension is a multiple of 4px
- **No extra fonts** — only SF Pro AR and SF Pro Text and SF Mono are allowed
- **No arbitrary border-radius** — use the scale: .1764705882rem, .25rem, .5882352941rem, .75rem, 1px, 1.1764705882rem, 1.2px, 1.3em, 2rem, 2px
- **No opacity for disabled states** — use muted colors instead

## Workflow

1. **Read** `references/DESIGN.md` before writing any UI code
2. **Pick colors** from the Color System section — never invent new ones
3. **Set typography** — SF Pro AR, SF Pro Text, SF Mono only, using the type scale
4. **Build layout** on the 4px grid — check every margin, padding, gap
5. **Match components** to patterns above before creating new ones
6. **Apply elevation** — use shadow tokens
7. **Validate** — every value traces back to a design token. No magic numbers.

## Brand Spec

- **Favicon:** `/favicon.ico`
- **Site URL:** `https://www.apple.com/`
- **Brand color:** `#0066cc`
- **Brand typeface:** SF Pro AR

## Quick Reference

```
Background:     #000000
Surface:        #161617
Text:           #f4f8fb / #e8e8ed
Accent:         #0066cc
Border:         #424245
Font:           SF Pro AR
Spacing:        4px grid
Radius:         17px
Components:     9 detected
```

## When to Trigger

Activate this skill when:
- Creating new components, pages, or visual elements for apple
- Writing CSS, Tailwind classes, styled-components, or inline styles
- Building page layouts, templates, or responsive designs
- Reviewing UI code for design consistency
- The user mentions "apple" design, style, UI, or theme
- Generating mockups, wireframes, or visual prototypes

---

# Full Reference Files

> Every output file is embedded below. Claude has full design system context from /skills alone.

## Design System Tokens (DESIGN.md)

# apple DESIGN.md

> Auto-generated design system — reverse-engineered via static analysis by skillui.
> Frameworks: None detected
> Colors: 20 · Fonts: 3 · Components: 9
> Icon library: not detected · State: not detected
> Primary theme: dark · Dark mode toggle: no · Motion: expressive

## Visual Reference

**Match this design exactly** — study colors, fonts, spacing, and component shapes before writing any UI code.

![apple Homepage](../screenshots/homepage.png)

---

## 1. Visual Theme & Atmosphere

This is a **dark-themed** interface with a cool tone. Depth is expressed through layered shadows and subtle surface color variation. Typography pairs **SF Pro Text** for display/headings with **SF Pro AR** for body text, creating clear visual hierarchy through type contrast. Spacing follows a **4px base grid** (compact density), with scale: 2, 4, 6, 8, 10, 12, 14, 16px. The palette is predominantly monochromatic with **#0066cc** as the single accent color — used sparingly for interactive elements and emphasis. Motion is expressive — spring physics, layout animations, and staggered reveals are part of the visual language.

---

## 2. Color Palette & Roles

| Token | Hex | Role | Use |
|---|---|---|---|
| r-globalnav-color | `#000000` | background | Page background, darkest surface |
| r-globalnav-background-opened-dark | `#161617` | surface | Card and panel backgrounds |
| r-globalnav-background-opened | `#f4f8fb` | text-primary | Headings and body text |
| r-globalnav-color-secondary | `#e8e8ed` | text-muted | Captions, placeholders, secondary info |
| r-globalnav-color-secondary | `#333336` | text-muted | Captions, placeholders, secondary info |
| r-globalnav-submenu-header-color | `#6e6e73` | text-muted | Captions, placeholders, secondary info |
| sk-glyph-gray-secondary-alt | `#424245` | border | Dividers, card borders, outlines |
| sk-blocklink-color | `#0066cc` | accent | CTAs, links, focus rings, active states |
| sk-badge-text-color | `#b64400` | danger | Error states, destructive actions |
| sk-button-background | `#0071e3` | info | Informational highlights |
| r-globalnav-submenu-header-color | `#86868b` | unknown | Palette color |
| sk-blocklink-color | `#2997ff` | unknown | Palette color |
| sk-glyph-gray-secondary-alt | `#d2d2d7` | unknown | Palette color |
| sk-button-background-hover | `#272729` | unknown | Palette color |
| sk-dotnav-scrim-solid-iconcontrol-scrim-color-hover | `#dfdfe3` | unknown | Palette color |
| sk-badge-text-color | `#ff791b` | unknown | Palette color |
| sk-badge-background | `#f56300` | unknown | Palette color |
| sk-paddlenav-background-active | `#c1c1c6` | unknown | Palette color |
| sk-badge-background | `#fae9e1` | unknown | Palette color |
| ribbon-focus-color | `#007aff` | unknown | Palette color |

### CSS Variable Tokens

```css
--r-globalnav-background-opened: #fafafc;
--r-globalnav-background-opened-dark: #161617;
--r-globalnav-color-secondary: #333336;
--globalnav-background: none;
--r-globalnav-color-secondary: #E8E8ED;
--r-globalnav-color-secondary: #333336;
--globalnav-background: rgba(250,250,252,.92);
--globalnav-background: rgba(250,250,252,.8);
--globalnav-background: rgba(22,22,23,.88);
--globalnav-background: rgba(22,22,23,.8);
--globalnav-background: rgba(250,250,252,.92);
--globalnav-background: rgba(250,250,252,.8);
--r-globalnav-search-list-item-hover-background: rgb(245,245,247);
--r-globalnav-search-list-item-hover-background: rgb(29,29,31);
--r-globalnav-search-list-item-hover-background: rgb(245,245,247);
--globalmessage-segment-background: rgb(250,250,252);
--globalmessage-segment-scrim-background: rgba(0,0,0,.04);
--globalmessage-segment-border-color: rgba(0,0,0,.48);
--globalmessage-segment-background: rgb(22,22,23);
--globalmessage-segment-scrim-background: rgba(255,255,255,.08);
```


---

## 3. Typography Rules

**Font Stack:**
- **SF Pro AR** — Heading 1, Heading 2, Heading 3
- **SF Pro Text** — Body, Caption
- **SF Mono** — Code

| Role | Font | Size | Weight |
|---|---|---|---|
| Heading 1 | SF Pro AR | 96px | 700 |
| Heading 2 | SF Pro AR | 89px | 700 |
| Heading 3 | SF Pro AR | 80px | 700 |
| Body | SF Pro Text | 17px | 400 |
| Caption | SF Pro Text | 12px | 400 |
| Code | SF Mono | 14px | 400 |

**Typographic Rules:**
- Limit to 3 font families max per screen
- Use **SF Pro AR** for body/UI text, **SF Pro Text** for display/headings
- Maintain consistent hierarchy: no more than 3-4 font sizes per screen
- Headings use bold (600-700), body uses regular (400)
- Line height: 1.5 for body text, 1.2 for headings
- Use color and opacity for secondary hierarchy, not additional font sizes


---

## 4. Component Stylings

### Layout (1)

**Footer** — `html`

### Navigation (1)

**Navigation** — `html`

### Data Display (3)

**Card** — `html`
- Variants: `13`, `content`, `info`, `title`, `header`

**Badge** — `html`

**List** — `html`

### Data Input (1)

**Button** — `html`
- Animation: 

### Overlay (1)

**Modal** — `html`

### Media (2)

**Image** — `html`

**Icon** — `html`



---

## 5. Layout Principles

- **Base spacing unit:** 4px
- **Spacing scale:** 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24
- **Border radius:** .1764705882rem, .25rem, .5882352941rem, .75rem, 1px, 1.1764705882rem, 1.2px, 1.3em, 2rem, 2px, 3px, 4px, 5px, 6px, 8px, 10px, 12px, 13px, 17px, 18px, 19.5px, 20px, 21px, 27.5px, 28px, 30px, 32px, 35px, 99px, 999px, inherit, 100%, 100px, 109px, 129px, 980px
- **Max content width:** 1068px

**Spacing as Meaning:**
| Spacing | Use |
|---|---|
| 4-8px | Tight: related items within a group |
| 12-16px | Medium: between groups |
| 24-32px | Wide: between sections |
| 48px+ | Vast: major section breaks |


---

## 6. Depth & Elevation

### Flat — subtle depth hints

- `inset 0 0 0 2px var(--tabnav-focus-color)`

### Raised — cards, buttons, interactive elements

- `inset 0 0 3px #f5f5f7`
- `inset 0 0 3px #1d1d1f`
- `inset 1.8px 1.8px .5px -1.4px #6e6e73,inset -1.5px -1.5px .5px -1.1px #6e6e73`

### Floating — dropdowns, popovers, modals

- `8px 8px 16px 0#00000014`
- `2px 4px 12px #00000014`
- `2px 4px 16px #00000029`

### Overlay — full-screen overlays, top-level dialogs

- `3px 5px 30px rgba(0,0,0,.22)`
- `2px 8px 24px 2px #00000014`

### Z-Index Scale

`0, 1, 2, 3, 4, 5, 9, 10, 11, 12, 15, 30, 1000, 9987, 9996, 9997, 9998, 9999, 10000, 10001, 11000, 11002, 99999, 9999999`



---

## 7. Animation & Motion

This project uses **expressive motion**. Animations are an integral part of the experience.

### CSS Animations

- `@keyframes globalnav-chevron-slide-in-hover`
- `@keyframes globalnav-chevron-hover-off`
- `@keyframes globalnav-flyout-slide-forward-next`
- `@keyframes globalnav-flyout-slide-forward-previous`
- `@keyframes globalnav-flyout-slide-back-previous`
- `@keyframes globalnav-flyout-slide-back-next`
- `@keyframes globalnav-scrim-height-change`
- `@keyframes globalnav-fade-in`

### Animated Components

- **Button**: 

### Motion Guidelines

- Duration: 150-300ms for micro-interactions, 300-500ms for page transitions
- Easing: `ease-out` for enters, `ease-in` for exits
- Always respect `prefers-reduced-motion`


---

## 8. Do's and Don'ts

### Do's

- Use `#0066cc` for interactive elements (buttons, links, focus rings)
- Use `#000000` as the primary page background
- Pair **SF Pro AR** (body) with **SF Pro Text** (display) — these are the only allowed fonts
- Follow the **4px** spacing grid for all margins, padding, and gaps
- Use the defined shadow tokens for elevation — see Section 6
- Use border-radius from the scale: .1764705882rem, .25rem, .5882352941rem, .75rem, 1px
- Reuse existing components from Section 4 before creating new ones

### Don'ts

- Don't introduce colors outside this palette — extend the design tokens first
- Don't introduce additional font families beyond SF Pro AR and SF Pro Text and SF Mono
- Don't use arbitrary spacing values — stick to multiples of 4px
- Don't create custom box-shadow values outside the system tokens
- Don't use arbitrary border-radius values — pick from the defined scale
- Don't duplicate component patterns — check Section 4 first


---

## 9. Responsive Behavior

| Name | Value | Source |
|---|---|---|
| xs | 320px | css |
| xs | 350px | css |
| xs | 360px | css |
| xs | 368px | css |
| xs | 375px | css |
| xs | 379px | css |
| xs | 393px | css |
| xs | 420px | css |
| xs | 433px | css |
| xs | 436px | css |
| xs | 460px | css |
| xs | 477px | css |
| xs | 478px | css |
| xs | 480px | css |
| sm | 550px | css |
| sm | 569px | css |
| sm | 605px | css |
| sm | 640px | css |
| md | 641px | css |
| md | 642px | css |
| md | 654px | css |
| md | 717px | css |
| md | 734px | css |
| md | 735px | css |
| md | 736px | css |
| md | 750px | css |
| md | 758px | css |
| md | 767px | css |
| md | 768px | css |
| lg | 833px | css |
| lg | 834px | css |
| lg | 863px | css |
| lg | 955px | css |
| lg | 959px | css |
| lg | 980px | css |
| lg | 1023px | css |
| lg | 1024px | css |
| xl | 1044px | css |
| xl | 1068px | css |
| xl | 1069px | css |
| xl | 1070px | css |
| xl | 1088px | css |
| xl | 1147px | css |
| 2xl | 1293px | css |
| 2xl | 1306px | css |
| 2xl | 1440px | css |
| 2xl | 1441px | css |

**Approach:** Use `@media (min-width: ...)` queries matching the breakpoints above.


---

## 10. Agent Prompt Guide

Use these as starting points when building new UI:

### Build a Card

```
Background: #161617
Border: 1px solid #424245
Radius: 17px
Padding: 16px
Font: SF Pro AR
Use shadow tokens from Section 6.
```

### Build a Button

```
Primary: bg #0066cc, text white
Ghost: bg transparent, border #424245
Padding: 8px 16px
Radius: 17px
Hover: opacity 0.9 or lighter shade
Focus: ring with #0066cc
```

### Build a Page Layout

```
Background: #000000
Max-width: 1068px, centered
Grid: 4px base
Responsive: mobile-first, breakpoints from Section 9
```

### Build a Stats Card

```
Surface: #161617
Label: #e8e8ed (muted, 12px, uppercase)
Value: #f4f8fb (primary, 24-32px, bold)
Status: use success/warning/danger from Section 2
```

### Build a Form

```
Input bg: #000000
Input border: 1px solid #424245
Focus: border-color #0066cc
Label: #e8e8ed 12px
Spacing: 16px between fields
Radius: 17px
```

### General Component

```
1. Read DESIGN.md Sections 2-6 for tokens
2. Colors: only from palette
3. Font: SF Pro AR, type scale from Section 3
4. Spacing: 4px grid
5. Components: match patterns from Section 4
6. Elevation: shadow tokens
```

## Homepage Screenshots (screenshots/)

![homepage.png](screenshots/homepage.png)

