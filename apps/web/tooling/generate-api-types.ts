// CLI for `make openapi`: node tooling/generate-api-types.ts [--check]
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';

import { generateApiTypes, typesPath } from './api-types.ts';

const generated = await generateApiTypes();
if (process.argv.includes('--check')) {
  const current = await readFile(typesPath, 'utf8').catch(() => '');
  if (current !== generated) {
    console.error(`stale: ${typesPath}; run make openapi`);
    process.exit(1);
  }
} else {
  await mkdir(dirname(typesPath), { recursive: true });
  await writeFile(typesPath, generated, 'utf8');
  console.log(`wrote ${typesPath}`);
}
