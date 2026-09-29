// @vitest-environment node
import { readFile } from 'node:fs/promises';

import { describe, expect, it } from 'vitest';

import { generateApiTypes, typesPath } from './api-types.ts';

describe('generated API types', () => {
  it('match the committed OpenAPI document (run make openapi after a backend change)', async () => {
    const committed = await readFile(typesPath, 'utf8');
    expect(committed).toBe(await generateApiTypes());
  });

  it('describe the turn endpoint and the problem details shape', async () => {
    const committed = await readFile(typesPath, 'utf8');
    expect(committed).toContain('"/v1/conversations/{conversation_id}/turns"');
    expect(committed).toContain('ProblemDetails');
  });
});
