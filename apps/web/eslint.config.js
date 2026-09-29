import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

import { boundariesConfig, boundariesTestOverride } from './eslint.boundaries.js';

export default tseslint.config(
  {
    ignores: [
      'dist',
      'coverage',
      'node_modules',
      'tooling/boundaries-fixture',
      '.shots',
      'src/shared/api/generated',
    ],
  },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.strictTypeChecked,
      tseslint.configs.stylisticTypeChecked,
    ],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [reactHooks.configs.flat['recommended-latest'], jsxA11y.flatConfigs.strict],
    plugins: { 'react-refresh': reactRefresh },
    rules: {
      'react-refresh/only-export-components': ['error', { allowConstantExport: true }],
      '@typescript-eslint/no-explicit-any': 'error',
      // Scrollable regions (wide tables, long records) must be keyboard focusable (WCAG 2.1.1, axe
      // scrollable-region-focusable); they carry role="region" and a name.
      'jsx-a11y/no-noninteractive-tabindex': [
        'error',
        { tags: [], roles: ['tabpanel', 'region'], allowExpressionValues: true },
      ],
      'no-restricted-syntax': [
        'error',
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: 'Never use dangerouslySetInnerHTML; render model output as plain text.',
        },
      ],
      'no-restricted-globals': [
        'error',
        {
          name: 'localStorage',
          message: 'Never store session data in web storage; the session is an httpOnly cookie.',
        },
        {
          name: 'sessionStorage',
          message: 'Never store session data in web storage; the session is an httpOnly cookie.',
        },
      ],
      'no-restricted-properties': [
        'error',
        {
          object: 'window',
          property: 'localStorage',
          message: 'Never store session data in web storage.',
        },
        {
          object: 'window',
          property: 'sessionStorage',
          message: 'Never store session data in web storage.',
        },
      ],
    },
  },
  {
    // The one module that stores per-viewer display preferences (theme and locale, never session data). It is the
    // only place web storage may be touched; see src/shared/lib/preferences.ts.
    // Tests may seed and inspect web storage to test that module and the pre-paint theme script.
    files: ['src/shared/lib/preferences.ts', 'src/**/*.test.{ts,tsx}', 'src/test/setup.ts'],
    rules: { 'no-restricted-globals': 'off', 'no-restricted-properties': 'off' },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    ...boundariesConfig,
  },
  {
    files: ['src/**/*.test.{ts,tsx}'],
    ...boundariesTestOverride,
  },
  {
    files: ['public/**/*.js'],
    languageOptions: { globals: globals.browser, sourceType: 'script' },
  },
  {
    files: ['*.{js,ts}'],
    languageOptions: { globals: globals.node },
  },
  {
    files: ['**/*.js'],
    extends: [tseslint.configs.disableTypeChecked],
  },
  prettier,
);
