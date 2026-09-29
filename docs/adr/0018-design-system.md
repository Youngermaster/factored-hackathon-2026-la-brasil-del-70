# 0018: Design system on Radix primitives, Tailwind tokens, Phosphor icons, and the deck's typefaces

- Status: accepted
- Date: 2026-09-29

## Context

Phase 12 builds the web foundation for three surfaces (customer chat, glass box, agent inbox) and a read-only evaluation view. The UI must meet WCAG 2.2 AA in light and dark themes, run under a strict CSP (no inline scripts, no font CDN), look deliberate rather than templated, and read as the same product as the team's pitch deck (`slides/`), which already has a palette with fixed meanings and three self-hosted typefaces. CLAUDE.md fixes the stack at the level of Radix UI, Tailwind CSS v4 with design tokens as CSS variables, and one outline icon set. The human delegated the design approval to the orchestrator, who pre-approved the direction (the deck's identity, adapted with restraint).

## Considered options

### Component foundation

1. **Radix Themes** (styled): fast, but its look and tokens would be overridden almost entirely to reach the deck's identity.
2. **shadcn/ui**: copies Radix-based components into the repository; a generator step and its default style to strip.
3. **Radix primitives wrapped in `shared/ui`** with our own Tailwind classes: unstyled, accessible behavior (focus traps, roving focus, live regions), our tokens only.
4. **A native-only set**: full control, but focus management for dialogs, tabs, and toasts would be rewritten and retested.

### Tokens

1. Tailwind's default palette with `dark:` variants.
2. **CSS variables per theme on `[data-theme]`**, mapped into Tailwind v4 with `@theme inline`, the default palette removed.

### Icons

Lucide, Phosphor, Radix Icons, Tabler.

### Fonts

Inter or Geist (generic defaults), or **the deck's Unbounded, Instrument Sans, and Geist Mono** through `@fontsource-variable`.

## Decision

- Radix primitives through the `radix-ui` umbrella package (one version for every primitive), wrapped in `apps/web/src/shared/ui` as compound components; `Select` stays a styled native `<select>` (better on phones and for screen readers than a custom listbox).
- Tokens as CSS variables per theme in `shared/ui/tokens.css`, mapped into Tailwind v4, with Tailwind's default colors removed so only tokens exist; `contrast.ts` lists every allowed pair and a test checks each against WCAG AA in both themes.
- The theme is `system`, `light`, or `dark`, applied before first paint by an external classic script (`public/theme-init.js`), so no inline script is needed; the preference sits in `localStorage` through one module that ESLint allows, never session data.
- Phosphor icons, regular (outline) weight, re-exported from `shared/ui/icons.ts` under role names. Both installed taste skills prefer it, and `minimalist-ui` rules out Lucide.
- The deck's typefaces, self-hosted: Unbounded for the product name and page titles only, Instrument Sans for text, Geist Mono for amounts, codes, and identifiers.
- Colors keep the deck's meanings: blue for the language model, yellow for deterministic decisions and verified actions, red for risk and escalation, light gray for data. Light theme by default for customer screens; the primary action is ink, not an accent.
- Accessibility tests use vitest-axe 0.1.0 with axe-core pinned directly at 4.13 (the 1.0 line of vitest-axe has been a prerelease since 2023; the wrapper is thin and its axe-core range resolves to the maintained release). Contrast is tested from the tokens because jsdom cannot compute it.

## Consequences

- Behavior (focus, keyboard, ARIA) comes from Radix; appearance is entirely ours and auditable in one CSS file.
- The deck and the app share a visual language, so screenshots in the video and the live demo match.
- New colors cannot be used ad hoc: a component needing a new pair adds it to `contrast.ts`, and the test proves it.
- Fonts add about 270 KB of WOFF2 files to the build (the browser downloads only the subsets it needs); Unbounded is the largest.
- Dependencies added (all MIT, OFL-1.1 for fonts): `radix-ui`, `@phosphor-icons/react` (33 MB unpacked, tree-shaken to the glyphs used), the three `@fontsource-variable` packages, plus the stack items CLAUDE.md names (React Router, TanStack Query, i18next, react-hook-form, zod, openapi-fetch); dev: `vitest-axe`, `axe-core`, `playwright-chromium` (screenshot script only).
