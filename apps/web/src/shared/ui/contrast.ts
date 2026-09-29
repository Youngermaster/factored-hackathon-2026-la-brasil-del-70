/**
 * The text and interface color pairs the design system allows, with the WCAG 2.2 minimum each must meet in both
 * themes. tokens.test.ts computes every ratio from tokens.css and fails below the minimum. A component that needs a
 * new foreground and background combination adds it here first.
 *
 *   4.5  text at body size (SC 1.4.3)
 *   3.0  non-text interface parts: input borders, focus indicators, icons that carry meaning (SC 1.4.11)
 */
export type TokenName =
  | 'canvas'
  | 'surface'
  | 'surface-sunken'
  | 'surface-hover'
  | 'border-strong'
  | 'fg'
  | 'fg-secondary'
  | 'fg-muted'
  | 'action'
  | 'action-hover'
  | 'action-fg'
  | 'focus'
  | 'understanding'
  | 'understanding-fg'
  | 'understanding-text'
  | 'understanding-subtle'
  | 'decision'
  | 'decision-fg'
  | 'decision-text'
  | 'decision-subtle'
  | 'risk'
  | 'risk-fg'
  | 'risk-text'
  | 'risk-subtle';

export interface ContrastPair {
  readonly fg: TokenName;
  readonly bg: TokenName;
  readonly min: 4.5 | 3;
  readonly use: string;
}

const onSurfaces = (fg: TokenName, min: 4.5 | 3, use: string): ContrastPair[] =>
  (['canvas', 'surface', 'surface-sunken', 'surface-hover'] as const).map((bg) => ({
    fg,
    bg,
    min,
    use,
  }));

export const CONTRAST_PAIRS: readonly ContrastPair[] = [
  ...onSurfaces('fg', 4.5, 'body text'),
  ...onSurfaces('fg-secondary', 4.5, 'secondary text'),
  ...onSurfaces('fg-muted', 4.5, 'hints, captions, as-of notes'),
  ...onSurfaces('understanding-text', 4.5, 'model-derived labels at body size'),
  ...onSurfaces('risk-text', 4.5, 'risk and error text at body size'),
  ...onSurfaces('border-strong', 3, 'input and control borders'),
  ...onSurfaces('focus', 3, 'focus indicator'),
  { fg: 'action-fg', bg: 'action', min: 4.5, use: 'primary button label' },
  { fg: 'action-fg', bg: 'action-hover', min: 4.5, use: 'primary button label on hover' },
  { fg: 'understanding-fg', bg: 'understanding', min: 4.5, use: 'ink on a filled blue chip' },
  { fg: 'understanding-text', bg: 'understanding-subtle', min: 4.5, use: 'model chip' },
  { fg: 'fg', bg: 'understanding-subtle', min: 4.5, use: 'text inside a model panel' },
  { fg: 'decision-fg', bg: 'decision', min: 4.5, use: 'ink on the yellow verified fill' },
  { fg: 'decision-text', bg: 'decision-subtle', min: 4.5, use: 'decision chip' },
  { fg: 'fg', bg: 'decision-subtle', min: 4.5, use: 'text inside a decision panel' },
  { fg: 'risk-fg', bg: 'risk', min: 4.5, use: 'label on a filled red button' },
  { fg: 'risk-text', bg: 'risk-subtle', min: 4.5, use: 'risk chip and error summary' },
  { fg: 'fg', bg: 'risk-subtle', min: 4.5, use: 'text inside a risk panel' },
  {
    fg: 'fg-secondary',
    bg: 'risk-subtle',
    min: 4.5,
    use: 'secondary text in an error state or toast',
  },
  {
    fg: 'fg-secondary',
    bg: 'decision-subtle',
    min: 4.5,
    use: 'secondary text in a verified toast',
  },
];

const channel = (value: number): number => {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
};

/** Relative luminance of a `#rrggbb` color (WCAG 2.2). */
export function luminance(hex: string): number {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) {
    throw new Error(`expected an opaque #rrggbb color, got ${hex}`);
  }
  const n = Number.parseInt(hex.slice(1), 16);
  return (
    0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255)
  );
}

/** WCAG contrast ratio between two opaque colors, from 1 to 21. */
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}
