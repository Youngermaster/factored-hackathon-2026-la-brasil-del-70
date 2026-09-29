import 'vitest';

interface AxeMatchers<R = unknown> {
  /** Passes when an axe-core run (see src/test/axe.ts) reports no violations. */
  toHaveNoViolations: () => R;
}

// vitest-axe 0.1.0 augments the pre-1.0 `Vi` namespace; current Vitest reads custom matchers from `Matchers`.
declare module 'vitest' {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type, @typescript-eslint/no-explicit-any
  interface Matchers<T = any> extends AxeMatchers<T> {}
}
