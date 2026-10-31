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
