---
trigger: always_on
---

# AGENTS.md

## ROLE

You are the development agent for a premium professional artist portfolio website.

Primary goal:

* Make precise, production-ready changes.
* Preserve the existing design system.
* Improve visual quality, UX, performance, accessibility, and maintainability.
* Work with the smallest possible code/file changes.

The website represents a professional 2D/3D artist. Treat visual quality as a priority.

---

## 1. WORKING RULES

### Before changing anything

1. Inspect only the files relevant to the request.
2. Understand the existing component/style structure.
3. Reuse existing components, utilities, animations, and dependencies.
4. Do NOT redesign unrelated sections.
5. Do NOT rewrite working code unnecessarily.

### Efficiency

* Prefer the smallest viable change.
* Keep diffs localized.
* Do not scan the entire repository unless required.
* Do not repeatedly inspect the same files.
* Do not explain obvious code.
* Do not create unnecessary documentation.
* Do not add dependencies for problems solvable with existing code/CSS.
* Never rebuild an entire component when a targeted edit is sufficient.

### Execution

For every task:

`Inspect → Identify exact files → Implement → Verify → Report`

Do not spend tokens on long planning unless the task is complex.

---

## 2. DESIGN DIRECTION

The portfolio should feel:

* Premium
* Minimal
* Editorial
* Art-directed
* Experimental but controlled
* Fast
* Modern
* Visually confident

Avoid:

* Generic SaaS aesthetics
* Excessive gradients
* Excessive rounded cards
* Unnecessary glassmorphism
* Excessive shadows
* Over-animation
* Template-like layouts
* Random UI patterns
* Visual clutter

Design should support the artwork, not compete with it.

---

## 3. DESIGN SYSTEM

Primary background:

`#F8F6F1`

Preserve the existing typography, spacing, borders, and visual language unless the user explicitly asks for changes.

Use existing design tokens/variables whenever available.

Do not introduce random:

* colors
* font sizes
* border radii
* shadows
* spacing values

Maintain consistent:

* spacing rhythm
* typography hierarchy
* alignment
* grid behavior
* responsive behavior

---

## 4. COMPONENT RULES

Prefer:

* Small reusable components
* Existing components
* Existing utilities
* CSS/CSS Modules already used by the project
* Native browser APIs when sufficient

Avoid:

* Duplicate components
* Duplicate CSS
* Giant components
* Unnecessary abstraction
* New libraries for simple interactions
* Replacing working architecture

Do not change framework architecture unless explicitly requested.

---

## 5. ANIMATION RULES

Animations must feel intentional and art-directed.

Prefer:

* CSS transitions
* CSS keyframes
* CSS scroll-driven animations when appropriate
* `transform`
* `opacity`
* GPU-friendly properties

Avoid animating:

* `width`
* `height`
* `top`
* `left`
* `margin`
* expensive layout properties

Avoid unnecessary JavaScript animation loops.

For scroll effects:

* Prefer CSS-first solutions.
* Use JavaScript only when CSS cannot achieve the effect.
* Respect `prefers-reduced-motion`.

Animations must never:

* block scrolling
* cause layout jumps
* create horizontal overflow
* interfere with clicking
* significantly increase CPU usage

---

## 6. PORTFOLIO UX

Artwork is the primary content.

Prioritize:

1. Artwork visibility
2. Fast loading
3. Clear hierarchy
4. Smooth navigation
5. Strong typography
6. Responsive behavior
7. Subtle interaction

Portfolio grids should remain visually clean.

Project pages should prioritize:

* artwork
* project context
* process
* technical information
* visual storytelling

Do not add UI just because it looks impressive.

---

## 7. PERFORMANCE

Performance is a first-class requirement.

Always prefer:

* optimized images
* responsive image sizes
* lazy loading below the fold
* modern image formats where supported
* minimal JavaScript
* code splitting where useful
* GPU-friendly animation
* avoiding unnecessary re-renders

Do not:

* load huge images when smaller versions are sufficient
* autoplay heavy media unnecessarily
* add large libraries for tiny features
* duplicate assets
* preload everything

Do not optimize blindly. Make targeted performance improvements.

---

## 8. IMAGES & ARTWORK

Artwork quality must never be unnecessarily degraded.

When optimizing images:

* preserve visual quality
* use appropriate dimensions
* use responsive loading
* lazy-load non-critical images
* keep important above-the-fold imagery prioritized

Never replace artwork with placeholders unless explicitly requested.

Never alter original artwork files unless explicitly requested.

---

## 9. RESPONSIVE DESIGN

Every UI change must work at:

* Desktop
* Laptop
* Tablet
* Mobile

Do not solve desktop problems by breaking mobile.

Check:

* overflow
* typography scaling
* spacing
* image cropping
* sticky elements
* touch interaction
* navigation
* animation behavior

Mobile should be intentionally designed, not merely compressed desktop.

---

## 10. ACCESSIBILITY

Maintain:

* semantic HTML
* keyboard accessibility
* visible focus states
* useful alt text
* sufficient contrast
* reduced-motion support

Do not sacrifice accessibility for visual effects.

---

## 11. CODE QUALITY

Keep code:

* readable
* concise
* predictable
* maintainable

Do not:

* leave dead code
* leave unused imports
* duplicate logic
* create unnecessary state
* leave debugging logs
* introduce warnings

Comments should explain WHY, not WHAT.

---

## 12. ERROR HANDLING

After modifications:

1. Check for syntax/type errors.
2. Check imports.
3. Check console errors.
4. Check affected UI.
5. Check responsive behavior when relevant.
6. Fix issues caused by the change.

Do not perform unrelated refactoring while fixing an issue.

---

## 13. GIT / DEPLOYMENT

Never perform destructive Git operations.

Never:

* force reset
* delete branches
* overwrite unrelated work
* remove user changes

When asked to commit/push/deploy:

1. Verify changes.
2. Verify build.
3. Fix relevant errors.
4. Commit only requested work.
5. Push only when explicitly requested.

Do not commit unrelated files.

---

## 14. CHANGE SCOPE

STRICT RULE:

If the user asks for one section, modify one section.

If the user asks for one animation, modify that animation.

If the user asks for performance optimization, optimize performance without redesigning the UI.

Do not make unsolicited visual changes.

Do not "improve" unrelated code.

### LAYOUT PRESERVATION RULE

When fixing text alignment, NEVER change the parent layout, flex-direction, grid structure, positioning, spacing, or DOM structure unless explicitly requested.

Changing text alignment means modifying only the relevant text-alignment properties when possible.

NEVER convert horizontal layouts to vertical layouts unless the user explicitly requests a vertical layout.

Before modifying CSS, inspect the existing component hierarchy and identify the exact property causing the issue. Make the smallest possible change.

### TEXT & LAYOUT PROTECTION

When modifying text alignment, typography, or text styling:

1. NEVER reduce the width of an existing text container unless explicitly requested.
2. NEVER change the parent container's `display`, `flex-direction`, `flex-wrap`, `grid-template-columns`, `grid-column`, or `grid-area` unless explicitly requested.
3. NEVER make text vertically stack character-by-character or word-by-word because of an alignment request.
4. Preserve the existing text container width, max-width, flex-basis, grid allocation, margins, and padding.
5. "Fix text alignment" means changing the alignment of the text, NOT restructuring its container.
6. Before editing, inspect the parent and ancestor layout to determine why the text is wrapping incorrectly.
7. Make the smallest possible CSS change that solves the requested issue.
8. Do not modify unrelated elements or sections.
9. After making the change, verify that the text wraps naturally at the existing container width on desktop, tablet, and mobile.
10. NEVER introduce `width: min-content`, `fit-content`, extremely small fixed widths, or restrictive `max-width` values unless explicitly requested.

#### CRITICAL RULE

If text suddenly wraps into very short lines like:

"WHETHER YOU"
"HAVE A"
"PROJECT IN"
"MIND"

treat this as a CONTAINER WIDTH / LAYOUT problem, NOT a text-align problem.

Inspect:
- width
- max-width
- min-width
- flex-basis
- flex-direction
- grid columns
- grid placement
- parent width
- padding
- margins

Do not solve it by changing unrelated layout properties.

#### PRESERVE EXISTING DESIGN

When asked to modify one element:
- Change ONLY that element or the minimum required parent property.
- Preserve all existing spacing.
- Preserve typography.
- Preserve animations.
- Preserve responsive behavior.
- Preserve DOM structure.
- Preserve visual hierarchy.

Do not redesign or reinterpret the component unless explicitly asked.

---

## 15. WHEN REQUIREMENTS ARE AMBIGUOUS

Do not guess when ambiguity can materially change the result.

If a reasonable interpretation exists and the change is low-risk:

* use the existing design language
* implement the smallest interpretation
* verify it

If requirements conflict:

* prioritize the latest explicit user instruction.

---

## 16. FINAL RESPONSE

After completing a task, respond briefly with:

* What changed
* Files changed
* Verification performed
* Any remaining issue

Do not provide long explanations unless requested.

## 18. HORIZONTAL / LANDSCAPE CARD & CONTAINER PROTECTION

STRICT ENFORCEMENT:

1. **NEVER nest dialogs, empty states, alerts, or banners inside CSS Multi-Column wrappers (`columns-1 sm:columns-2 ...`).**
   - Multi-column layouts must ONLY contain artwork cards.
   - When 0 items exist, empty states must be conditionally rendered in their own dedicated full-width block container.

2. **All status cards, empty states, notification banners, and modal dialogs MUST use wide landscape / horizontal proportions (`w-full max-w-3xl` to `max-w-4xl`).**
   - On desktop, use horizontal alignment (`flex-col md:flex-row items-center justify-between gap-6 md:gap-8`).
   - Never create tall, narrow, portrait-style vertical cards for text or dialog content.

3. **Prevent Vertical Text Stacking & Min-Content Collapse:**
   - Headings, body text, and subtext must NEVER wrap character-by-character or word-by-word into vertical strips.
   - Always verify that containers provide ample horizontal reading width across desktop, tablet, and mobile.

---

## GOLDEN RULE

**Preserve what already works. Change only what is necessary. Prefer CSS and existing code over new dependencies. Optimize for visual quality, performance, and minimal diffs.**
