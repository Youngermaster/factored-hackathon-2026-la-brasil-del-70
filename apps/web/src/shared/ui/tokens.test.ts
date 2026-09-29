import { describe, expect, it } from 'vitest';

import { CONTRAST_PAIRS, contrastRatio, luminance, type TokenName } from './contrast';
import tokensCss from './tokens.css?raw';

type Theme = 'light' | 'dark';

function themeBlock(theme: Theme): Map<string, string> {
  const match = new RegExp(String.raw`\[data-theme='${theme}'\]\s*\{([^}]*)\}`).exec(tokensCss);
  if (match?.[1] === undefined) {
    throw new Error(`tokens.css has no [data-theme='${theme}'] block`);
  }
  const values = new Map<string, string>();
  for (const [, name, value] of match[1].matchAll(/--([a-z-]+):\s*([^;]+);/g)) {
    if (name !== undefined && value !== undefined) {
      values.set(name, value.trim());
    }
  }
  return values;
}

const themes: Record<Theme, Map<string, string>> = {
  light: themeBlock('light'),
  dark: themeBlock('dark'),
};

function color(theme: Theme, token: TokenName): string {
  const value = themes[theme].get(token);
  if (value === undefined) {
    throw new Error(`--${token} is missing from the ${theme} theme`);
  }
  return value;
}

describe('design tokens', () => {
  it('define the same variables in the light and dark themes', () => {
    expect([...themes.dark.keys()].sort()).toEqual([...themes.light.keys()].sort());
  });

  it('keep the deck palette for the accent fills', () => {
    for (const theme of ['light', 'dark'] as const) {
      expect(color(theme, 'understanding')).toBe('#3772ff');
      expect(color(theme, 'decision')).toBe('#fdc840');
      expect(color(theme, 'risk')).toBe('#e12b37');
    }
    expect(color('dark', 'canvas')).toBe('#070707');
    expect(color('light', 'surface-sunken')).toBe('#e6e6e4');
  });

  it.each(
    CONTRAST_PAIRS.flatMap((pair) =>
      (['light', 'dark'] as const).map((theme) => ({ ...pair, theme })),
    ),
  )('$theme: $fg on $bg meets $min:1 ($use)', ({ theme, fg, bg, min }) => {
    const ratio = contrastRatio(color(theme, fg), color(theme, bg));
    expect(ratio).toBeGreaterThanOrEqual(min);
  });

  it('never allow saturated red or blue as body text on the light surfaces', () => {
    for (const accent of ['risk', 'understanding'] as const) {
      expect(contrastRatio(color('light', accent), color('light', 'canvas'))).toBeLessThan(4.5);
      expect(CONTRAST_PAIRS.some((pair) => pair.fg === accent)).toBe(false);
    }
  });
});

describe('contrast math', () => {
  it('matches the WCAG reference values', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 5);
    expect(contrastRatio('#070707', '#fdc840')).toBeCloseTo(12.96, 1);
    expect(luminance('#ffffff')).toBeCloseTo(1, 5);
  });

  it('refuses colors with alpha, which would make the ratio meaningless', () => {
    expect(() => luminance('#070707b3')).toThrow(/opaque/);
  });
});
