// Layer boundaries for src/: pages -> features -> entities -> shared, with app as the composition root.
// Shared by eslint.config.js and by tooling/boundaries.test.ts, which proves the policies fire.
import boundaries from 'eslint-plugin-boundaries';

/** Element types, matched as path suffixes so the same policies apply to the test fixture tree. */
export const boundaryElements = [
  { type: 'main', pattern: 'src/main.tsx', mode: 'file' },
  { type: 'app', pattern: 'src/app' },
  { type: 'pages', pattern: 'src/pages' },
  { type: 'feature', pattern: 'src/features/*', capture: ['featureName'] },
  { type: 'entities', pattern: 'src/entities' },
  { type: 'shared', pattern: 'src/shared' },
  { type: 'test', pattern: 'src/test' },
];

const allowed = (fromType, toTypes) => ({
  from: { element: { type: fromType } },
  allow: { to: { element: { types: { anyOf: toTypes } } } },
});

const policies = [
  allowed('main', ['app']),
  allowed('app', ['pages', 'feature', 'entities', 'shared']),
  allowed('pages', ['feature', 'entities', 'shared']),
  // Another feature is reachable only through its index.ts (see the last policy).
  allowed('feature', ['feature', 'entities', 'shared']),
  allowed('entities', ['shared']),
  allowed('test', ['app', 'pages', 'feature', 'entities', 'shared']),
  // Last policy wins: from outside a feature, only its index.ts is importable. Imports inside the
  // same feature are internal and not checked.
  {
    disallow: { to: { element: { type: 'feature', fileInternalPath: '!(index.ts)' } } },
    message: 'Import a feature through its public index.ts, never its internals.',
  },
];

const dependenciesRule = (extraPolicies) => [
  'error',
  {
    default: 'disallow',
    message: 'Layer boundary: {{ from.element.type }} may not import {{ to.element.type }}.',
    policies: [...extraPolicies, ...policies],
  },
];

/**
 * Colocated tests (*.test.ts, *.test.tsx) may also import the shared test infrastructure in src/test (render
 * helpers, MSW handlers); every other boundary still applies to them.
 * @type {import('eslint').Linter.Config}
 */
export const boundariesTestOverride = {
  rules: {
    'boundaries/dependencies': dependenciesRule(
      ['app', 'pages', 'feature', 'entities', 'shared'].map((type) => allowed(type, ['test'])),
    ),
  },
};

/**
 * Flat-config block with the boundary settings and rules.
 * @type {import('eslint').Linter.Config}
 */
export const boundariesConfig = {
  plugins: { boundaries },
  settings: {
    'boundaries/elements': boundaryElements,
    'boundaries/legacy-warnings': false,
    'import/resolver': {
      typescript: { alwaysTryTypes: true, project: './tsconfig.app.json' },
    },
  },
  rules: {
    'boundaries/dependencies': dependenciesRule([]),
  },
};
