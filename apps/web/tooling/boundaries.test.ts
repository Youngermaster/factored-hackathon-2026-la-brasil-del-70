// @vitest-environment node
import { fileURLToPath } from 'node:url';

import { ESLint } from 'eslint';
import tseslint from 'typescript-eslint';
import { describe, expect, it } from 'vitest';

import { boundariesConfig } from '../eslint.boundaries.js';

const webRoot = fileURLToPath(new URL('..', import.meta.url));
const fixtureRoot = 'tooling/boundaries-fixture/src';

const eslint = new ESLint({
  cwd: webRoot,
  overrideConfigFile: true,
  overrideConfig: [
    { files: ['**/*.ts'], languageOptions: { parser: tseslint.parser } },
    { files: ['**/*.ts'], ...boundariesConfig },
  ],
});

async function boundaryErrors(fileInFixture: string, code: string): Promise<string[]> {
  const [result] = await eslint.lintText(`${code}\nexport {};\n`, {
    filePath: `${webRoot}/${fixtureRoot}/${fileInFixture}`,
  });
  return (result?.messages ?? []).map((message) => message.message);
}

describe('layer boundaries', () => {
  it.each([
    [
      'entities/probe.ts',
      "import { alphaValue } from '../features/alpha';",
      'entities may not import feature',
    ],
    [
      'shared/probe.ts',
      "import { customer } from '../entities/customer';",
      'shared may not import entities',
    ],
    [
      'features/beta/probe.ts',
      "import { home } from '../../pages/home';",
      'feature may not import pages',
    ],
    ['pages/probe.ts', "import { App } from '../app/App';", 'pages may not import app'],
  ])('rejects an upward import from %s', async (file, code, expected) => {
    expect(await boundaryErrors(file, code)).toEqual([`Layer boundary: ${expected}.`]);
  });

  it.each([
    ['pages/probe.ts', "import { alphaValue } from '../features/alpha/internal';"],
    ['features/beta/probe.ts', "import { alphaValue } from '../alpha/internal';"],
  ])('rejects importing feature internals from %s', async (file, code) => {
    expect(await boundaryErrors(file, code)).toEqual([
      'Import a feature through its public index.ts, never its internals.',
    ]);
  });

  it.each([
    ['app/probe.ts', "import { home } from '../pages/home';"],
    ['pages/probe.ts', "import { alphaValue } from '../features/alpha';"],
    ['features/beta/probe.ts', "import { alphaValue } from '../alpha';"],
    ['features/beta/probe.ts', "import { customer } from '../../entities/customer';"],
    ['features/alpha/probe.ts', "import { alphaValue } from './internal';"],
    ['entities/probe.ts', "import { format } from '../shared/format';"],
  ])('accepts a downward or public import from %s', async (file, code) => {
    expect(await boundaryErrors(file, code)).toEqual([]);
  });
});
