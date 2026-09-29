import { expect } from 'vitest';
import { configureAxe } from 'vitest-axe';
import * as matchers from 'vitest-axe/matchers';

expect.extend(matchers);

/**
 * axe-core through vitest-axe (0.1.0; its axe-core range resolves to the pinned 4.13). jsdom has no layout or
 * canvas, so axe's color-contrast rule can only report "incomplete" there; it is switched off here and contrast is
 * enforced for every allowed token pair, in both themes, by src/shared/ui/tokens.test.ts.
 */
export const axe = configureAxe({
  rules: {
    'color-contrast': { enabled: false },
    // A component rendered alone is not a whole page; landmark and heading-order checks run on the layouts.
    region: { enabled: false },
  },
});
